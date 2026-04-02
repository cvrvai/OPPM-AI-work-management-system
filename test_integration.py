"""Live integration tests for OPPM microservices."""
import urllib.request
import urllib.error
import json

SERVICES = {
    "core": "http://core:8000",
    "ai": "http://ai:8001",
    "git": "http://git:8002",
    "mcp": "http://mcp:8003",
}

PASS = 0
FAIL = 0

def check(label, url, expected_status=200, headers=None, body=None):
    global PASS, FAIL
    try:
        req = urllib.request.Request(url, headers=headers or {}, data=body)
        resp = urllib.request.urlopen(req, timeout=5)
        data = resp.read().decode()
        status = resp.status
        if status == expected_status:
            snippet = data[:80].replace('\n','')
            print(f"  PASS  {label}: {status} {snippet}")
            PASS += 1
        else:
            print(f"  FAIL  {label}: expected {expected_status}, got {status}")
            FAIL += 1
    except urllib.error.HTTPError as e:
        status = e.code
        if status == expected_status:
            print(f"  PASS  {label}: {status} (expected)")
            PASS += 1
        else:
            body_snippet = e.read().decode()[:80] if e.fp else ""
            print(f"  FAIL  {label}: expected {expected_status}, got {status} {body_snippet}")
            FAIL += 1
    except Exception as e:
        print(f"  FAIL  {label}: {type(e).__name__}: {e}")
        FAIL += 1

print("=== Health Checks ===")
for svc, base in SERVICES.items():
    check(f"{svc} /health", f"{base}/health")

print("\n=== Auth Tests ===")
for svc, base in SERVICES.items():
    check(f"{svc} no-auth → 401", f"{base}/api/v1/workspaces", expected_status=401)

print("\n=== Internal Key Tests ===")
check("core /api/v1/workspaces with bad key → 401",
      "http://core:8000/api/v1/workspaces",
      expected_status=401,
      headers={"X-Internal-API-Key": "wrong-key"})

print(f"\n{'='*40}")
print(f"Results: {PASS} passed, {FAIL} failed")
