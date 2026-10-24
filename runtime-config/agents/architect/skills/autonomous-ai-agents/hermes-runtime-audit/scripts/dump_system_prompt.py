#!/usr/bin/env python3
"""Dump the system prompt a FRESH session would receive, then audit it.

Fully offline: reuses the same builder as `hermes prompt-size` (no API call, no session
created). Answers "what is really in the system prompt?" — SOUL, USER profile, memory,
custom policy sections, skills index, cwd context files.

Run it with the install's own interpreter (repo dev venv python, or a `source ./activate`
shell) and from the directory you want to simulate (cwd context files are picked up from it):

    cd <hermes-install-dir>
    python -X utf8 scripts/dump_system_prompt.py --out /tmp/prompt.txt \
        --marker "<identity line from SOUL.md>" --marker "[Priority]" --marker "[On demand]"

Audit another profile with HERMES_HOME=/path/to/profile.
Exit codes: 0 ok, 2 a requested marker is missing.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument(
        "--install-dir",
        default=os.environ.get("HERMES_INSTALL_DIR") or os.getcwd(),
        help="Hermes checkout/install dir put on sys.path (default: $HERMES_INSTALL_DIR or cwd)",
    )
    ap.add_argument("--platform", default="cli", help="cli, telegram, discord, ...")
    ap.add_argument("--out", default=None, help="prompt text output path (default: ./fresh_system_prompt.txt)")
    ap.add_argument(
        "--marker",
        action="append",
        default=[],
        help="substring that MUST appear in the prompt (repeatable); exit 2 if missing",
    )
    ap.add_argument(
        "--section",
        action="append",
        default=[],
        help="substring marking a block boundary; prints offset + length to the next one",
    )
    ap.add_argument("--show", type=int, default=0, help="print the first N characters of the prompt")
    args = ap.parse_args()

    install = Path(args.install_dir).expanduser().resolve()
    if not (install / "hermes_cli").is_dir():
        sys.exit(f"not a Hermes install dir (no hermes_cli/): {install}")
    sys.path.insert(0, str(install))

    home = Path(os.environ.get("HERMES_HOME") or (Path.home() / ".hermes"))

    from hermes_cli.prompt_size import _build_inspection_agent
    from agent.system_prompt import build_system_prompt, build_system_prompt_parts

    agent = _build_inspection_agent(args.platform)
    prompt = build_system_prompt(agent)
    parts = build_system_prompt_parts(agent)

    out = Path(args.out) if args.out else (Path.cwd() / "fresh_system_prompt.txt")
    out.write_text(prompt, encoding="utf-8")

    print(f"install dir : {install}")
    print(f"HERMES_HOME : {home}")
    print(f"platform    : {args.platform}")
    print(f"prompt      : {len(prompt)} chars / {len(prompt.encode('utf-8'))} bytes -> {out}")
    for name, text in parts.items():
        if isinstance(text, str):
            print(f"  part {name}: {len(text)} chars")

    policies = home / "policies"
    if policies.is_dir():
        print(f"\npolicies/ file names found in the prompt ({policies}):")
        print("  (on-demand files appear by NAME only - presence here is not proof of loading)")
        for path in sorted(policies.glob("*.md")):
            print(
                f"  {path.name:36s} count={prompt.count(path.name):<3} "
                f"first_offset={prompt.find(path.name)}"
            )

    missing: list[str] = []
    if args.marker:
        print("\nmarkers:")
        for marker in args.marker:
            at = prompt.find(marker)
            print(
                f"  {'OK  ' if at >= 0 else 'MISS'} count={prompt.count(marker):<3} "
                f"first_offset={at}  {marker[:60]!r}"
            )
            if at < 0:
                missing.append(marker)

    if args.section:
        marks = sorted((prompt.find(s), s) for s in args.section if prompt.find(s) >= 0)
        if marks:
            print("\nsections (offset, length to the next mark):")
            for idx, (offset, name) in enumerate(marks):
                end = marks[idx + 1][0] if idx + 1 < len(marks) else len(prompt)
                print(f"  {offset:>8}  {end - offset:>6} chars  {name[:50]!r}")

    if args.show:
        print("\n--- prompt head ---")
        print(prompt[: args.show])

    if missing:
        print(f"\nMISSING MARKERS: {len(missing)} -> {missing}")
        return 2
    print("\nOK: prompt built, all requested markers present")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
