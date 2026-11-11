"""Check that the committed benchmark files are exactly benchmark v1 (SHA-256 in MANIFEST.json).

Run:  python -m bench.verify_data
"""

from __future__ import annotations

import hashlib
import json
import sys

from bench.generate import OUT_DIR


def main() -> None:
    manifest = json.loads((OUT_DIR / "MANIFEST.json").read_text())
    bad = [
        name
        for name, expected in manifest["sha256"].items()
        if hashlib.sha256((OUT_DIR / name).read_bytes()).hexdigest() != expected
    ]
    for name in bad:
        print(f"MISMATCH {name}")
    print(
        f"{len(manifest['sha256']) - len(bad)} of {len(manifest['sha256'])} benchmark files match MANIFEST.json"
    )
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
