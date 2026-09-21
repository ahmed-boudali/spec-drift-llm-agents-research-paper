#!/usr/bin/env python3
"""
extract.py -- recover the implementation specification I from BI4YOU sources.

Static analysis only: this never runs the application, never touches a database,
and never needs credentials. It reads Angular templates, the Angular router,
the route guards, and the Spring controllers, and emits a machine-readable
description of what the system can actually do.

Layers (see paper Sec. 4.1):
  L1 lexical        -- data-nav selectors present in templates
  L2 reachability   -- routes declared in app.routes.ts
  L3 authorisation  -- roles admitted by guards and @PreAuthorize policies
  L4 procedural     -- business-rule exceptions thrown by the service layer

Usage:
    python extract.py --root <path-to-MyBi4you> --out impl.json
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Iterable

# --------------------------------------------------------------------------
# Patterns
# --------------------------------------------------------------------------

RE_DATA_NAV = re.compile(r'data-nav="([^"]+)"')
RE_ROUTE = re.compile(r"path:\s*'([^']*)'")
RE_GUARD_ON_ROUTE = re.compile(
    r"path:\s*'([^']*)'.*?canActivate:\s*\[([A-Za-z0-9_,\s]+)\]"
)
RE_GUARD_DEF = re.compile(
    r"export\s+const\s+(\w+Guard)\s*:\s*CanActivateFn\s*=\s*\(\)\s*=>\s*\{(.*?)\n\};",
    re.DOTALL,
)
RE_ROLE_LITERAL = re.compile(r"role\s*===\s*'([A-Z_]+)'")
RE_PREAUTH = re.compile(r'@PreAuthorize\("([^"]+)"\)')
RE_ROLE_IN_POLICY = re.compile(r"'([A-Z_]+)'")
RE_ROLE_ENUM = re.compile(r"\b(ADMIN|HR_MANAGER|FINANCE|MANAGER|COLLABORATOR|CANDIDATE)\b")
RE_EXCEPTION_MSG = re.compile(
    r'(?:InvalidOperationException|RuntimeException|IllegalStateException)'
    r'\(\s*"([^"]{8,})"'
)
RE_MAPPING = re.compile(r"@(Get|Post|Put|Delete|Patch)Mapping")


def read(p: Path) -> str:
    """Read a source file, tolerating the mixed encodings in this codebase."""
    for enc in ("utf-8", "latin-1"):
        try:
            return p.read_text(encoding=enc)
        except (UnicodeDecodeError, OSError):
            continue
    return ""


def walk(root: Path, suffix: str, skip: Iterable[str] = ("node_modules", "target", "build")) -> list[Path]:
    out = []
    for p in root.rglob(f"*{suffix}"):
        if any(s in p.parts for s in skip):
            continue
        out.append(p)
    return out


# --------------------------------------------------------------------------
# L1 -- lexical layer
# --------------------------------------------------------------------------

def extract_l1(front: Path) -> dict:
    selectors: dict[str, list[str]] = {}
    for p in walk(front, ".html"):
        for m in RE_DATA_NAV.finditer(read(p)):
            selectors.setdefault(m.group(1), []).append(
                str(p.relative_to(front)).replace("\\", "/")
            )
    return {
        "selectors": sorted(selectors),
        "selector_sites": {k: sorted(set(v)) for k, v in sorted(selectors.items())},
        "count": len(selectors),
    }


# --------------------------------------------------------------------------
# L2 -- reachability layer
# --------------------------------------------------------------------------

def extract_l2(front: Path) -> dict:
    routes_file = front / "src" / "app" / "app.routes.ts"
    if not routes_file.exists():
        hits = walk(front, "app.routes.ts")
        if not hits:
            return {"routes": [], "guarded": {}, "count": 0, "error": "app.routes.ts not found"}
        routes_file = hits[0]

    text = read(routes_file)
    routes = ["/" + r if not r.startswith("/") else r for r in RE_ROUTE.findall(text)]

    guarded: dict[str, list[str]] = {}
    for line in text.splitlines():
        m = RE_GUARD_ON_ROUTE.search(line)
        if m:
            path = "/" + m.group(1) if not m.group(1).startswith("/") else m.group(1)
            guarded[path] = [g.strip() for g in m.group(2).split(",") if g.strip()]

    return {
        "routes": sorted(set(routes)),
        "guarded": guarded,
        "count": len(set(routes)),
        "guarded_count": len(guarded),
        "source": str(routes_file.name),
    }


# --------------------------------------------------------------------------
# L3 -- authorisation layer
# --------------------------------------------------------------------------

def extract_l3(front: Path, back: Path) -> dict:
    # Frontend guards -> role sets
    guards: dict[str, list[str]] = {}
    for p in walk(front, ".ts"):
        if "guard" not in p.name.lower():
            continue
        text = read(p)
        for m in RE_GUARD_DEF.finditer(text):
            name, body = m.group(1), m.group(2)
            roles = sorted(set(RE_ROLE_LITERAL.findall(body)))
            if roles:
                guards[name] = roles

    # Backend @PreAuthorize policies
    policies: dict[str, int] = {}
    endpoints = 0
    for p in walk(back, ".java"):
        text = read(p)
        endpoints += len(RE_MAPPING.findall(text))
        for m in RE_PREAUTH.finditer(text):
            policies[m.group(1)] = policies.get(m.group(1), 0) + 1

    policy_roles = sorted({
        r for pol in policies for r in RE_ROLE_IN_POLICY.findall(pol)
    })

    # Declared role enum
    declared: list[str] = []
    for p in walk(back, "Role.java"):
        text = read(p)
        if "enum Role" in text:
            body = text.split("enum Role", 1)[1]
            declared = sorted(set(RE_ROLE_ENUM.findall(body)))
            if declared:
                break

    return {
        "declared_roles": declared,
        "frontend_guards": dict(sorted(guards.items())),
        "backend_policies": dict(sorted(policies.items(), key=lambda kv: -kv[1])),
        "policy_count_total": sum(policies.values()),
        "policy_count_distinct": len(policies),
        "roles_used_in_policies": policy_roles,
        "endpoints": endpoints,
    }


# --------------------------------------------------------------------------
# L4 -- procedural layer
# --------------------------------------------------------------------------

def extract_l4(back: Path) -> dict:
    rules: dict[str, list[str]] = {}
    for p in walk(back, ".java"):
        if f"{'service'}" not in str(p).lower():
            continue
        # The agent specification itself lives in a service file; exclude it,
        # or its quoted error strings would be mistaken for implementation.
        if p.name == "FinanceAIService.java":
            continue
        for m in RE_EXCEPTION_MSG.finditer(read(p)):
            rules.setdefault(m.group(1).strip(), []).append(p.name)
    return {
        "enforced_rules": {k: sorted(set(v)) for k, v in sorted(rules.items())},
        "count": len(rules),
    }


# --------------------------------------------------------------------------
# Driver
# --------------------------------------------------------------------------

def find_roots(root: Path) -> tuple[Path, Path]:
    """Locate the front-end and back-end trees under an arbitrary checkout."""
    front = back = None
    for p in root.rglob("mybi4you_front"):
        if "node_modules" not in p.parts:
            front = p
            break
    for p in root.rglob("mybi4you_back"):
        if "target" not in p.parts:
            back = p
            break
    if front is None or back is None:
        sys.exit(f"could not locate mybi4you_front / mybi4you_back under {root}")
    return front, back


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--root", required=True, type=Path, help="BI4YOU checkout root")
    ap.add_argument("--out", type=Path, default=Path("impl.json"))
    args = ap.parse_args()

    front, back = find_roots(args.root)
    print(f"front-end : {front}")
    print(f"back-end  : {back}\n")

    impl = {
        "L1_lexical": extract_l1(front),
        "L2_reachability": extract_l2(front),
        "L3_authorisation": extract_l3(front, back),
        "L4_procedural": extract_l4(back),
    }

    args.out.write_text(json.dumps(impl, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"L1  selectors ............ {impl['L1_lexical']['count']}")
    print(f"L2  routes ............... {impl['L2_reachability']['count']}"
          f" ({impl['L2_reachability']['guarded_count']} guarded)")
    print(f"L3  declared roles ....... {len(impl['L3_authorisation']['declared_roles'])}"
          f" {impl['L3_authorisation']['declared_roles']}")
    print(f"L3  @PreAuthorize ........ {impl['L3_authorisation']['policy_count_total']}"
          f" ({impl['L3_authorisation']['policy_count_distinct']} distinct)")
    print(f"L3  endpoints ............ {impl['L3_authorisation']['endpoints']}")
    print(f"L4  enforced rules ....... {impl['L4_procedural']['count']}")
    print(f"\nwrote {args.out}")


if __name__ == "__main__":
    main()
