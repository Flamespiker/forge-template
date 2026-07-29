"""
Smoke test — file_io.py

Tests local file parsing — no API calls, no credentials needed.
Run manually from the repo root:
    python -m core.agents.utils.smoke_tests.smoke_file_io

Parses the real Intake Template.xlsx from docs/, and exercises
round-trip read/write for Markdown and YAML using a temp directory.
"""

from __future__ import annotations

import sys
import tempfile
import traceback
from pathlib import Path

PASS = "[PASS]"
FAIL = "[FAIL]"
results: list[tuple[str, bool]] = []


def run(label: str, fn):
    try:
        result = fn()
        print(f"{PASS} {label}")
        results.append((label, True))
        return result
    except Exception as exc:
        print(f"{FAIL} {label}: {exc}")
        traceback.print_exc()
        results.append((label, False))
        return None


def main():
    from core.agents.utils.file_io import read_xlsx, read_markdown, write_markdown, read_yaml, write_yaml

    print("=== File I/O Smoke Test ===\n")

    # ── Excel ──────────────────────────────────────────────────────────────────
    template_path = Path(__file__).parents[4] / "docs" / "Intake Template.xlsx"
    if template_path.exists():
        data = run(
            f"read_xlsx('{template_path.name}')",
            lambda: read_xlsx(template_path),
        )
        if data:
            print(f"       Overview sections: {list(data['overview'].keys())}")
            print(f"       Requirements rows: {len(data['requirements'])}")
    else:
        print(f"  SKIP read_xlsx — {template_path} not found (expected at docs/Intake Template.xlsx)")

    # ── Markdown round-trip ───────────────────────────────────────────────────
    with tempfile.TemporaryDirectory() as tmpdir:
        md_path = Path(tmpdir) / "test.md"
        content = "# FORGE smoke test\n\nThis file was written by file_io smoke test.\n"

        run("write_markdown()", lambda: write_markdown(md_path, content))
        read_back = run("read_markdown()", lambda: read_markdown(md_path))
        run(
            "markdown round-trip content matches",
            lambda: None if read_back == content else (_ for _ in ()).throw(AssertionError(f"Mismatch: {read_back!r} != {content!r}")),
        )

    # ── YAML round-trip ───────────────────────────────────────────────────────
    with tempfile.TemporaryDirectory() as tmpdir:
        yaml_path = Path(tmpdir) / "test.yaml"
        data_out = {"forge": True, "stage": "smoke-test", "items": [1, 2, 3]}

        run("write_yaml()", lambda: write_yaml(yaml_path, data_out))
        data_in = run("read_yaml()", lambda: read_yaml(yaml_path))
        run(
            "YAML round-trip content matches",
            lambda: None if data_in == data_out else (_ for _ in ()).throw(AssertionError(f"Mismatch: {data_in!r}")),
        )

    print("\n=== Results ===")
    passed = sum(1 for _, ok in results if ok)
    for label, ok in results:
        print(f"  {'OK' if ok else 'XX'} {label}")
    print(f"\n{passed}/{len(results)} checks passed.")
    sys.exit(0 if passed == len(results) else 1)


if __name__ == "__main__":
    main()
