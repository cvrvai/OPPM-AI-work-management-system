from fastapi import APIRouter, HTTPException
from database import get_db
from schemas import TaskCreate, TaskUpdate

router = APIRouter()


@router.get("/tasks")
async def list_tasks(project_id: str | None = None, status: str | None = None):
    db = get_db()
    query = db.table("tasks").select("*")
    if project_id:
        query = query.eq("project_id", project_id)
    if status:
        query = query.eq("status", status)
    result = query.order("created_at", desc=True).execute()
    return result.data


@router.get("/tasks/{task_id}")
async def get_task(task_id: str):
    db = get_db()
    result = db.table("tasks").select("*").eq("id", task_id).single().execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Task not found")
    return result.data


@router.post("/tasks")
async def create_task(data: TaskCreate):
    db = get_db()
    result = db.table("tasks").insert(data.model_dump()).execute()
    return result.data[0]


@router.put("/tasks/{task_id}")
async def update_task(task_id: str, data: TaskUpdate):
    db = get_db()
    update_data = {k: v for k, v in data.model_dump().items() if v is not None}
    result = db.table("tasks").update(update_data).eq("id", task_id).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Task not found")

    # Recalculate project progress
    task = result.data[0]
    all_tasks = (
        db.table("tasks")
        .select("progress, project_contribution")
        .eq("project_id", task["project_id"])
        .execute()
    )
    if all_tasks.data:
        total_weight = sum(t["project_contribution"] for t in all_tasks.data)
        if total_weight > 0:
            weighted_progress = sum(
                t["progress"] * t["project_contribution"] / total_weight
                for t in all_tasks.data
            )
            db.table("projects").update(
                {"progress": round(weighted_progress)}
            ).eq("id", task["project_id"]).execute()

    return result.data[0]


@router.delete("/tasks/{task_id}")
async def delete_task(task_id: str):
    db = get_db()
    db.table("tasks").delete().eq("id", task_id).execute()
    return {"ok": True}
