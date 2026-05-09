"""OPPM objectives, timeline, costs, sub-objectives, task-owners, deliverables, forecasts, risks repositories."""

import uuid
from datetime import date, datetime
from decimal import Decimal
from sqlalchemy import select, delete as sa_delete
from sqlalchemy.ext.asyncio import AsyncSession

from domains.workspace.base_repository import BaseRepository
from shared.models.oppm import (
    OPPMObjective, OPPMTimelineEntry, ProjectCost,
    OPPMSubObjective, TaskSubObjective,
    OPPMDeliverable, OPPMForecast, OPPMRisk,
    OPPMTemplate, OPPMHeader, OPPMTaskItem,
    OPPMBorderOverride,
    OPPMVirtualMember,
)
from shared.models.task import Task, TaskAssignee, TaskOwner
from shared.models.workspace import WorkspaceMember


def _serialize(value):
    """Convert ORM column value to JSON-safe type."""
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    return value


def _row_to_dict(obj) -> dict:
    return {c.name: _serialize(getattr(obj, c.name)) for c in obj.__table__.columns}


class ObjectiveRepository(BaseRepository):
    model = OPPMObjective

    async def find_project_objectives(self, project_id: str) -> list[OPPMObjective]:
        return await self.find_all(
            filters={"project_id": project_id},
            order_by="sort_order",
            desc=False,
        )

    async def find_with_tasks(self, project_id: str) -> list[dict]:
        """Get objectives with nested tasks including owners and sub-objective links."""
        objectives = await self.find_project_objectives(project_id)
        result = []
        for obj in objectives:
            d = _row_to_dict(obj)
            stmt = select(Task).where(Task.oppm_objective_id == obj.id).order_by(Task.sort_order, Task.created_at)
            tasks_result = await self.session.execute(stmt)
            tasks = tasks_result.scalars().all()

            task_ids = [t.id for t in tasks]

            # Bulk-load assignees
            assignees_map: dict[str, list[dict]] = {str(tid): [] for tid in task_ids}
            if task_ids:
                assign_stmt = (
                    select(TaskAssignee.task_id, WorkspaceMember.id, WorkspaceMember.display_name)
                    .join(WorkspaceMember, WorkspaceMember.id == TaskAssignee.member_id)
                    .where(TaskAssignee.task_id.in_(task_ids))
                )
                assign_result = await self.session.execute(assign_stmt)
                for row in assign_result.all():
                    assignees_map[str(row.task_id)].append({
                        "id": str(row.id),
                        "display_name": row.display_name,
                    })

            # Bulk-load task owners (A/B/C per member)
            owners_map: dict[str, list[dict]] = {str(tid): [] for tid in task_ids}
            if task_ids:
                owner_stmt = (
                    select(TaskOwner.task_id, TaskOwner.member_id, TaskOwner.priority, WorkspaceMember.display_name)
                    .join(WorkspaceMember, WorkspaceMember.id == TaskOwner.member_id)
                    .where(TaskOwner.task_id.in_(task_ids))
                )
                owner_result = await self.session.execute(owner_stmt)
                for row in owner_result.all():
                    owners_map[str(row.task_id)].append({
                        "member_id": str(row.member_id),
                        "display_name": row.display_name,
                        "priority": row.priority,
                    })

            # Bulk-load sub-objective links
            sub_obj_map: dict[str, list[str]] = {str(tid): [] for tid in task_ids}
            if task_ids:
                sub_stmt = (
                    select(TaskSubObjective.task_id, TaskSubObjective.sub_objective_id)
                    .where(TaskSubObjective.task_id.in_(task_ids))
                )
                sub_result = await self.session.execute(sub_stmt)
                for row in sub_result.all():
                    sub_obj_map[str(row.task_id)].append(str(row.sub_objective_id))

            task_dicts = []
            for t in tasks:
                td = _row_to_dict(t)
                td["assignees"] = assignees_map.get(str(t.id), [])
                td["owners"] = owners_map.get(str(t.id), [])
                td["sub_objective_ids"] = sub_obj_map.get(str(t.id), [])
                task_dicts.append(td)

            d["tasks"] = task_dicts
            result.append(d)
        return result


class TimelineRepository(BaseRepository):
    model = OPPMTimelineEntry

    async def find_project_timeline(self, project_id: str) -> list[OPPMTimelineEntry]:
        return await self.find_all(
            filters={"project_id": project_id},
            order_by="week_start",
            desc=False,
        )

    async def upsert_entry(self, data: dict) -> OPPMTimelineEntry:
        """Insert or update a timeline entry by (objective_id, week_start)."""
        # Convert week_start string to date object for type-safe DB comparison
        week_start_val = data["week_start"]
        if isinstance(week_start_val, str):
            week_start_val = date.fromisoformat(week_start_val)
        stmt = (
            select(OPPMTimelineEntry)
            .where(
                OPPMTimelineEntry.task_id == data["task_id"],
                OPPMTimelineEntry.week_start == week_start_val,
            )
            .limit(1)
        )
        result = await self.session.execute(stmt)
        existing = result.scalar_one_or_none()
        if existing:
            for k, v in data.items():
                if k == "week_start" and isinstance(v, str):
                    v = date.fromisoformat(v)
                setattr(existing, k, v)
            await self.session.flush()
            return existing
        # Ensure week_start is a date in the create dict too
        create_data = {**data, "week_start": week_start_val}
        return await self.create(create_data)


class CostRepository(BaseRepository):
    model = ProjectCost

    async def find_project_costs(self, project_id: str) -> list[ProjectCost]:
        return await self.find_all(
            filters={"project_id": project_id},
            order_by="created_at",
            desc=False,
        )

    async def get_cost_summary(self, project_id: str) -> dict:
        costs = await self.find_project_costs(project_id)
        return {
            "total_planned": sum(float(c.planned_amount) for c in costs),
            "total_actual": sum(float(c.actual_amount) for c in costs),
            "items": [_row_to_dict(c) for c in costs],
        }


# ─── Sub-Objectives ───────────────────────────────────────────

class SubObjectiveRepository(BaseRepository):
    model = OPPMSubObjective

    async def find_project_sub_objectives(self, project_id: str) -> list[OPPMSubObjective]:
        return await self.find_all(
            filters={"project_id": project_id},
            order_by="position",
            desc=False,
        )

    async def set_task_sub_objectives(self, task_id: str, sub_objective_ids: list[str]) -> list[str]:
        """Replace all sub-objective links for a task."""
        await self.session.execute(
            sa_delete(TaskSubObjective).where(TaskSubObjective.task_id == task_id)
        )
        for so_id in sub_objective_ids:
            self.session.add(TaskSubObjective(task_id=task_id, sub_objective_id=so_id))
        await self.session.flush()
        return sub_objective_ids


# ─── Task Owners ──────────────────────────────────────────────

class TaskOwnerRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def set_owner(self, task_id: str, member_id: str, priority: str) -> dict:
        """Set (upsert) A/B/C priority for a task-member pair."""
        stmt = (
            select(TaskOwner)
            .where(TaskOwner.task_id == task_id, TaskOwner.member_id == member_id)
            .limit(1)
        )
        result = await self.session.execute(stmt)
        existing = result.scalar_one_or_none()
        if existing:
            existing.priority = priority
            await self.session.flush()
            return _row_to_dict(existing)
        owner = TaskOwner(task_id=task_id, member_id=member_id, priority=priority)
        self.session.add(owner)
        await self.session.flush()
        return _row_to_dict(owner)

    async def remove_owner(self, task_id: str, member_id: str) -> bool:
        await self.session.execute(
            sa_delete(TaskOwner).where(
                TaskOwner.task_id == task_id, TaskOwner.member_id == member_id
            )
        )
        await self.session.flush()
        return True

    async def find_task_owners(self, task_id: str) -> list[dict]:
        stmt = (
            select(TaskOwner.member_id, TaskOwner.priority, WorkspaceMember.display_name)
            .join(WorkspaceMember, WorkspaceMember.id == TaskOwner.member_id)
            .where(TaskOwner.task_id == task_id)
        )
        result = await self.session.execute(stmt)
        return [
            {"member_id": str(r.member_id), "display_name": r.display_name, "priority": r.priority}
            for r in result.all()
        ]


# ─── Deliverables ─────────────────────────────────────────────

class DeliverableRepository(BaseRepository):
    model = OPPMDeliverable

    async def find_project_deliverables(self, project_id: str) -> list[OPPMDeliverable]:
        return await self.find_all(
            filters={"project_id": project_id},
            order_by="item_number",
            desc=False,
        )


# ─── Forecasts ────────────────────────────────────────────────

class ForecastRepository(BaseRepository):
    model = OPPMForecast

    async def find_project_forecasts(self, project_id: str) -> list[OPPMForecast]:
        return await self.find_all(
            filters={"project_id": project_id},
            order_by="item_number",
            desc=False,
        )


# ─── Risks ────────────────────────────────────────────────────

class RiskRepository(BaseRepository):
    model = OPPMRisk

    async def find_project_risks(self, project_id: str) -> list[OPPMRisk]:
        return await self.find_all(
            filters={"project_id": project_id},
            order_by="item_number",
            desc=False,
        )


# ─── OPPM Templates ──────────────────────────────────────────

class OPPMTemplateRepository(BaseRepository):
    model = OPPMTemplate

    async def find_by_project(self, project_id: str) -> OPPMTemplate | None:
        stmt = select(OPPMTemplate).where(OPPMTemplate.project_id == project_id).limit(1)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def upsert(self, project_id: str, workspace_id: str, sheet_data: list, file_name: str | None = None) -> OPPMTemplate:
        existing = await self.find_by_project(project_id)
        if existing:
            existing.sheet_data = sheet_data
            existing.file_name = file_name
            existing.updated_at = datetime.utcnow()
            await self.session.flush()
            return existing
        return await self.create({
            "project_id": project_id,
            "workspace_id": workspace_id,
            "sheet_data": sheet_data,
            "file_name": file_name,
        })

    async def delete_by_project(self, project_id: str) -> bool:
        stmt = sa_delete(OPPMTemplate).where(OPPMTemplate.project_id == project_id)
        await self.session.execute(stmt)
        await self.session.flush()
        return True


# ─── OPPM Header ──────────────────────────────────────────────

class OPPMHeaderRepository(BaseRepository):
    model = OPPMHeader

    async def find_by_project(self, project_id: str) -> OPPMHeader | None:
        stmt = select(OPPMHeader).where(OPPMHeader.project_id == project_id).limit(1)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def upsert(self, project_id: str, workspace_id: str, data: dict) -> OPPMHeader:
        existing = await self.find_by_project(project_id)
        if existing:
            for k, v in data.items():
                setattr(existing, k, v)
            existing.updated_at = datetime.utcnow()
            await self.session.flush()
            return existing
        return await self.create({
            "project_id": project_id,
            "workspace_id": workspace_id,
            **data,
        })


# ─── OPPM Task Items ──────────────────────────────────────────

class OPPMTaskItemRepository(BaseRepository):
    model = OPPMTaskItem

    async def find_project_items(self, project_id: str) -> list[OPPMTaskItem]:
        """Return all items for a project ordered by sort_order."""
        stmt = (
            select(OPPMTaskItem)
            .where(OPPMTaskItem.project_id == project_id)
            .order_by(OPPMTaskItem.sort_order)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def find_project_items_tree(self, project_id: str) -> list[dict]:
        """Return major tasks with their sub-tasks nested under 'children'."""
        items = await self.find_project_items(project_id)
        by_id: dict[str, dict] = {}
        roots: list[dict] = []
        for item in items:
            d = _row_to_dict(item)
            d["children"] = []
            by_id[str(item.id)] = d
        for item in items:
            d = by_id[str(item.id)]
            if item.parent_id is None:
                roots.append(d)
            else:
                parent = by_id.get(str(item.parent_id))
                if parent:
                    parent["children"].append(d)
        return roots

    async def replace_all(self, project_id: str, workspace_id: str, items: list[dict]) -> list[dict]:
        """Delete all existing items for a project and insert the new set.

        Each item in *items* may contain a 'children' list for sub-tasks.
        Parent rows are inserted first; children reference the newly created parent id.
        """
        await self.session.execute(
            sa_delete(OPPMTaskItem).where(OPPMTaskItem.project_id == project_id)
        )
        await self.session.flush()

        result_rows: list[dict] = []
        sort = 0
        for item in items:
            children = item.pop("children", [])
            item.pop("id", None)  # strip client-side id
            parent = await self.create({
                **item,
                "project_id": project_id,
                "workspace_id": workspace_id,
                "parent_id": None,
                "sort_order": sort,
            })
            sort += 1
            pd = _row_to_dict(parent)
            pd["children"] = []
            for child in children:
                child.pop("id", None)
                child.pop("children", None)
                sub = await self.create({
                    **child,
                    "project_id": project_id,
                    "workspace_id": workspace_id,
                    "parent_id": parent.id,
                    "sort_order": sort,
                })
                sort += 1
                pd["children"].append(_row_to_dict(sub))
            result_rows.append(pd)
        return result_rows


# ─── OPPM Border Overrides ──────────────────────────────────

class OPPMBorderOverrideRepository(BaseRepository):
    """Repository for FortuneSheet cell border overrides.

    Stores AI/user edits as a delta layer on top of the generated scaffold.
    Each row = one cell side (top/bottom/left/right).
    """

    model = OPPMBorderOverride

    async def find_by_project(self, project_id: str) -> list[OPPMBorderOverride]:
        stmt = (
            select(OPPMBorderOverride)
            .where(OPPMBorderOverride.project_id == project_id)
            .order_by(OPPMBorderOverride.cell_row, OPPMBorderOverride.cell_col)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def upsert(
        self,
        project_id: str,
        workspace_id: str,
        cell_row: int,
        cell_col: int,
        side: str,
        style: str,
        color: str,
        created_by: str | None = None,
    ) -> OPPMBorderOverride:
        stmt = (
            select(OPPMBorderOverride)
            .where(
                OPPMBorderOverride.project_id == project_id,
                OPPMBorderOverride.cell_row == cell_row,
                OPPMBorderOverride.cell_col == cell_col,
                OPPMBorderOverride.side == side,
            )
            .limit(1)
        )
        existing = (await self.session.execute(stmt)).scalar_one_or_none()
        if existing:
            existing.style = style
            existing.color = color
            existing.updated_at = datetime.utcnow()
            await self.session.flush()
            return existing
        instance = OPPMBorderOverride(
            project_id=project_id,
            workspace_id=workspace_id,
            cell_row=cell_row,
            cell_col=cell_col,
            side=side,
            style=style,
            color=color,
            created_by=created_by,
        )
        self.session.add(instance)
        await self.session.flush()
        return instance

    async def delete_by_project(self, project_id: str) -> int:
        stmt = sa_delete(OPPMBorderOverride).where(OPPMBorderOverride.project_id == project_id)
        result = await self.session.execute(stmt)
        await self.session.flush()
        return result.rowcount or 0


# ─── Virtual Members ──────────────────────────────────────────

class VirtualMemberRepository(BaseRepository):
    model = OPPMVirtualMember

    async def find_project_virtual_members(self, project_id: str) -> list[OPPMVirtualMember]:
        return await self.find_all(
            filters={"project_id": project_id},
            order_by="created_at",
            desc=False,
        )


# ─── Project All Members (real + virtual) ─────────────────────

class ProjectAllMemberRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def find_project_all_members(self, project_id: str) -> list[dict]:
        """Return unified list of real and virtual members ordered by display_order."""
        from shared.models.oppm import OPPMProjectAllMember
        from shared.models.workspace import WorkspaceMember
        from shared.models.user import User

        stmt = (
            select(
                OPPMProjectAllMember.id,
                OPPMProjectAllMember.workspace_member_id,
                OPPMProjectAllMember.virtual_member_id,
                OPPMProjectAllMember.display_order,
                OPPMProjectAllMember.is_leader,
                WorkspaceMember.display_name.label("ws_display_name"),
                User.email.label("ws_email"),
                User.full_name.label("ws_full_name"),
                OPPMVirtualMember.name.label("virtual_name"),
                OPPMVirtualMember.email.label("virtual_email"),
            )
            .outerjoin(WorkspaceMember, WorkspaceMember.id == OPPMProjectAllMember.workspace_member_id)
            .outerjoin(User, WorkspaceMember.user_id == User.id)
            .outerjoin(OPPMVirtualMember, OPPMVirtualMember.id == OPPMProjectAllMember.virtual_member_id)
            .where(OPPMProjectAllMember.project_id == project_id)
            .order_by(OPPMProjectAllMember.display_order)
        )
        result = await self.session.execute(stmt)
        rows = []
        for r in result.all():
            if r.workspace_member_id:
                email = r.ws_email
                name = r.ws_display_name or r.ws_full_name or (email.split("@")[0] if email else None) or "Member"
                source = "workspace"
                member_id = str(r.workspace_member_id)
            else:
                name = r.virtual_name or "External"
                source = "virtual"
                member_id = str(r.virtual_member_id)
            rows.append({
                "id": str(r.id),
                "member_id": member_id,
                "source": source,
                "name": name,
                "display_order": r.display_order,
                "is_leader": r.is_leader,
            })
        return rows

    async def add_workspace_member(self, project_id: str, workspace_member_id: str, display_order: int = 0, is_leader: bool = False) -> dict:
        from shared.models.oppm import OPPMProjectAllMember
        instance = OPPMProjectAllMember(
            project_id=project_id,
            workspace_member_id=workspace_member_id,
            display_order=display_order,
            is_leader=is_leader,
        )
        self.session.add(instance)
        await self.session.flush()
        return _row_to_dict(instance)

    async def add_virtual_member(self, project_id: str, virtual_member_id: str, display_order: int = 0, is_leader: bool = False) -> dict:
        from shared.models.oppm import OPPMProjectAllMember
        instance = OPPMProjectAllMember(
            project_id=project_id,
            virtual_member_id=virtual_member_id,
            display_order=display_order,
            is_leader=is_leader,
        )
        self.session.add(instance)
        await self.session.flush()
        return _row_to_dict(instance)

    async def remove_member(self, all_member_id: str) -> bool:
        from shared.models.oppm import OPPMProjectAllMember
        stmt = sa_delete(OPPMProjectAllMember).where(OPPMProjectAllMember.id == all_member_id)
        await self.session.execute(stmt)
        await self.session.flush()
        return True

    async def update_order(self, all_member_id: str, display_order: int) -> dict | None:
        from shared.models.oppm import OPPMProjectAllMember
        stmt = select(OPPMProjectAllMember).where(OPPMProjectAllMember.id == all_member_id).limit(1)
        result = await self.session.execute(stmt)
        existing = result.scalar_one_or_none()
        if not existing:
            return None
        existing.display_order = display_order
        await self.session.flush()
        return _row_to_dict(existing)

    async def set_leader(self, project_id: str, all_member_id: str) -> dict | None:
        """Unset any existing leader for the project, then set the new one."""
        from shared.models.oppm import OPPMProjectAllMember
        await self.session.execute(
            sa_delete(OPPMProjectAllMember)
            .where(OPPMProjectAllMember.project_id == project_id, OPPMProjectAllMember.is_leader == True)
        )
        stmt = select(OPPMProjectAllMember).where(OPPMProjectAllMember.id == all_member_id).limit(1)
        result = await self.session.execute(stmt)
        existing = result.scalar_one_or_none()
        if not existing:
            return None
        existing.is_leader = True
        await self.session.flush()
        return _row_to_dict(existing)
