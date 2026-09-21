#!/usr/bin/env python3
"""
repair.py -- derive Sigma_R from Sigma_0 by correcting it against the source.

Sigma_R is produced by a PRE-SPECIFIED mechanical procedure, not by editing
until benchmark scores improve. That distinction matters: a specification
hand-tuned against the evaluation would make C3 win by construction and the
comparison would be worthless (paper Sec. 9.2).

The four repairs, each justified by a measured divergence:

  R1 (L3)  Replace the informal role list with the roles the guards actually
           admit, extracted from role.guard.ts. Sigma_0 names 4 of 6 roles and
           never states that FINANCE reaches timesheet pages.
  R2 (L4)  Delete the accounting-period sections. No such subsystem exists in
           finance-service (drift instance L4-01).
  R3 (L4)  Correct the supplier-invoice receipt rule: it binds cash-operation
           validation, not invoice creation (L4-02).
  R4 (L4)  Add the missing navigation step to the 'exporter les factures'
           tour, the only tour of 26 that does not open on the sidebar (L4-03).

R1 is fully automatic. R2-R4 are textual edits whose targets were located
mechanically but whose replacement wording is authored, since deleting prose
requires knowing where a section ends. Every edit is asserted to have applied,
and the script fails loudly if a target is not found -- silent no-ops would
make Sigma_R differ from Sigma_0 in unknown ways.

Usage:
    python repair.py --impl ../extractor/impl.json --sigma0 sigma_0.txt \
                     --out sigma_R.txt
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def apply_edit(text: str, needle: str, replacement: str, label: str) -> str:
    """Replace `needle` exactly once, or abort."""
    n = text.count(needle)
    if n != 1:
        sys.exit(f"[{label}] expected exactly 1 occurrence of target, found {n}. "
                 "Sigma_0 may have changed; repair.py must be updated.")
    return text.replace(needle, replacement)


def cut_between(text: str, start: str, end: str, replacement: str, label: str) -> str:
    """Replace the span from `start` up to (not including) `end`."""
    i = text.find(start)
    if i == -1:
        sys.exit(f"[{label}] start marker not found.")
    j = text.find(end, i + len(start))
    if j == -1:
        sys.exit(f"[{label}] end marker not found after start.")
    return text[:i] + replacement + text[j:]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--impl", type=Path, default=Path("../extractor/impl.json"))
    ap.add_argument("--sigma0", type=Path, default=Path("sigma_0.txt"))
    ap.add_argument("--out", type=Path, default=Path("sigma_R.txt"))
    args = ap.parse_args()

    impl = json.loads(args.impl.read_text(encoding="utf-8"))
    sigma = args.sigma0.read_text(encoding="utf-8")
    original_len = len(sigma)
    guards = impl["L3_authorisation"]["frontend_guards"]
    roles = impl["L3_authorisation"]["declared_roles"]
    applied = []

    # ---- R1: role rules regenerated from the guards ------------------------
    role_block = ["RÔLES (extraits des gardes de routes — source de vérité) :"]
    role_block.append(f"Rôles déclarés dans le système : {', '.join(roles)}.")
    guard_routes = {
        "financeGuard": "toutes les pages /finance/*",
        "timesheetGuard": "/timesheet/projects, /timesheet/tasks, "
                          "/timesheet/my-timesheet, /timesheet/messenger",
        "managerGuard": "/timesheet/validation, /timesheet/reporting",
        "adminGuard": "/admin/audit-logs",
        "adminHrGuard": "/employees, /recruitment",
        "candidateGuard": "les pages /candidate/*",
    }
    for g, admitted in sorted(guards.items()):
        where = guard_routes.get(g, "(routes non cartographiées)")
        role_block.append(f"- {where} : {', '.join(sorted(admitted))}")
    role_block.append(
        "IMPORTANT : un rôle non listé pour une page ne peut pas y accéder. "
        "Ne proposez jamais une action à un rôle qui n'y est pas admis, et "
        "n'affirmez pas qu'un rôle est bloqué s'il figure dans la liste "
        "ci-dessus."
    )
    new_roles = "\n".join(role_block) + "\n"

    sigma = cut_between(
        sigma,
        "RÔLES :\n- COLLABORATOR",
        "\n═══",
        new_roles,
        "R1 roles",
    )
    applied.append("R1 role rules regenerated from guards")

    # ---- R2: delete the phantom accounting-period subsystem ----------------
    sigma = cut_between(
        sigma,
        "PÉRIODES COMPTABLES:",
        "\nTAUX DE CHANGE:",
        "PÉRIODES COMPTABLES:\n"
        "- Le module Finance ne comporte PAS de périodes comptables. Il n'existe "
        "ni verrouillage ni clôture de mois côté Finance.\n"
        "- Si un utilisateur demande à verrouiller ou clôturer une période "
        "comptable, répondez que cette fonctionnalité n'existe pas dans le "
        "module Finance.\n"
        "- (Le verrouillage de période existe uniquement dans le module "
        "Timesheet, sur les feuilles de temps.)\n",
        "R2 accounting periods",
    )
    applied.append("R2 phantom accounting-period subsystem removed")

    sigma = apply_edit(
        sigma,
        "- Une période comptable verrouillée (LOCKED) bloque toute nouvelle "
        "opération sur ce mois.\n",
        "",
        "R2 cash-period claim",
    )
    applied.append("R2 dependent cash-period claim removed")

    sigma = cut_between(
        sigma,
        "WORKFLOW DÉTAILLÉ — PÉRIODE VERROUILLÉE (ADMIN)",
        "\n\nCONTRAINTES",
        "WORKFLOW DÉTAILLÉ — PÉRIODE VERROUILLÉE (TIMESHEET UNIQUEMENT)\n"
        "Le verrouillage de période concerne UNIQUEMENT les feuilles de temps. "
        "Un ADMIN peut verrouiller un mois : ni ajout ni modification de saisie "
        "(\"Cannot add entries to a locked period\"). Il n'existe aucun "
        "équivalent dans le module Finance.",
        "R2 locked-period workflow",
    )
    applied.append("R2 locked-period workflow scoped to timesheet")

    # ---- R3: correct the receipt rule --------------------------------------
    sigma = apply_edit(
        sigma,
        "Étape 8 — Justificatif : PIÈCE OBLIGATOIRE, PDF ou image uniquement.",
        "Étape 8 — Justificatif : fortement recommandé (PDF ou image). "
        "Le backend ne refuse PAS l'enregistrement d'une facture sans "
        "justificatif ; cette obligation ne s'applique qu'à la VALIDATION "
        "d'une opération de trésorerie.",
        "R3 receipt rule",
    )
    applied.append("R3 supplier-invoice receipt over-constraint corrected")

    # ---- R4: repair the incomplete export tour -----------------------------
    sigma = apply_edit(
        sigma,
        'Tour "exporter les factures":\nsteps: [\n'
        '  {"selector":"[data-nav=\'export-excel\']"',
        'Tour "exporter les factures":\nsteps: [\n'
        '  {"selector":"[data-nav=\'finance-menu\']","message":"Ouvrez le menu '
        '**Finance**."},\n'
        '  {"selector":"[data-nav=\'supplier-invoices\']","message":"Allez dans '
        '**Factures Fournisseurs**."},\n'
        '  {"selector":"[data-nav=\'export-excel\']"',
        "R4 export tour",
    )
    applied.append("R4 missing navigation steps added to export tour")

    args.out.write_text(sigma, encoding="utf-8")

    print("Sigma_R written to", args.out)
    print(f"  Sigma_0 : {original_len:,} chars")
    print(f"  Sigma_R : {len(sigma):,} chars  ({len(sigma) - original_len:+,})")
    print("\nrepairs applied:")
    for a in applied:
        print("  -", a)


if __name__ == "__main__":
    main()
