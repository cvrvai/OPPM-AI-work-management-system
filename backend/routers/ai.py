from fastapi import APIRouter
from database import get_db
from schemas import AIModelConfig

router = APIRouter()


@router.get("/ai/models")
async def list_ai_models():
    db = get_db()
    result = db.table("ai_models").select("*").order("name").execute()
    return result.data


@router.post("/ai/models")
async def add_ai_model(data: AIModelConfig):
    db = get_db()
    result = db.table("ai_models").insert(data.model_dump()).execute()
    return result.data[0]


@router.put("/ai/models/{model_id}/toggle")
async def toggle_ai_model(model_id: str):
    db = get_db()
    current = db.table("ai_models").select("is_active").eq("id", model_id).single().execute()
    if not current.data:
        return {"error": "Model not found"}
    new_state = not current.data["is_active"]
    db.table("ai_models").update({"is_active": new_state}).eq("id", model_id).execute()
    return {"is_active": new_state}


@router.delete("/ai/models/{model_id}")
async def delete_ai_model(model_id: str):
    db = get_db()
    db.table("ai_models").delete().eq("id", model_id).execute()
    return {"ok": True}
