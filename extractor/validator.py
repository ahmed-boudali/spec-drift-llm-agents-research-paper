#!/usr/bin/env python3
"""
validator.py -- the four-dimensional action validator (paper Sec. 5.3).

Given an action emitted by the agent and the context it was emitted in, decide
mechanically whether it is valid under the implementation I:

    V1 existence     -- the selector exists in the templates
    V2 reachability  -- the target is reachable from the current route
    V3 permission    -- the acting role is admitted by the relevant guard
    V4 procedure     -- step ordering respects extracted preconditions

and, separately, whether it is entailed by the specification Sigma:

    E  entailment    -- entailed / contradicted / unspecified

The cross-product of V and E gives the failure attribution of Table 3:
an action that is invalid under I but entailed by Sigma is drift-induced,
not model error.

Importable as a module; run directly for a self-test against the 26 gold tours.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

HERE = Path(__file__).parent

# Selector -> the route on which that control is available. Derived from the
# specification's own navigation map, then checked against the templates.
# Sidebar items are reachable from anywhere because finance-chat.ts expands
# the sidebar and clicks the parent menu toggle before resolving a target.
from routes import SIDEBAR, SIDEBAR_TARGET, ROUTE_OF_SELECTOR, GUARD_OF_ROUTE


@dataclass
class Verdict:
    """Outcome of validating one emitted step."""
    selector: str
    v1_exists: bool = True
    v2_reachable: bool = True
    v3_permitted: bool = True
    v4_ordered: bool = True
    reasons: list[str] = field(default_factory=list)

    @property
    def valid(self) -> bool:
        return self.v1_exists and self.v2_reachable and self.v3_permitted and self.v4_ordered

    def as_dict(self) -> dict:
        return {
            "selector": self.selector, "valid": self.valid,
            "V1_exists": self.v1_exists, "V2_reachable": self.v2_reachable,
            "V3_permitted": self.v3_permitted, "V4_ordered": self.v4_ordered,
            "reasons": self.reasons,
        }


class Validator:
    def __init__(self, impl: dict, spec: dict):
        self.impl, self.spec = impl, spec
        self.impl_selectors = set(impl["L1_lexical"]["selectors"])
        self.spec_selectors = set(spec["L1_selectors"])
        self.guards = impl["L3_authorisation"]["frontend_guards"]

    # -- V1 ---------------------------------------------------------------
    def v1(self, sel: str) -> bool:
        return sel in self.impl_selectors

    # -- V2 ---------------------------------------------------------------
    def v2(self, sel: str, current_route: str) -> tuple[bool, str | None]:
        if sel in SIDEBAR:
            return True, None  # sidebar is reachable from any route
        target = ROUTE_OF_SELECTOR.get(sel)
        if target is None:
            return True, None  # unknown placement: do not penalise
        if current_route == target:
            return True, None
        return False, f"{sel} lives on {target}, not {current_route}"

    # -- V3 ---------------------------------------------------------------
    def v3(self, sel: str, role: str) -> tuple[bool, str | None]:
        target = ROUTE_OF_SELECTOR.get(sel)
        if target is None:
            return True, None
        guard = GUARD_OF_ROUTE.get(target)
        if guard is None:
            return True, None
        admitted = self.guards.get(guard, [])
        if role in admitted:
            return True, None
        return False, f"{role} not admitted by {guard} for {target}"

    # -- V4 ---------------------------------------------------------------
    def v4(self, steps: list[str]) -> tuple[bool, str | None]:
        """Ordering preconditions recoverable from the service layer."""
        # An invoice must be VALIDEE before a payment is recorded:
        # "Seules les factures validees peuvent recevoir un paiement."
        for pay, val in (("record-payment", "validate"),
                         ("record-payment-ci", "validate-ci")):
            if pay in steps and val in steps:
                if steps.index(pay) < steps.index(val):
                    return False, f"{pay} precedes {val}; validation must come first"
        return True, None

    # -- E ----------------------------------------------------------------
    def entailment(self, sel: str) -> str:
        return "entailed" if sel in self.spec_selectors else "unspecified"

    # -- driver -----------------------------------------------------------
    def validate_sequence(self, steps: list[str], route: str, role: str) -> list[Verdict]:
        verdicts = []
        ordered_ok, ord_reason = self.v4(steps)
        simulated = route
        for sel in steps:
            v = Verdict(selector=sel)
            v.v1_exists = self.v1(sel)
            if not v.v1_exists:
                v.reasons.append(f"selector '{sel}' not present in any template")
            ok2, r2 = self.v2(sel, simulated)
            v.v2_reachable = ok2
            if r2:
                v.reasons.append(r2)
            ok3, r3 = self.v3(sel, role)
            v.v3_permitted = ok3
            if r3:
                v.reasons.append(r3)
            v.v4_ordered = ordered_ok
            if not ordered_ok and ord_reason:
                v.reasons.append(ord_reason)
            # A sidebar click navigates; a menu toggle only expands. Advance
            # the simulated route so later steps are judged from where the
            # user now is.
            if sel in SIDEBAR_TARGET:
                dest = SIDEBAR_TARGET[sel]
                if dest is not None:
                    simulated = dest
            elif sel in ROUTE_OF_SELECTOR and ok2:
                simulated = ROUTE_OF_SELECTOR[sel]
            verdicts.append(v)
        return verdicts

    def attribute(self, verdict: Verdict) -> str:
        """Table 3: map (V, E) to a failure class."""
        if verdict.valid:
            return "correct"
        e = self.entailment(verdict.selector)
        if e == "entailed":
            return "F_drift"      # faithful to a false premise
        if e == "unspecified":
            return "F_gap"        # specification silent, model guessed
        return "F_model"          # contradicted a correct specification


def load_default() -> Validator:
    return Validator(
        json.loads((HERE / "impl.json").read_text(encoding="utf-8")),
        json.loads((HERE / "spec.json").read_text(encoding="utf-8")),
    )


def selftest() -> None:
    """Validate the 26 hand-authored gold tours against the implementation."""
    v = load_default()
    tours = v.spec["tours"]
    print("=" * 66)
    print("SELF-TEST -- validating the specification's own gold tours")
    print("=" * 66)

    total = bad = 0
    issues: list[str] = []
    for name, steps in tours.items():
        sels = [s["selector"].replace("[data-nav='", "").replace("']", "")
                for s in steps]
        # Tours start from an unspecified page and navigate via the sidebar;
        # evaluate as ADMIN from the dashboard, the most permissive case.
        verdicts = v.validate_sequence(sels, "/dashboard", "ADMIN")
        for verd in verdicts:
            total += 1
            if not verd.valid:
                bad += 1
                issues.append(f"  [{name}] {verd.selector}: {'; '.join(verd.reasons)}")

    print(f"\ntours: {len(tours)}   steps validated: {total}   invalid: {bad}")
    if issues:
        print("\nsteps flagged invalid:")
        for i in issues[:25]:
            print(i)
        if len(issues) > 25:
            print(f"  ... and {len(issues) - 25} more")
    else:
        print("\nall gold-tour steps validate cleanly.")
    print("\nNote: a hand-authored tour step flagged invalid is itself evidence")
    print("of drift -- the specification instructing an action the code refuses.")


if __name__ == "__main__":
    selftest()
