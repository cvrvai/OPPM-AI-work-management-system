from fastapi import APIRouter, HTTPException
from database import get_db
from schemas import ProjectCreate, ProjectUpdate, OPPMObjectiveCreate

router = APIRouter()


@router.get("/projects")
async def list_projects():
    db = get_db()
    result = db.table("projects").select("*").order("created_at", desc=True).execute()
    return result.data


@router.get("/projects/{project_id}")
async def get_project(project_id: str):
    db = get_db()
    result = db.table("projects").select("*").eq("id", project_id).single().execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Project not found")
    return result.data


@router.post("/projects")
async def create_project(data: ProjectCreate):
    db = get_db()
    result = db.table("projects").insert(data.model_dump()).execute()
    return result.data[0]


@router.put("/projects/{project_id}")
async def update_project(project_id: str, data: ProjectUpdate):
    db = get_db()
    update_data = {k: v for k, v in data.model_dump().items() if v is not None}
    result = (
        db.table("projects").update(update_data).eq("id", project_id).execute()
    )
    if not result.data:
        raise HTTPException(status_code=404, detail="Project not found")
    return result.data[0]


@router.delete("/projects/{project_id}")
async def delete_project(project_id: str):
    db = get_db()
    db.table("projects").delete().eq("id", project_id).execute()
    return {"ok": True}


# ── OPPM Objectives ──

@router.get("/projects/{project_id}/oppm/objectives")
async def get_oppm_objectives(project_id: str):
    db = get_db()
    objectives = (
        db.table("oppm_objectives")
        .select("*")
        .eq("project_id", project_id)
        .order("sort_order")
        .execute()
    )
    result = []
    for obj in objectives.data or []:
        tasks = (
            db.table("tasks")
            .select("*")
            .eq("oppm_objective_id", obj["id"])
            .order("created_at")
            .execute()
        )
        obj["tasks"] = tasks.data or []
        result.append(obj)
    return result


@router.post("/projects/{project_id}/oppm/objectives")
async def create_oppm_objective(project_id: str, data: OPPMObjectiveCreate):
    db = get_db()
    payload = data.model_dump()
    payload["project_id"] = project_id
    result = db.table("oppm_objectives").insert(payload).execute()
    return result.data[0]


# ── Tasks within a project ──

@router.get("/projects/{project_id}/tasks")
async def get_project_tasks(project_id: str):
    db = get_db()
    result = (
        db.table("tasks")
        .select("*")
        .eq("project_id", project_id)
        .order("created_at")
        .execute()
    )
    return result.data
