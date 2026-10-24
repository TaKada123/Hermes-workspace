#!/usr/bin/env python3
"""Create a deterministic local manifest for a background-swap batch.

This helper performs no generation, network request, or upload. Review the CSV,
then process approved rows with Hermes ``image_generate`` under the skill's
explicit-user-approval and budget gate.
"""

from __future__ import annotations

import argparse
import csv
import re
from pathlib import Path

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}


def _variable(raw: str) -> tuple[str, str]:
    if "=" not in raw:
        raise argparse.ArgumentTypeError("--var must be name=value")
    name, value = raw.split("=", 1)
    if not name or not value:
        raise argparse.ArgumentTypeError("--var must have a non-empty name and value")
    return name, value


def _tag(values: dict[str, str]) -> str:
    parts = [re.sub(r"[^A-Za-z0-9]+", "", value)[:20] for value in values.values()]
    return "-".join(part for part in parts if part)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("in_dir", type=Path)
    parser.add_argument("out_dir", type=Path)
    parser.add_argument("--prompt-file", required=True, type=Path)
    parser.add_argument("--size", default="1024x1024")
    parser.add_argument("--var", action="append", default=[], type=_variable, metavar="NAME=VALUE")
    parser.add_argument("--max-images", type=int, default=50)
    args = parser.parse_args()

    if args.max_images < 1:
        parser.error("--max-images must be at least 1")
    if not args.in_dir.is_dir():
        parser.error(f"input directory does not exist: {args.in_dir}")
    if not args.prompt_file.is_file():
        parser.error(f"prompt file does not exist: {args.prompt_file}")

    template = args.prompt_file.read_text(encoding="utf-8")
    variants = [{}] if not args.var else [{name: value} for name, value in args.var]
    inputs = sorted(
        path for path in args.in_dir.iterdir()
        if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS
    )

    args.out_dir.mkdir(parents=True, exist_ok=True)
    manifest = args.out_dir / "batch-manifest.csv"
    rows: list[dict[str, str]] = []
    for image in inputs:
        for variant in variants:
            if len(rows) >= args.max_images:
                break
            prompt = template
            for name, value in variant.items():
                prompt = prompt.replace("{" + name + "}", value)
            suffix = _tag(variant)
            output_name = image.stem + (f"-{suffix}" if suffix else "") + ".png"
            rows.append({
                "input": str(image.resolve()),
                "variant": "; ".join(f"{key}={value}" for key, value in variant.items()),
                "size": args.size,
                "prompt": prompt,
                "output": str((args.out_dir / output_name).resolve()),
                "status": "PENDING_APPROVAL",
            })
        if len(rows) >= args.max_images:
            break

    fieldnames = ["input", "variant", "size", "prompt", "output", "status"]
    with manifest.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"wrote {len(rows)} planned images to {manifest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
