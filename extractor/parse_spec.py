#!/usr/bin/env python3
"""
parse_spec.py -- recover the informal specification Sigma from the agent prompt.

Sigma is the CHAT_SYSTEM_PROMPT constant inside FinanceAIService.java: the
hand-authored natural-language description of the application that the LLM is
given as its entire knowledge of the environment.

Usage:
    python parse_spec.py --root <path-to-MyBi4you> --out spec.json
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

RE_SELECTOR = re.compile(r"data-nav='([^']+)'")
RE_URL = re.compile(r"(/(?:finance|timesheet)(?:/[a-z-]+)?)")
RE_TOUR = re.compile(r'^Tour "([^"]+)":\s*$', re.MULTILINE)
RE_STEP = re.compile(r'\{"selector":"([^"]+)","message":"((?:[^"\\]|\\.)*)"\}')
RE_ROLE = re.compile(r"\b(ADMIN|HR_MANAGER|FINANCE|MANAGER|COLLABORATOR|CANDIDATE)\b")
RE_QUOTED_RULE = re.compile(r'"([A-Z][^"]{12,120})"')

# Literals that appear only inside the JSON schema example the prompt shows the
# model, not as real affordances. Counting them as specified selectors would
# manufacture a phantom that does not exist. See paper Sec. 4.3.1.
SCHEMA_ARTEFACTS = {"selector"}


def read(p: Path) -> str:
    for enc in ("utf-8", "latin-1"):
        try:
            return p.read_text(encoding=enc)
        except (UnicodeDecodeError, OSError):
            continue
    return ""


def locate_prompt(root: Path) -> Path:
    for p in root.rglob("FinanceAIService.java"):
        if "target" not in p.parts:
            return p
    sys.exit("FinanceAIService.java not found")


def slice_prompt(text: str) -> str:
    """Extract the CHAT_SYSTEM_PROMPT text block."""
    start = text.find('CHAT_SYSTEM_PROMPT = """')
    if start == -1:
        sys.exit("CHAT_SYSTEM_PROMPT not found")
    start = text.index("\n", start) + 1
    end = text.find('\n""";', start)
    return text[start:end]


def parse_tours(prompt: str) -> dict[str, list[dict]]:
    """The 26 hand-authored gold action sequences."""
    tours: dict[str, list[dict]] = {}
    names = list(RE_TOUR.finditer(prompt))
    for i, m in enumerate(names):
        end = names[i + 1].start() if i + 1 < len(names) else len(prompt)
        block = prompt[m.end():end]
        steps = [
            {"selector": s.group(1), "message": s.group(2)}
            for s in RE_STEP.finditer(block)
        ]
        if steps:
            tours[m.group(1)] = steps
    return tours


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--root", required=True, type=Path)
    ap.add_argument("--out", type=Path, default=Path("spec.json"))
    args = ap.parse_args()

    src = locate_prompt(args.root)
    prompt = slice_prompt(read(src))

    raw_selectors = set(RE_SELECTOR.findall(prompt))
    selectors = sorted(raw_selectors - SCHEMA_ARTEFACTS)

    urls = sorted({u.rstrip("/") for u in RE_URL.findall(prompt) if u.rstrip("/")})
    tours = parse_tours(prompt)
    roles = sorted(set(RE_ROLE.findall(prompt)))
    quoted_rules = sorted(set(RE_QUOTED_RULE.findall(prompt)))

    spec = {
        "source": str(src.name),
        "lines": prompt.count("\n") + 1,
        "characters": len(prompt),
        "L1_selectors": selectors,
        "L1_excluded_schema_artefacts": sorted(raw_selectors & SCHEMA_ARTEFACTS),
        "L2_urls": urls,
        "L3_roles_mentioned": roles,
        "L4_quoted_rules": quoted_rules,
        "tours": tours,
        "tour_count": len(tours),
    }
    args.out.write_text(json.dumps(spec, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"source ................... {src.name}")
    print(f"prompt lines ............. {spec['lines']}")
    print(f"prompt characters ........ {spec['characters']}")
    print(f"L1 selectors named ....... {len(selectors)}"
          f"  (excluded artefacts: {spec['L1_excluded_schema_artefacts']})")
    print(f"L2 urls named ............ {len(urls)}")
    print(f"L3 roles mentioned ....... {len(roles)} {roles}")
    print(f"L4 quoted rules .......... {len(quoted_rules)}")
    print(f"gold tours ............... {len(tours)}"
          f" ({sum(len(v) for v in tours.values())} steps)")
    print(f"\nwrote {args.out}")


if __name__ == "__main__":
    main()
