#!/usr/bin/env python3
"""
Import NHRS-3.0 SRS roadmap into the OPPM form for the existing project.

Usage:
    python scripts/import_nhrs_oppm.py --dry-run
    python scripts/import_nhrs_oppm.py

Credentials: choonvai@gmail.com / 12345678
Backend:    http://localhost:8000
"""

import argparse
import sys
from datetime import date, timedelta
from typing import Any

import requests

BASE_URL = "http://localhost:8000"
EMAIL = "choonvai@gmail.com"
PASSWORD = "12345678"

# ── SRS-derived OPPM data ──

SUB_OBJECTIVES = [
    {"position": 1, "label": "Security & Compliance"},
    {"position": 2, "label": "Clinical Data Standards"},
    {"position": 3, "label": "AI Safety & Governance"},
    {"position": 4, "label": "Performance & Reliability"},
    {"position": 5, "label": "User Experience"},
    {"position": 6, "label": "Operational Excellence"},
]

OBJECTIVES = [
    {"title": "Phase 2 — Clinical Standards Foundation", "sort_order": 1, "priority": "A"},
    {"title": "Phase 3 — Clinical Workflow Completion", "sort_order": 2, "priority": "A"},
    {"title": "Phase 4 — Advanced AI Intelligence", "sort_order": 3, "priority": "B"},
    {"title": "Phase 5 — Operations & Reliability", "sort_order": 4, "priority": "B"},
    {"title": "Compliance Gap Closure (PDPA / HIPAA)", "sort_order": 5, "priority": "A"},
]

# Each task maps to an objective index (0-based) and a list of sub-objective positions (1-based)
# Timeline weeks are expressed as ISO date strings (Monday of each week)
TASKS = [
    # Phase 2 — Clinical Standards Foundation (weeks 2026-05-05 to 2026-06-09)
    {"title": "ICD-10 code field migration on medical_records", "objective_idx": 0, "sub_positions": [2], "weeks": ["2026-05-05", "2026-05-12"]},
    {"title": "LOINC code field migration on lab_results", "objective_idx": 0, "sub_positions": [2], "weeks": ["2026-05-12", "2026-05-19"]},
    {"title": "RxNorm code field migration on prescriptions", "objective_idx": 0, "sub_positions": [2], "weeks": ["2026-05-19"]},
    {"title": "FHIR R4 adapter layer (utils/fhir-mapper.js)", "objective_idx": 0, "sub_positions": [2, 6], "weeks": ["2026-05-19", "2026-05-26", "2026-06-02"]},
    {"title": "FHIR R4 REST API endpoints", "objective_idx": 0, "sub_positions": [2, 6], "weeks": ["2026-05-26", "2026-06-02", "2026-06-09"]},
    {"title": "7-year data retention policy doc + enforcement", "objective_idx": 0, "sub_positions": [1, 6], "weeks": ["2026-06-02", "2026-06-09"]},
    {"title": "UI: ICD-10 picker component", "objective_idx": 0, "sub_positions": [2, 5], "weeks": ["2026-05-26", "2026-06-02"]},
    {"title": "UI: SOAP note structured form", "objective_idx": 0, "sub_positions": [2, 5], "weeks": ["2026-06-02", "2026-06-09"]},
    {"title": "UI: LOINC picker for lab orders", "objective_idx": 0, "sub_positions": [2, 5], "weeks": ["2026-06-09"]},

    # Phase 3 — Clinical Workflow Completion (weeks 2026-06-09 to 2026-07-14)
    {"title": "SOAP clinical note model (draft/sign/lock workflow)", "objective_idx": 1, "sub_positions": [2, 5], "weeks": ["2026-06-09", "2026-06-16", "2026-06-23"]},
    {"title": "Drug interaction checking service", "objective_idx": 1, "sub_positions": [1, 2], "weeks": ["2026-06-16", "2026-06-23", "2026-06-30"]},
    {"title": "Allergy registry + cross-reference", "objective_idx": 1, "sub_positions": [1, 2], "weeks": ["2026-06-23", "2026-06-30"]},
    {"title": "Discharge summary generator", "objective_idx": 1, "sub_positions": [2, 5], "weeks": ["2026-06-30", "2026-07-07", "2026-07-14"]},
    {"title": "Referral system", "objective_idx": 1, "sub_positions": [5, 6], "weeks": ["2026-07-07", "2026-07-14"]},
    {"title": "Lab result notification webhook", "objective_idx": 1, "sub_positions": [5, 6], "weeks": ["2026-07-14"]},
    {"title": "UI: Drug interaction warning banner", "objective_idx": 1, "sub_positions": [1, 5], "weeks": ["2026-06-30", "2026-07-07"]},
    {"title": "UI: Discharge summary form", "objective_idx": 1, "sub_positions": [5], "weeks": ["2026-07-07", "2026-07-14"]},
    {"title": "UI: Consent scope display", "objective_idx": 1, "sub_positions": [1, 5], "weeks": ["2026-07-14"]},
    {"title": "UI: Allergy header badge", "objective_idx": 1, "sub_positions": [1, 5], "weeks": ["2026-07-14"]},

    # Phase 4 — Advanced AI Intelligence (weeks 2026-07-14 to 2026-08-04)
    {"title": "AI confidence scoring (0.0–1.0) on every RAG response", "objective_idx": 2, "sub_positions": [3], "weeks": ["2026-07-14", "2026-07-21"]},
    {"title": "Hallucination detection (post-gen validation)", "objective_idx": 2, "sub_positions": [3], "weeks": ["2026-07-21", "2026-07-28"]},
    {"title": "ML-Service integration in Doctor AI (risk + classifier)", "objective_idx": 2, "sub_positions": [3, 4], "weeks": ["2026-07-21", "2026-07-28", "2026-08-04"]},
    {"title": "Chain-of-thought reasoning for complex queries", "objective_idx": 2, "sub_positions": [3], "weeks": ["2026-07-28", "2026-08-04"]},
    {"title": "UI: Confidence bar on AI responses", "objective_idx": 2, "sub_positions": [3, 5], "weeks": ["2026-07-28"]},
    {"title": "UI: ML risk-score badge in patient header", "objective_idx": 2, "sub_positions": [3, 5], "weeks": ["2026-08-04"]},
    {"title": "UI: Disclaimer screen before AI chat", "objective_idx": 2, "sub_positions": [3, 5], "weeks": ["2026-08-04"]},

    # Phase 5 — Operations & Reliability (parallel with P4, weeks 2026-07-21 to 2026-08-04)
    {"title": "CI/CD pipeline (GitHub Actions)", "objective_idx": 3, "sub_positions": [6], "weeks": ["2026-07-21", "2026-07-28"]},
    {"title": "Sentry error monitoring (5xx alerting)", "objective_idx": 3, "sub_positions": [4, 6], "weeks": ["2026-07-28"]},
    {"title": "Load testing with k6 (p95 < 1s)", "objective_idx": 3, "sub_positions": [4], "weeks": ["2026-07-28", "2026-08-04"]},
    {"title": "AES key rotation mechanism (key versioning)", "objective_idx": 3, "sub_positions": [1], "weeks": ["2026-08-04"]},
    {"title": "Redis sentinel (HA)", "objective_idx": 3, "sub_positions": [4, 6], "weeks": ["2026-08-04"]},
    {"title": "UI: System health status page", "objective_idx": 3, "sub_positions": [5, 6], "weeks": ["2026-07-28"]},
    {"title": "UI: Audit PDF export", "objective_idx": 3, "sub_positions": [1, 5], "weeks": ["2026-08-04"]},
    {"title": "UI: Patient access ledger", "objective_idx": 3, "sub_positions": [1, 5], "weeks": ["2026-08-04"]},

    # Compliance Gap Closure (parallel, throughout)
    {"title": "Right-to-erasure mechanism (PDPA + audit trail)", "objective_idx": 4, "sub_positions": [1], "weeks": ["2026-05-05", "2026-05-12", "2026-05-19", "2026-05-26"]},
    {"title": "De-identification utility for research datasets", "objective_idx": 4, "sub_positions": [1, 2], "weeks": ["2026-06-09", "2026-06-16", "2026-06-23"]},
    {"title": "Breach notification + alerting system", "objective_idx": 4, "sub_positions": [1, 6], "weeks": ["2026-07-07", "2026-07-14", "2026-07-21"]},
    {"title": "Audit READ logging completeness sweep across 14 routes", "objective_idx": 4, "sub_positions": [1], "weeks": ["2026-07-21", "2026-07-28"]},
]

DELIVERABLES = [
    {"item_number": 1, "description": "ICD-10 / LOINC / RxNorm coded clinical records"},
    {"item_number": 2, "description": "FHIR R4 REST API surface"},
    {"item_number": 3, "description": "SOAP-structured clinical note workflow"},
    {"item_number": 4, "description": "Drug-interaction + allergy safety system"},
    {"item_number": 5, "description": "Discharge summary + referral pipeline"},
    {"item_number": 6, "description": "AI confidence scoring + hallucination guard"},
    {"item_number": 7, "description": "ML risk/classifier integrated into Doctor UI"},
    {"item_number": 8, "description": "CI/CD + monitoring + load-test verified production posture"},
    {"item_number": 9, "description": "PDPA compliance package (retention, erasure, de-ID, breach)"},
]

RISKS = [
    {"item_number": 1, "description": "FHIR R4 mapper complexity may slip Phase 2", "rag": "amber"},
    {"item_number": 2, "description": "Drug-interaction dataset licensing/cost unclear", "rag": "amber"},
    {"item_number": 3, "description": "Ollama single-stream bottleneck under concurrent RAG load", "rag": "amber"},
    {"item_number": 4, "description": "AES key rotation requires re-encrypt of historical records", "rag": "red"},
    {"item_number": 5, "description": "Right-to-erasure conflicts with immutable audit trail", "rag": "red"},
    {"item_number": 6, "description": "UI scope (ICD-10 / SOAP / Discharge) is heavy for Phase 2–3", "rag": "amber"},
    {"item_number": 7, "description": "Cloud LLM fallback could leak PHI if de-ID is incomplete", "rag": "red"},
]


class Importer:
    def __init__(self, base_url: str, dry_run: bool = False):
        self.base_url = base_url.rstrip("/")
        self.dry_run = dry_run
        self.token: str | None = None
        self.workspace_id: str | None = None
        self.project_id: str | None = None
        self.sub_objective_map: dict[int, str] = {}  # position -> id
        self.objective_map: dict[int, str] = {}      # sort_order -> id
        self.created_tasks: list[dict] = []

    # ── HTTP helpers ──

    def _headers(self) -> dict[str, str]:
        h = {"Content-Type": "application/json"}
        if self.token:
            h["Authorization"] = f"Bearer {self.token}"
        return h

    def _get(self, path: str) -> Any:
        url = f"{self.base_url}{path}"
        if self.dry_run:
            print(f"[DRY-RUN] GET {url}")
            return None
        resp = requests.get(url, headers=self._headers(), timeout=30)
        resp.raise_for_status()
        return resp.json()

    def _post(self, path: str, payload: dict) -> Any:
        url = f"{self.base_url}{path}"
        if self.dry_run:
            print(f"[DRY-RUN] POST {url} -> {payload}")
            # Return a fake id so downstream dry-run can continue
            return {"id": f"dry-{path.replace('/', '-')}-{hash(str(payload)) & 0xFFFFFFFF}"}
        resp = requests.post(url, json=payload, headers=self._headers(), timeout=30)
        if resp.status_code >= 400:
            print(f"[ERROR] POST {url} -> {resp.status_code}: {resp.text}")
            raise requests.HTTPError(resp.text, response=resp)
        resp.raise_for_status()
        return resp.json()

    def _put(self, path: str, payload: dict) -> Any:
        url = f"{self.base_url}{path}"
        if self.dry_run:
            print(f"[DRY-RUN] PUT {url} -> {payload}")
            return {"success": True}
        resp = requests.put(url, json=payload, headers=self._headers(), timeout=30)
        if resp.status_code >= 400:
            print(f"[ERROR] PUT {url} -> {resp.status_code}: {resp.text}")
            raise requests.HTTPError(resp.text, response=resp)
        resp.raise_for_status()
        return resp.json()

    # ── Steps ──

    def login(self) -> None:
        print("\n[1/9] Authenticating...")
        resp = self._post("/api/auth/login", {"email": EMAIL, "password": PASSWORD})
        if self.dry_run:
            self.token = "dry-token"
            print("  -> dry-run token")
            return
        self.token = resp.get("access_token") or resp.get("token")
        if not self.token:
            raise RuntimeError(f"Login response missing token: {resp}")
        print(f"  -> logged in as {resp.get('email', EMAIL)}")

    def resolve_workspace(self) -> None:
        print("\n[2/9] Resolving workspace...")
        data = self._get("/api/v1/workspaces")
        if self.dry_run:
            self.workspace_id = "dry-ws"
            print("  -> dry-run workspace")
            return
        workspaces = data if isinstance(data, list) else data.get("items", [])
        if not workspaces:
            raise RuntimeError("No workspaces found for this user.")
        # Prefer a workspace with name containing "ic" or just take the first one
        ws = None
        for w in workspaces:
            name = (w.get("name") or "").lower()
            if "ic" in name or "oppm" in name or "nhrs" in name:
                ws = w
                break
        if not ws:
            ws = workspaces[0]
        self.workspace_id = ws["id"]
        print(f"  -> workspace '{ws.get('name')}' ({self.workspace_id})")

    def resolve_project(self) -> None:
        print("\n[3/9] Resolving project...")
        data = self._get(f"/api/v1/workspaces/{self.workspace_id}/projects")
        if self.dry_run:
            self.project_id = "dry-project"
            print("  -> dry-run project")
            return
        projects = data if isinstance(data, list) else data.get("items", [])
        target = None
        for p in projects:
            title = (p.get("title") or "").lower()
            if "national health record" in title or "nhrs" in title:
                target = p
                break
        if not target:
            raise RuntimeError(
                f"No project matching 'National Health Record' or 'NHRS' found. "
                f"Found: {[p.get('title') for p in projects]}"
            )
        self.project_id = target["id"]
        print(f"  -> project '{target.get('title')}' ({self.project_id})")

    def check_existing_oppm(self) -> None:
        print("\n[4/9] Checking existing OPPM data...")
        data = self._get(f"/api/v1/workspaces/{self.workspace_id}/projects/{self.project_id}/oppm")
        if self.dry_run:
            print("  -> dry-run, skipping check")
            return
        sub_objs = data.get("sub_objectives", [])
        objectives = data.get("objectives", [])
        if sub_objs or objectives:
            print(f"  ⚠ WARNING: Existing OPPM data found:")
            print(f"     Sub-objectives: {len(sub_objs)}")
            print(f"     Objectives:     {len(objectives)}")
            print(f"     Re-running will likely create duplicates. Continue at your own risk.")
        else:
            print("  -> clean slate — no existing OPPM data")

    def create_sub_objectives(self) -> None:
        print("\n[5/9] Ensuring sub-objectives (strategic alignment columns)...")
        # Fetch existing sub-objectives first (idempotent)
        existing = self._get(
            f"/api/v1/workspaces/{self.workspace_id}/projects/{self.project_id}/oppm/sub-objectives"
        )
        existing_map = {}
        if existing and isinstance(existing, list):
            for so in existing:
                existing_map[so["position"]] = so["id"]
                print(f"  [EXISTING] [{so['position']}] {so['label']} -> {so['id']}")

        for so in SUB_OBJECTIVES:
            if so["position"] in existing_map:
                self.sub_objective_map[so["position"]] = existing_map[so["position"]]
                continue
            payload = {"position": so["position"], "label": so["label"]}
            resp = self._post(
                f"/api/v1/workspaces/{self.workspace_id}/projects/{self.project_id}/oppm/sub-objectives",
                payload,
            )
            self.sub_objective_map[so["position"]] = resp["id"]
            print(f"  [NEW] [{so['position']}] {so['label']} -> {resp['id']}")

    def create_objectives(self) -> None:
        print("\n[6/9] Creating objectives (phases)...")
        for i, obj in enumerate(OBJECTIVES):
            payload = {
                "title": obj["title"],
                "sort_order": obj["sort_order"],
                "priority": obj["priority"],
            }
            resp = self._post(
                f"/api/v1/workspaces/{self.workspace_id}/projects/{self.project_id}/oppm/objectives",
                payload,
            )
            self.objective_map[i] = resp["id"]
            print(f"  [{obj['sort_order']}] {obj['title']} -> {resp['id']}")

    def create_tasks_and_link(self) -> None:
        print("\n[7/9] Creating tasks + linking sub-objectives + timeline...")
        for t in TASKS:
            obj_id = self.objective_map[t["objective_idx"]]
            task_payload = {
                "title": t["title"],
                "description": "",
                "project_id": self.project_id,
                "oppm_objective_id": obj_id,
                "priority": "medium",
                "project_contribution": 0,
            }
            try:
                resp = self._post(
                    f"/api/v1/workspaces/{self.workspace_id}/tasks",
                    task_payload,
                )
            except requests.HTTPError as exc:
                print(f"  [SKIP] Task creation failed for '{t['title']}': {exc}")
                continue

            task_id = resp["id"]
            self.created_tasks.append({"id": task_id, "title": t["title"]})

            # Link sub-objectives
            sub_ids = [self.sub_objective_map[pos] for pos in t["sub_positions"] if pos in self.sub_objective_map]
            if sub_ids:
                try:
                    self._put(
                        f"/api/v1/workspaces/{self.workspace_id}/projects/{self.project_id}/oppm/tasks/{task_id}/sub-objectives",
                        {"sub_objective_ids": sub_ids},
                    )
                except requests.HTTPError as exc:
                    print(f"  [WARN] Sub-objective link failed for '{t['title']}': {exc}")

            # Timeline entries
            for week in t["weeks"]:
                try:
                    self._put(
                        f"/api/v1/workspaces/{self.workspace_id}/projects/{self.project_id}/oppm/timeline",
                        {"task_id": task_id, "week_start": week, "status": "planned"},
                    )
                except requests.HTTPError as exc:
                    print(f"  [WARN] Timeline entry failed for '{t['title']}' week {week}: {exc}")

            print(f"  -> {t['title']}")

    def create_deliverables(self) -> None:
        print("\n[8/9] Creating deliverables...")
        for d in DELIVERABLES:
            payload = {"item_number": d["item_number"], "description": d["description"]}
            try:
                self._post(
                    f"/api/v1/workspaces/{self.workspace_id}/projects/{self.project_id}/oppm/deliverables",
                    payload,
                )
                print(f"  [{d['item_number']}] {d['description']}")
            except requests.HTTPError as exc:
                print(f"  [SKIP] Deliverable failed: {exc}")

    def create_risks(self) -> None:
        print("\n[9/9] Creating risks...")
        for r in RISKS:
            payload = {"item_number": r["item_number"], "description": r["description"], "rag": r["rag"]}
            try:
                self._post(
                    f"/api/v1/workspaces/{self.workspace_id}/projects/{self.project_id}/oppm/risks",
                    payload,
                )
                print(f"  [{r['item_number']}] ({r['rag']}) {r['description']}")
            except requests.HTTPError as exc:
                print(f"  [SKIP] Risk failed: {exc}")

    def summary(self) -> None:
        print("\n" + "=" * 60)
        print("IMPORT SUMMARY")
        print("=" * 60)
        print(f"Workspace:      {self.workspace_id}")
        print(f"Project:        {self.project_id}")
        print(f"Sub-objectives: {len(self.sub_objective_map)}")
        print(f"Objectives:     {len(self.objective_map)}")
        print(f"Tasks created:  {len(self.created_tasks)}")
        print(f"Deliverables:   {len(DELIVERABLES)}")
        print(f"Risks:          {len(RISKS)}")
        print("=" * 60)
        if self.dry_run:
            print("This was a DRY RUN — no data was written.")
            print("Run without --dry-run to execute.")

    def run(self) -> None:
        self.login()
        self.resolve_workspace()
        self.resolve_project()
        self.check_existing_oppm()
        self.create_sub_objectives()
        self.create_objectives()
        self.create_tasks_and_link()
        self.create_deliverables()
        self.create_risks()
        self.summary()


def main() -> None:
    parser = argparse.ArgumentParser(description="Import NHRS-3.0 SRS into OPPM")
    parser.add_argument("--dry-run", action="store_true", help="Print plan without writing")
    parser.add_argument("--base-url", default=BASE_URL, help=f"Backend base URL (default: {BASE_URL})")
    args = parser.parse_args()

    importer = Importer(base_url=args.base_url, dry_run=args.dry_run)
    try:
        importer.run()
    except Exception as exc:
        print(f"\n[FATAL] {exc}")
        sys.exit(1)


if __name__ == "__main__":
    main()
