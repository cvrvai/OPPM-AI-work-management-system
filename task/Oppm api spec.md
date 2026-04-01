# OPPM AI Chat — Backend API Spec

## New endpoints to add to routers/v1/

---

## POST /workspaces/{ws}/projects/{project_id}/chat

Send a message to the AI about this project. AI may call tools and return structured updates.

### Request
```json
{
  "messages": [
    { "role": "user", "content": "Backend API is done, mark it completed" }
  ],
  "model_id": "uuid-of-ai-model"
}
```
`messages` is the full conversation history (you maintain this on the frontend).
`model_id` is optional — falls back to the workspace's default active model.

### Response
```json
{
  "message": "Backend API marked as completed for W4. Project is now at 45%.",
  "tool_calls": [
    {
      "tool": "set_timeline_status",
      "input": {
        "objective_id": "...",
        "week_start": "2026-04-28",
        "status": "completed"
      },
      "result": { "success": true, "entry_id": "..." }
    }
  ],
  "updated_entities": ["oppm_timeline_entries", "projects"]
}
```

The frontend uses `updated_entities` to know which React Query keys to invalidate.

### Pydantic schemas
```python
# schemas/ai_chat.py

from pydantic import BaseModel
from typing import List, Optional, Any, Literal

class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str

class ChatRequest(BaseModel):
    messages: List[ChatMessage]
    model_id: Optional[str] = None  # falls back to workspace default

class ToolCallResult(BaseModel):
    tool: str
    input: dict
    result: dict
    success: bool
    error: Optional[str] = None

class ChatResponse(BaseModel):
    message: str
    tool_calls: List[ToolCallResult] = []
    updated_entities: List[str] = []
```

---

## GET /workspaces/{ws}/projects/{project_id}/chat/history

Return recent AI chat messages for this project (stored in audit_log or a new table).

### Response
```json
{
  "messages": [
    { "role": "user", "content": "...", "created_at": "2026-04-01T10:00:00Z" },
    { "role": "assistant", "content": "...", "created_at": "2026-04-01T10:00:01Z" }
  ]
}
```

---

## POST /workspaces/{ws}/projects/{project_id}/ai/suggest-plan

Ask AI to generate a full OPPM plan from a description. Returns a preview without committing.

### Request
```json
{
  "description": "We're building a B2B SaaS dashboard. Launch is end of Q2.",
  "commit": false
}
```

### Response (preview mode, commit=false)
```json
{
  "suggested_objectives": [
    { "title": "Product design & wireframes", "suggested_weeks": ["W1", "W2"] },
    { "title": "Backend API", "suggested_weeks": ["W2", "W3", "W4"] },
    { "title": "Frontend dashboard", "suggested_weeks": ["W3", "W4", "W5"] },
    { "title": "QA & testing", "suggested_weeks": ["W5", "W6"] },
    { "title": "Deployment & launch", "suggested_weeks": ["W7", "W8"] }
  ],
  "explanation": "Based on an 8-week timeline to Q2 end...",
  "commit_token": "temp-token-abc123"
}
```

### POST …/ai/suggest-plan/commit
```json
{ "commit_token": "temp-token-abc123" }
```
Actually writes the objectives and timeline entries. Returns the created records.

---

## GET /workspaces/{ws}/projects/{project_id}/ai/weekly-summary

Generate a weekly status summary using AI. Useful for weekly review meetings.

### Response
```json
{
  "summary": "Week 4 of 8. 3 objectives on track, 1 at risk (Frontend dashboard — 2 days behind). No blocked items. Budget at 52% of planned.",
  "at_risk": ["obj-id-frontend"],
  "on_track": ["obj-id-design", "obj-id-backend", "obj-id-qa"],
  "blocked": [],
  "suggested_actions": [
    "Mark frontend dashboard as at-risk for W4",
    "Assign additional resource to frontend team"
  ]
}
```

---

## PATCH /workspaces/{ws}/projects/{project_id}/oppm/objectives/{obj_id}

Update an objective inline (title, owner, sort order).

### Request
```json
{
  "title": "Backend API & database",
  "owner_id": "member-uuid",
  "sort_order": 2
}
```

---

## PUT /workspaces/{ws}/projects/{project_id}/oppm/timeline

Bulk upsert timeline entries. Used by both the AI tool executor and the inline grid editor.

### Request
```json
{
  "entries": [
    {
      "objective_id": "...",
      "week_start": "2026-04-06",
      "status": "completed",
      "notes": "Finished ahead of schedule"
    },
    {
      "objective_id": "...",
      "week_start": "2026-04-13",
      "status": "at_risk"
    }
  ]
}
```

### Response
```json
{
  "upserted": 2,
  "entries": [ ... ]
}
```

---

## POST /workspaces/{ws}/projects/{project_id}/oppm/deliverables

Save summary deliverables, forecast, and risk items (the bottom section of the OPPM form).

### Request
```json
{
  "summary_deliverables": ["Feature-complete build", "Load-tested API", "Signed-off QA report"],
  "forecast": ["Beta available W6", "Soft launch W7", "Full launch W8"],
  "risks": ["3rd-party API dependency", "1 engineer on leave W5"]
}
```

---

## Executor service (services/oppm_tool_executor.py)

```python
from repositories.oppm_repo import OPPMRepository
from repositories.task_repo import TaskRepository
from repositories.project_repo import ProjectRepository

async def execute_oppm_tool(
    tool_name: str,
    tool_input: dict,
    project_id: str,
    workspace_id: str,
    user_id: str,
) -> dict:
    """
    Routes AI tool calls to the correct repository method.
    Returns a dict with success/error and the created/updated record.
    """
    oppm_repo = OPPMRepository()
    task_repo = TaskRepository()
    project_repo = ProjectRepository()

    try:
        match tool_name:

            case "create_objective":
                result = await oppm_repo.create_objective(
                    project_id=project_id,
                    title=tool_input["title"],
                    owner_id=tool_input.get("owner_id"),
                    sort_order=tool_input.get("sort_order", 999),
                )
                updated_entities = ["oppm_objectives"]

            case "update_objective":
                result = await oppm_repo.update_objective(**tool_input)
                updated_entities = ["oppm_objectives"]

            case "set_timeline_status":
                result = await oppm_repo.upsert_timeline_entry(
                    project_id=project_id,
                    objective_id=tool_input["objective_id"],
                    week_start=tool_input["week_start"],
                    status=tool_input["status"],
                    notes=tool_input.get("notes"),
                )
                updated_entities = ["oppm_timeline_entries"]

            case "bulk_set_timeline":
                result = await oppm_repo.bulk_upsert_timeline(
                    project_id=project_id,
                    entries=tool_input["entries"],
                )
                updated_entities = ["oppm_timeline_entries"]

            case "create_task":
                result = await task_repo.create(
                    project_id=project_id,
                    created_by=user_id,
                    **tool_input,
                )
                # Recalculate project progress after task creation
                await project_repo.recalculate_progress(project_id)
                updated_entities = ["tasks", "projects"]

            case "update_task":
                result = await task_repo.update(**tool_input)
                await project_repo.recalculate_progress(project_id)
                updated_entities = ["tasks", "projects"]

            case "update_project_costs":
                result = await oppm_repo.upsert_cost(
                    project_id=project_id, **tool_input
                )
                updated_entities = ["project_costs"]

            case "get_project_summary":
                result = await project_repo.get_summary(project_id)
                updated_entities = []

            case "suggest_oppm_plan":
                # This is handled at the service layer, not here
                # The AI returns a preview; committing is a separate endpoint
                result = {"preview": True, "message": "Plan preview generated"}
                updated_entities = []

            case _:
                return {
                    "success": False,
                    "error": f"Unknown tool: {tool_name}",
                    "updated_entities": [],
                }

        # Write to audit log
        await audit_log.record(
            workspace_id=workspace_id,
            user_id=user_id,
            action=f"ai_tool:{tool_name}",
            entity_type=tool_name,
            new_data=tool_input,
        )

        return {
            "success": True,
            "result": result,
            "updated_entities": updated_entities,
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "updated_entities": [],
        }
```

---

## React Query invalidation (frontend)

After every chat response, invalidate the keys listed in `updated_entities`:

```typescript
// hooks/useChatMutation.ts

const ENTITY_TO_QUERY_KEY: Record<string, string[]> = {
  oppm_objectives:      ['objectives'],
  oppm_timeline_entries:['timeline'],
  tasks:                ['tasks'],
  projects:             ['project'],
  project_costs:        ['costs'],
};

export function useSendMessage(workspaceId: string, projectId: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (messages: ChatMessage[]) =>
      api.post(`/v1/workspaces/${workspaceId}/projects/${projectId}/chat`, { messages }),

    onSuccess: (data) => {
      // Invalidate every entity the AI touched
      data.updated_entities.forEach((entity: string) => {
        const key = ENTITY_TO_QUERY_KEY[entity];
        if (key) queryClient.invalidateQueries({ queryKey: [workspaceId, projectId, ...key] });
      });
    },
  });
}
```