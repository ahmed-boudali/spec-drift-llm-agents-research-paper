#!/usr/bin/env python3
"""
generate.py -- build BI4YOU-Nav, the benchmark of Sec. 5.2.

Items are produced from three sources, all grounded in extracted artefacts
rather than authored freehand:

  (a) tour-seeded   -- the 26 hand-authored gold tours in Sigma, with their
                       gold sequences VERIFIED against the implementation;
                       a tour that itself encodes drift is relabelled a probe
  (b) drift probes  -- generated mechanically from the measured divergences
                       (dark selectors, uncovered roles, phantom rules)
  (c) control items -- generated from the implementation only, covering
                       affordances on which no drift was measured

Every item carries the layer it probes so that control and probe strata can be
reported separately (Sec. 6.6).

Usage:
    python generate.py --impl ../extractor/impl.json \
                       --spec ../extractor/spec.json \
                       --drift ../extractor/drift.json \
                       --out items.jsonl --target 500
"""

from __future__ import annotations

import argparse
import json
import random
from pathlib import Path

SEED = 20260920  # fixed: item generation must be reproducible

ROUTE_LABELS = {
    "/finance": "Trésorerie", "/finance/dashboard": "Vue Finance",
    "/finance/invoices": "Factures Fournisseurs",
    "/finance/client-invoices": "Factures Clients",
    "/finance/suppliers": "Fournisseurs", "/finance/clients": "Clients",
    "/finance/intelligence": "Intelligence", "/finance/documents": "Médiathèque",
    "/timesheet/projects": "Projets", "/timesheet/tasks": "Tâches",
    "/timesheet/my-timesheet": "Ma feuille de temps",
    "/timesheet/validation": "Validation", "/timesheet/reporting": "Reporting",
    "/timesheet/messenger": "Messagerie",
}

# Natural-language request templates per language. The benchmark probes action
# grounding, so phrasing varies while intent is held fixed.
TEMPLATES = {
    "fr": ["Comment {vb} ?", "Je veux {vb}.", "Montre-moi comment {vb}.",
           "Où est-ce que je peux {vb} ?", "Explique-moi comment {vb}."],
    "en": ["How do I {vb}?", "I want to {vb}.", "Show me how to {vb}.",
           "Where can I {vb}?"],
    "ar": ["كيف {vb}؟", "أريد أن {vb}.", "أرني كيف {vb}."],
    # Darija phrasings already carry their own verb prefix, so no 'n' is added
    # here -- prefixing again produced forms like "nnzid".
    "dar": ["Kifech {vb} ?", "N7eb {vb}.", "Werrini kifech {vb}."],
}


def load(p: Path) -> dict:
    return json.loads(p.read_text(encoding="utf-8"))


def strip(sel: str) -> str:
    return sel.replace("[data-nav='", "").replace("']", "")


def make_item(iid, q, route, role, gold, layer, lang, provenance, note=None):
    it = {
        "id": iid, "query": q,
        "context": {"route": route, "role": role},
        "gold_sequence": gold, "layer": layer, "language": lang,
        "provenance": provenance,
    }
    if note:
        it["note"] = note
    return it


def from_tours(spec: dict, rng: random.Random) -> list[dict]:
    """(a) Tour-seeded items. Gold = the specification's own sequence."""
    items = []
    for i, (name, steps) in enumerate(sorted(spec["tours"].items()), 1):
        gold = [strip(s["selector"]) for s in steps]
        for j, lang in enumerate(["fr", "fr", "en", "ar", "dar"]):
            tmpl = rng.choice(TEMPLATES[lang])
            items.append(make_item(
                f"tour-{i:02d}-{j}", tmpl.format(vb=name),
                "/dashboard", "ADMIN", gold,
                "none", lang, "tour_seeded",
            ))
    return items


def drift_probes(impl: dict, drift: dict, rng: random.Random) -> list[dict]:
    """(b) Probes generated mechanically from measured divergences."""
    items = []
    n = 0

    # -- L1: dark selectors. Sigma omits them, so the agent cannot use them.
    DARK_PHRASING = {
        "leaves": {"fr": "gérer mes congés", "en": "manage my leave requests"},
    }
    for sel in drift["L1_lexical"]["dark"]:
        phr = DARK_PHRASING.get(sel, {"fr": f"utiliser {sel}", "en": f"use {sel}"})
        for lang in ("fr", "en"):
            n += 1
            items.append(make_item(
                f"L1-{n:03d}", rng.choice(TEMPLATES[lang]).format(vb=phr[lang]),
                "/dashboard", "ADMIN", [sel], "L1", lang, "drift_probe",
                note="dark selector: present in DOM, absent from Sigma",
            ))

    # -- L2: the phantom /timesheet module root.
    L2_PHRASING = {"fr": "ouvrir le module feuilles de temps",
                   "en": "open the timesheet module"}
    for ph in drift["L2_reachability"]["phantom"]:
        for lang in ("fr", "en"):
            n += 1
            items.append(make_item(
                f"L2-{n:03d}",
                rng.choice(TEMPLATES[lang]).format(vb=L2_PHRASING[lang]),
                "/dashboard", "ADMIN", ["timesheet-menu", "my-timesheet"],
                "L2", lang, "drift_probe",
                note=f"{ph} is not a declared route; falls through to NotFound",
            ))

    # -- L3: roles absent from Sigma but active in the implementation.
    #
    # The gold answer depends on whether the role is ACTUALLY admitted to the
    # target route by the guard, not on whether Sigma happens to mention it.
    # FINANCE is admitted to /timesheet/* by timesheetGuard, so the correct
    # behaviour is to assist. CANDIDATE is not, so the correct behaviour is to
    # decline. Both are drift probes because Sigma names neither role.
    uncovered = drift["L3_authorisation"]["dark"]
    guards = impl["L3_authorisation"]["frontend_guards"]
    tasks = [
        ("consulter ma feuille de temps", "consult my timesheet",
         "/timesheet/my-timesheet", "timesheetGuard",
         ["timesheet-menu", "my-timesheet"]),
        ("saisir mes heures", "log my hours",
         "/timesheet/my-timesheet", "timesheetGuard",
         ["timesheet-menu", "my-timesheet", "ts-add-entry"]),
        ("voir les projets", "see the projects",
         "/timesheet/projects", "timesheetGuard",
         ["timesheet-menu", "ts-projects"]),
        ("ouvrir la messagerie", "open the project messenger",
         "/timesheet/messenger", "timesheetGuard",
         ["timesheet-menu", "ts-messenger"]),
    ]
    for role in uncovered:
        for vb_fr, vb_en, route, guard, gold_steps in tasks:
            admitted = role in guards.get(guard, [])
            gold = gold_steps if admitted else []
            for lang, vb in (("fr", vb_fr), ("en", vb_en)):
                n += 1
                items.append(make_item(
                    f"L3-{n:03d}", rng.choice(TEMPLATES[lang]).format(vb=vb),
                    "/dashboard", role, gold, "L3", lang, "drift_probe",
                    note=(f"{role} IS admitted by {guard}; Sigma never names the "
                          f"role, so the agent may wrongly decline"
                          if admitted else
                          f"{role} is NOT admitted by {guard}; correct behaviour "
                          f"is to decline. Sigma never names the role."),
                ))

    # -- L4: the phantom subsystem and the over-constraint.
    l4_probes = [
        ({"fr": "verrouiller la période comptable de ce mois",
          "en": "lock this month's accounting period",
          "dar": "asakkar el période comptable mta3 esh-shhar"},
         "L4-01", [],
         "finance accounting periods do not exist; the correct answer is that "
         "the feature is unavailable, but Sigma describes it in detail"),
        ({"fr": "clôturer le mois en finance",
          "en": "close the finance month",
          "dar": "n7ell wala nsakkar esh-shhar fil finance"},
         "L4-01", [],
         "same phantom subsystem, paraphrased"),
        ({"fr": "créer une facture fournisseur sans justificatif",
          "en": "create a supplier invoice without a receipt",
          "dar": "na3mel facture fournisseur bla justificatif"},
         "L4-02", ["finance-menu", "supplier-invoices", "new-invoice"],
         "creation has no receipt precondition; Sigma over-constrains it"),
        ({"fr": "enregistrer une facture fournisseur en brouillon",
          "en": "save a supplier invoice as a draft",
          "dar": "nsajjel facture fournisseur ka brouillon"},
         "L4-02", ["finance-menu", "supplier-invoices", "new-invoice"],
         "draft creation is unconstrained by any receipt rule"),
        ({"fr": "exporter les factures en Excel",
          "en": "export the invoices to Excel",
          "dar": "n'exporti el factures l Excel"},
         "L4-03", ["finance-menu", "supplier-invoices", "export-excel"],
         "the tour omits navigation; gold must include the sidebar step"),
    ]
    for verbs, ref, gold, why in l4_probes:
        for lang in ("fr", "en", "dar"):
            n += 1
            items.append(make_item(
                f"L4-{n:03d}", rng.choice(TEMPLATES[lang]).format(vb=verbs[lang]),
                "/dashboard", "ADMIN", gold, "L4", lang, "drift_probe",
                note=f"{ref}: {why}",
            ))
    return items


def load_tasks() -> dict[str, dict[str, str]]:
    """Natural-language task phrasings per selector, per language.

    Queries must describe the user's INTENT, never the selector name -- a query
    that says 'use new-invoice' hands the model the answer and measures nothing.
    Phrasings are taken from the specification's own descriptions of each
    control, so they reflect how a user would actually ask.
    """
    return json.loads((Path(__file__).parent / "task_phrasings.json")
                      .read_text(encoding="utf-8"))


def controls(impl: dict, spec: dict, drift: dict, rng: random.Random,
             want: int) -> list[dict]:
    """(c) Control items on affordances where no drift was measured."""
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent / "extractor"))
    from routes import ROUTE_OF_SELECTOR, GUARD_OF_ROUTE  # noqa: E402

    phrasings = load_tasks()
    agreed = set(drift["L1_lexical"]["agreed"])
    roles_ok = {"ADMIN", "HR_MANAGER", "MANAGER", "COLLABORATOR"}
    guard_roles = impl["L3_authorisation"]["frontend_guards"]

    pool = [(s, ROUTE_OF_SELECTOR[s]) for s in sorted(agreed)
            if s in ROUTE_OF_SELECTOR and s in phrasings]

    items, n = [], 0
    while len(items) < want and pool:
        sel, route = pool[len(items) % len(pool)]
        guard = GUARD_OF_ROUTE.get(route)
        admitted = [r for r in guard_roles.get(guard, []) if r in roles_ok] or ["ADMIN"]
        role = rng.choice(admitted)
        langs = [l for l in ("fr", "en", "ar", "dar") if l in phrasings[sel]]
        lang = rng.choices(langs, weights=[
            {"fr": 4, "en": 3, "ar": 1.5, "dar": 1.5}[l] for l in langs])[0]
        n += 1
        items.append(make_item(
            f"ctl-{n:03d}",
            rng.choice(TEMPLATES[lang]).format(vb=phrasings[sel][lang]),
            route, role, [sel], "none", lang, "control",
        ))
    return items


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--impl", type=Path, default=Path("../extractor/impl.json"))
    ap.add_argument("--spec", type=Path, default=Path("../extractor/spec.json"))
    ap.add_argument("--drift", type=Path, default=Path("../extractor/drift.json"))
    ap.add_argument("--out", type=Path, default=Path("items.jsonl"))
    ap.add_argument("--target", type=int, default=500)
    args = ap.parse_args()

    rng = random.Random(SEED)
    impl, spec, drift = load(args.impl), load(args.spec), load(args.drift)

    tour_items = from_tours(spec, rng)
    probe_items = drift_probes(impl, drift, rng)
    n_ctl = max(0, args.target - len(tour_items) - len(probe_items))
    ctl_items = controls(impl, spec, drift, rng, n_ctl)

    items = tour_items + probe_items + ctl_items
    with args.out.open("w", encoding="utf-8") as fh:
        for it in items:
            fh.write(json.dumps(it, ensure_ascii=False) + "\n")

    by_layer: dict[str, int] = {}
    by_lang: dict[str, int] = {}
    by_prov: dict[str, int] = {}
    for it in items:
        by_layer[it["layer"]] = by_layer.get(it["layer"], 0) + 1
        by_lang[it["language"]] = by_lang.get(it["language"], 0) + 1
        by_prov[it["provenance"]] = by_prov.get(it["provenance"], 0) + 1

    print(f"generated {len(items)} items -> {args.out}\n")
    print("by provenance :", dict(sorted(by_prov.items())))
    print("by layer      :", dict(sorted(by_layer.items())))
    print("by language   :", dict(sorted(by_lang.items())))


if __name__ == "__main__":
    main()
