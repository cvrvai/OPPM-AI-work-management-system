"""Waterfall domain repositories — ProjectPhase, PhaseDocument."""

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from domains.workspace.base_repository import BaseRepository
from shared.models.waterfall import ProjectPhase, PhaseDocument


class ProjectPhaseRepository(BaseRepository):
    model = ProjectPhase

    async def find_project_phases(self, project_id: str) -> list[ProjectPhase]:
        stmt = (
            select(ProjectPhase)
            .where(ProjectPhase.project_id == project_id)
            .order_by(ProjectPhase.position.asc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def find_by_project_and_type(self, project_id: str, phase_type: str) -> ProjectPhase | None:
        stmt = (
            select(ProjectPhase)
            .where(
                ProjectPhase.project_id == project_id,
                ProjectPhase.phase_type == phase_type,
            )
            .limit(1)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def initialize_phases(self, workspace_id: str, project_id: str) -> list[ProjectPhase]:
        """Create the 6 standard waterfall phases for a project."""
        phase_types = [
            ("requirements", 1),
            ("design", 2),
            ("development", 3),
            ("testing", 4),
            ("deployment", 5),
            ("maintenance", 6),
        ]
        phases = []
        for phase_type, position in phase_types:
            phase = await self.create({
                "workspace_id": workspace_id,
                "project_id": project_id,
                "phase_type": phase_type,
                "status": "not_started",
                "position": position,
            })
            phases.append(phase)
        return phases


class PhaseDocumentRepository(BaseRepository):
    model = PhaseDocument

    async def find_phase_documents(self, phase_id: str) -> list[PhaseDocument]:
        stmt = (
            select(PhaseDocument)
            .where(PhaseDocument.phase_id == phase_id)
            .order_by(PhaseDocument.created_at.desc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def increment_version(self, doc_id: str) -> PhaseDocument | None:
        doc = await self.find_by_id(doc_id)
        if doc:
            stmt = (
                update(PhaseDocument)
                .where(PhaseDocument.id == doc_id)
                .values(version=doc.version + 1)
                .returning(PhaseDocument)
            )
            result = await self.session.execute(stmt)
            await self.session.flush()
            return result.scalar_one_or_none()
        return None
