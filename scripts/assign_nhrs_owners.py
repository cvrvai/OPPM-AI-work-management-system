#!/usr/bin/env python3
"""
Assign task owners (A/B/C) for NHRS project.
Since only choonvai@gmail.com exists in the workspace, assign him to
Frontend/UI/Architecture tasks as Priority A (Primary Owner).

Run: python scripts/assign_nhrs_owners.py
"""

import requests

BASE_URL = "http://localhost:8000"
EMAIL = "choonvai@gmail.com"
PASSWORD = "12345678"
WORKSPACE_ID = "4cb12b24-daca-4c05-8ebd-75eb58e16bd1"
PROJECT_ID = "a7d13256-f3c0-4c54-81eb-596ba5d7af78"
CHEONG_MEMBER_ID = "6c0a23bf-5ffd-40f9-87fb-a6b06aee940f"

# Keywords that indicate Cheong's ownership (Frontend, RAG, Architecture, UI)
CHEONG_KEYWORDS = [
    "ui:", "frontend", "rag", "architecture", "fhir adapter", "fhir r4 rest api",
    "discharge summary", "consent scope", "patient access ledger", "system health",
    "audit pdf", "allergy header", "drug interaction warning", "confidence bar",
    "ml risk-score", "disclaimer screen", "icd-10 picker", "soap note", "loinc picker",
]

# Keywords that indicate Sothea's ownership (Backend, Infrastructure, Database)
SOTHEA_KEYWORDS = [
    "backend", "api", "database", "infrastructure", "ci/cd", "sentry", "redis",
    "load testing", "aes key rotation", "fhir mapper", "fhir r4 adapter",
]

# Keywords that indicate Lyhour's ownership (AI Safety, Compliance, Governance)
LYHOUR_KEYWORDS = [
    "compliance", "audit", "consent", "privacy", "pdpa", "hipaa", "governance",
    "right-to-erasure", "de-identification", "breach notification", "audit read logging",
    "data retention", "7-year",
]

# Keywords that indicate Parinha's ownership (ML, Models, Training)
PARINHA_KEYWORDS = [
    "ml-service", "ml ", "classifier", "anomaly", "risk scorer", "disease classifier",
    "readmission predictor", "ml intelligence", "chain-of-thought", "hallucination",
    "ai confidence",
]


def login() -> str:
    resp = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": EMAIL, "password": PASSWORD},
        headers={"Content-Type": "application/json"},
        timeout=30,
        proxies={"http": None, "https": None},
    )
    resp.raise_for_status()
    return resp.json()["access_token"]


def get_tasks(token: str) -> list[dict]:
    resp = requests.get(
        f"{BASE_URL}/api/v1/workspaces/{WORKSPACE_ID}/tasks?project_id={PROJECT_ID}&page_size=200",
        headers={"Authorization": f"Bearer {token}"},
        timeout=30,
        proxies={"http": None, "https": None},
    )
    resp.raise_for_status()
    data = resp.json()
    return data if isinstance(data, list) else data.get("items", [])


def assign_owner(token: str, task_id: str, member_id: str, priority: str) -> None:
    resp = requests.put(
        f"{BASE_URL}/api/v1/workspaces/{WORKSPACE_ID}/projects/{PROJECT_ID}/oppm/tasks/{task_id}/owners",
        json={"member_id": member_id, "priority": priority},
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        timeout=30,
        proxies={"http": None, "https": None},
    )
    if resp.status_code >= 400:
        print(f"  [WARN] Failed to assign {task_id}: {resp.status_code} {resp.text}")
    else:
        print(f"  -> assigned {priority}")


def classify_task(title: str) -> str | None:
    t = title.lower()
    for kw in CHEONG_KEYWORDS:
        if kw in t:
            return "cheong"
    for kw in SOTHEA_KEYWORDS:
        if kw in t:
            return "sothea"
    for kw in LYHOUR_KEYWORDS:
        if kw in t:
            return "lyhour"
    for kw in PARINHA_KEYWORDS:
        if kw in t:
            return "parinha"
    return None


def main() -> None:
    print("[1/3] Authenticating...")
    token = login()
    print("  -> logged in")

    print("\n[2/3] Fetching tasks...")
    tasks = get_tasks(token)
    print(f"  -> found {len(tasks)} tasks")

    print("\n[3/3] Assigning owners...")
    cheong_count = 0
    unassigned = []

    for task in tasks:
        tid = task["id"]
        title = task.get("title", "")
        owner = classify_task(title)

        if owner == "cheong":
            print(f"  [Cheong A] {title}")
            assign_owner(token, tid, CHEONG_MEMBER_ID, "A")
            cheong_count += 1
        else:
            unassigned.append(title)

    print(f"\n  Assigned Cheong to {cheong_count} tasks.")
    if unassigned:
        print(f"  Unassigned ({len(unassigned)} tasks — waiting for team invites):")
        for t in unassigned[:10]:
            print(f"    - {t}")
        if len(unassigned) > 10:
            print(f"    ... and {len(unassigned) - 10} more")

    print("\nDone.")


if __name__ == "__main__":
    main()
