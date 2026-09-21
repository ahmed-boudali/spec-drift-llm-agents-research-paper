#!/usr/bin/env python3
"""
drift.py -- compute specification-implementation drift across the four layers.

Consumes impl.json (extract.py) and spec.json (parse_spec.py) and reports, per
layer, what the specification claims that the implementation lacks (phantom)
and what the implementation provides that the specification omits (dark).

This reproduces Table 2 of the paper. It is pure set arithmetic over the two
extracted descriptions -- no judgement, no model, no running system.

Usage:
    python drift.py --impl impl.json --spec spec.json --out drift.json
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

# Roles named in Sigma only inside the phantom accounting-period section
# (paper Sec. 4.3.4, L4-01). Sigma mentions FINANCE exactly once, in a rule
# describing a subsystem that does not exist in the implementation, and never
# in the role enumeration a reader would consult. We therefore report it
# separately rather than crediting Sigma with covering the role.
ROLE_MENTIONED_ONLY_IN_PHANTOM_RULE = {"FINANCE"}


def load(p: Path) -> dict:
    return json.loads(p.read_text(encoding="utf-8"))


def setdiff(spec: list[str], impl: list[str]) -> dict:
    s, i = set(spec), set(impl)
    return {
        "phantom": sorted(s - i),   # specified, absent from implementation
        "dark": sorted(i - s),      # implemented, absent from specification
        "agreed": sorted(s & i),
        "n_spec": len(s),
        "n_impl": len(i),
        "n_agreed": len(s & i),
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--impl", type=Path, default=Path("impl.json"))
    ap.add_argument("--spec", type=Path, default=Path("spec.json"))
    ap.add_argument("--out", type=Path, default=Path("drift.json"))
    args = ap.parse_args()

    impl, spec = load(args.impl), load(args.spec)

    # ---- L1 lexical -------------------------------------------------------
    l1 = setdiff(spec["L1_selectors"], impl["L1_lexical"]["selectors"])

    # ---- L2 reachability --------------------------------------------------
    # Compare only the module routes Sigma is scoped to describe (finance,
    # timesheet); Sigma explicitly excludes HR, auth and candidate areas.
    impl_scoped = [r for r in impl["L2_reachability"]["routes"]
                   if r.startswith("/finance") or r.startswith("/timesheet")]
    spec_urls = [u for u in spec["L2_urls"] if u]
    l2 = setdiff(spec_urls, impl_scoped)
    l2["note"] = (
        "/timesheet is reported as phantom and this is a real finding, not an "
        "extraction artefact: 'finance' IS a declared route (CashManagement) "
        "while 'timesheet' is NOT, so a bare /timesheet falls through to the "
        "** NotFound wildcard. Sigma's parallel '/finance/*' and '/timesheet/*' "
        "phrasing implies a module-root symmetry the router does not have."
    )

    # ---- L3 authorisation -------------------------------------------------
    declared = impl["L3_authorisation"]["declared_roles"]
    mentioned = spec["L3_roles_mentioned"]
    effective = [r for r in mentioned if r not in ROLE_MENTIONED_ONLY_IN_PHANTOM_RULE]
    l3 = setdiff(effective, declared)
    l3["roles_mentioned_raw"] = sorted(mentioned)
    l3["roles_discounted"] = sorted(set(mentioned) & ROLE_MENTIONED_ONLY_IN_PHANTOM_RULE)
    l3["note"] = (
        "FINANCE appears in Sigma exactly once, inside the phantom "
        "accounting-period rule (L4-01), never in the role enumeration. "
        "Counted as not covered; see drift.py header."
    )

    # Guards admitting roles Sigma never associates with that module
    guard_surprises = {}
    for guard, roles in impl["L3_authorisation"]["frontend_guards"].items():
        unexpected = sorted(set(roles) - set(effective))
        if unexpected:
            guard_surprises[guard] = {"admits": roles, "unstated_in_spec": unexpected}
    l3["guard_surprises"] = guard_surprises

    # ---- L4 procedural ----------------------------------------------------
    # Fully automatic alignment of prose rules to code is an open problem
    # (paper Sec. 10.3). We report the extracted sets and the manually
    # confirmed instances from the audit log (Appendix B).
    l4 = {
        "enforced_rule_count": impl["L4_procedural"]["count"],
        "spec_quoted_rule_count": len(spec["L4_quoted_rules"]),
        "automatic_alignment": False,
        "confirmed_instances": [
            {
                "id": "L4-01",
                "type": "phantom_subsystem",
                "claim": "Finance accounting periods with OPEN/LOCKED states "
                         "blocking invoice and cash-operation creation.",
                "evidence": "No accounting-period entity, repository, service "
                            "or precondition exists in finance-service.",
                "note": "An analogous mechanism IS implemented in "
                        "timesheet-service (TimesheetPeriod.locked).",
            },
            {
                "id": "L4-02",
                "type": "over_constraint",
                "claim": "A receipt is mandatory when creating a supplier "
                         "invoice.",
                "evidence": "The receipt rule exists only for cash operations "
                            "at validation time; SupplierInvoiceService has no "
                            "such precondition on creation.",
            },
            {
                "id": "L4-03",
                "type": "incomplete_procedure",
                "claim": "Tour 'exporter les factures' instructs the user to "
                         "click export-excel / export-pdf.",
                "evidence": "The tour contains no navigation step. Both "
                            "controls live on /finance/invoices, so the "
                            "sequence is unexecutable from any other route. "
                            "It is the only one of the 26 tours that does not "
                            "open with a sidebar step; cf. 'filtrer et "
                            "exporter une liste', which navigates correctly.",
                "discovered_by": "validator.py self-test (not manual audit)",
            },
        ],
    }

    drift = {"L1_lexical": l1, "L2_reachability": l2,
             "L3_authorisation": l3, "L4_procedural": l4}
    args.out.write_text(json.dumps(drift, indent=2, ensure_ascii=False), encoding="utf-8")

    # ---- report -----------------------------------------------------------
    bar = "=" * 66
    print(bar)
    print("SPECIFICATION-IMPLEMENTATION DRIFT -- BI4YOU")
    print(bar)
    print(f"\nL1 LEXICAL        agreed {l1['n_agreed']}/{l1['n_impl']}")
    print(f"   phantom (spec claims, code lacks) : {l1['phantom'] or 'none'}")
    print(f"   dark    (code has, spec omits)    : {l1['dark'] or 'none'}")

    print(f"\nL2 REACHABILITY   agreed {l2['n_agreed']}/{l2['n_impl']}")
    print(f"   phantom : {l2['phantom'] or 'none'}")
    print(f"   dark    : {l2['dark'] or 'none'}")

    print(f"\nL3 AUTHORISATION  covered {l3['n_agreed']}/{len(declared)} declared roles")
    print(f"   absent from spec : {l3['dark'] or 'none'}")
    print(f"   discounted       : {l3['roles_discounted'] or 'none'} (phantom-rule only)")
    for g, d in guard_surprises.items():
        print(f"   {g}: admits {d['unstated_in_spec']} -- unstated in spec")

    print(f"\nL4 PROCEDURAL     {l4['enforced_rule_count']} enforced rules extracted")
    print(f"   automatic alignment: NO (manual audit, Appendix B)")
    for c in l4["confirmed_instances"]:
        print(f"   {c['id']} {c['type']}")

    print(f"\nwrote {args.out}")


if __name__ == "__main__":
    main()
