"""
Demo helper: copy a JSON file into the watch path so the issuer picks it up.
Usage:
    python demo_inject.py path\to\idemia_export.json

Also usable as a quick smoke-test for the parser + credential builder
without starting the full Flask server.
"""

import json
import sys
from pathlib import Path
from datetime import date


def inject(json_path: str, watch_root: str = r"C:\icvs-local-exports"):
    import shutil, uuid
    src = Path(json_path)
    today = date.today().strftime("%Y%m%d")
    dest_dir = Path(watch_root) / today / str(uuid.uuid4())
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / src.name
    shutil.copy2(src, dest)
    print(f"Injected → {dest}")


def smoke_test(json_path: str):
    """Parse and build credential without starting the server."""
    from parser import parse_idemia_json
    from credential import build_pid_sd_jwt
    from cryptography.hazmat.primitives.asymmetric import ec

    with open(json_path, encoding="utf-8") as f:
        data = json.load(f)

    pid = parse_idemia_json(data)
    print("\n── Parsed PID claims ──────────────────────────────────")
    for k, v in pid.items():
        if k == "portrait" and v:
            print(f"  portrait: <{len(v)} bytes base64>")
        elif not k.startswith("_"):
            print(f"  {k}: {v}")

    key = ec.generate_private_key(ec.SECP256R1())
    sd_jwt = build_pid_sd_jwt(pid, "http://localhost:8080", key)
    parts = sd_jwt.split("~")
    print(f"\n── SD-JWT structure ──────────────────────────────────")
    print(f"  JWT header+payload+sig : {parts[0][:60]}…")
    print(f"  Disclosures            : {len(parts)-2}")
    print(f"  Total token length     : {len(sd_jwt)} chars")
    print("\nSmoke test PASSED")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python demo_inject.py <path-to-json> [--smoke-test]")
        sys.exit(1)
    path = sys.argv[1]
    if "--smoke-test" in sys.argv or "-s" in sys.argv:
        smoke_test(path)
    else:
        inject(path)
