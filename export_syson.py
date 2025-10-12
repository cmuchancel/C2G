#!/usr/bin/env python3
import os, requests, pathlib

BASE = os.environ.get("SYSON_BASE_URL", "https://localhost:8443")
OUT = pathlib.Path(os.environ.get("SYSON_OUT_DIR", "exports"))
VERIFY_TLS = os.environ.get("SYSON_VERIFY_TLS", "false").lower() == "true"

sess = requests.Session()

def get(url):
    r = sess.get(url, verify=VERIFY_TLS)
    r.raise_for_status()
    return r.json()

projects = get(f"{BASE}/api/projects")
OUT.mkdir(parents=True, exist_ok=True)

for p in projects:
    pid = p["id"]
    pname = p.get("name", f"project-{pid}").replace("/", "_")
    print(f"Exporting {pname}…")

    resp = sess.get(f"{BASE}/api/projects/{pid}/export", verify=VERIFY_TLS)
    resp.raise_for_status()

    proj_dir = OUT / pname
    proj_dir.mkdir(parents=True, exist_ok=True)
    (proj_dir / "project.json").write_bytes(resp.content)

print("✅ Export complete")

