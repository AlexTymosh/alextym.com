"""Verify all six PR-11 TS2802 source fixes are present."""
from __future__ import annotations
from pathlib import Path
from apply_vor_pr11_ts_hotfix import FILES, PATCHES


def main() -> None:
    for name, path in FILES.items():
        text = path.read_text(encoding="utf-8")
        for old, new in PATCHES[name]:
            if old in text or text.count(new) != 1:
                raise AssertionError(f"Not fixed: {path.name}: {old[:70]}")
        print(f"PASS: {path.name}")
    print("All six TypeScript compatibility fixes are present.")


if __name__ == "__main__":
    main()
