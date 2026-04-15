"""Optimize the Material Design Icons metadata for fast runtime lookup."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from urllib.request import urlopen

SOURCE_URL = (
    "https://raw.githubusercontent.com/OpenDisplay/Home_Assistant_Integration/"
    "refs/heads/main/custom_components/opendisplay/imagegen/assets/"
    "materialdesignicons-webfont_meta.json"
)
DEFAULT_OUTPUT_PATH = (
    Path(__file__).resolve().parents[1]
    / "custom_components"
    / "argon_industria_oled"
    / "assets"
    / "materialdesignicons.meta.json"
)


def _optimize_meta(entries: list[dict[str, object]]) -> dict[str, str]:
    """Flatten icon names and aliases into a single name -> codepoint mapping."""
    optimized: dict[str, str] = {}
    for entry in entries:
        name = entry.get("name")
        codepoint = entry.get("codepoint")
        if not isinstance(name, str) or not isinstance(codepoint, str):
            continue

        optimized[name] = codepoint
        aliases = entry.get("aliases", [])
        if not isinstance(aliases, list):
            continue

        for alias in aliases:
            if isinstance(alias, str):
                optimized.setdefault(alias, codepoint)

    return dict(sorted(optimized.items()))


def _load_source_json(source_url: str) -> list[dict[str, object]]:
    """Download and parse the upstream metadata JSON."""
    with urlopen(source_url, timeout=30) as response:
        raw_json = json.load(response)

    if not isinstance(raw_json, list):
        msg = "Source JSON must be a list of icon entries"
        raise ValueError(msg)

    entries: list[dict[str, object]] = []
    for item in raw_json:
        if isinstance(item, dict):
            entries.append(item)
    return entries


def _build_argument_parser() -> argparse.ArgumentParser:
    """Create the command-line parser for metadata optimization."""
    parser = argparse.ArgumentParser(
        description="Download and optimize Material Design Icons metadata."
    )
    parser.add_argument("--source-url", default=SOURCE_URL, help="Source metadata URL.")
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT_PATH,
        help="Output path for the optimized metadata JSON.",
    )
    return parser


def main() -> None:
    """Run the metadata optimization workflow."""
    parser = _build_argument_parser()
    args = parser.parse_args()

    entries = _load_source_json(args.source_url)
    optimized = _optimize_meta(entries)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(optimized, ensure_ascii=False, separators=(",", ":"), sort_keys=True),
        encoding="utf-8",
    )
    print(f"Wrote {len(optimized)} names/aliases to {args.output}")


if __name__ == "__main__":
    main()
