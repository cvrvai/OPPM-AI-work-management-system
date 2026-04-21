"""GraphQL router for AI service."""
import logging
from fastapi import APIRouter, Depends
from strawberry.asgi import GraphQL as GraphQLASGI
import strawberry
from strawberry.types import Info
from schemas.graphql_schema import StatusItem, WeeklySummaryResult, SuggestedObjective, SuggestPlanResult
from shared.auth import WorkspaceContext, require_write
from shared.database import get_session
from sqlalchemy.ext.asyncio import AsyncSession
from services.ai_chat_service import weekly_summary, suggest_plan, commit_plan

logger = logging.getLogger(__name__)


@strawberry.type
class Query:
    @strawberry.field
    async def weekly_status_summary(
        self, 
        workspace_id: str, 
        project_id: str,
        info: Info
    ) -> WeeklySummaryResult:
        """Get weekly project status summary."""
        try:
            # Extract session and workspace context from GraphQL context
            context = info.context
            session = context.get("session")
            user_id = context.get("user_id")
            
            if not session or not user_id:
                return WeeklySummaryResult(
                    summary="Error: Missing session context",
                    at_risk=[],
                    on_track=[],
                    blocked=[],
                    suggested_actions=[]
                )
            
            # Call existing AI service function
            result = await weekly_summary(
                session=session,
                project_id=project_id,
                workspace_id=workspace_id,
                user_id=user_id
            )
            
            # Transform result to GraphQL types
            at_risk_items = [
                StatusItem(
                    title=item.get("title", ""),
                    description=item.get("description")
                )
                for item in result.get("at_risk", [])
            ]
            on_track_items = [
                StatusItem(
                    title=item.get("title", ""),
                    description=item.get("description")
                )
                for item in result.get("on_track", [])
            ]
            blocked_items = [
                StatusItem(
                    title=item.get("title", ""),
                    description=item.get("description")
                )
                for item in result.get("blocked", [])
            ]
            suggested_items = [
                StatusItem(
                    title=item.get("title", ""),
                    description=item.get("description")
                )
                for item in result.get("suggested_actions", [])
            ]
            
            return WeeklySummaryResult(
                summary=result.get("summary", ""),
                at_risk=at_risk_items,
                on_track=on_track_items,
                blocked=blocked_items,
                suggested_actions=suggested_items
            )
        except Exception as e:
            logger.error(f"Error in weekly_status_summary: {e}")
            return WeeklySummaryResult(
                summary=f"Error: {str(e)}",
                at_risk=[],
                on_track=[],
                blocked=[],
                suggested_actions=[]
            )

    @strawberry.field
    async def suggest_oppm_plan(
        self, 
        workspace_id: str,
        project_id: str, 
        description: str,
        info: Info
    ) -> SuggestPlanResult:
        """Suggest OPPM plan based on project description."""
        try:
            context = info.context
            session = context.get("session")
            user_id = context.get("user_id")
            
            if not session or not user_id:
                return SuggestPlanResult(
                    suggested_objectives=[],
                    explanation="Error: Missing session context",
                    commit_token=""
                )
            
            # Call existing AI service function
            result = await suggest_plan(
                session=session,
                project_id=project_id,
                workspace_id=workspace_id,
                user_id=user_id,
                description=description
            )
            
            # Transform to GraphQL types
            objectives = [
                SuggestedObjective(
                    title=obj.get("title", ""),
                    suggested_weeks=obj.get("suggested_weeks", [])
                )
                for obj in result.get("suggested_objectives", [])
            ]
            
            return SuggestPlanResult(
                suggested_objectives=objectives,
                explanation=result.get("explanation", ""),
                commit_token=result.get("commit_token", "")
            )
        except Exception as e:
            logger.error(f"Error in suggest_oppm_plan: {e}")
            return SuggestPlanResult(
                suggested_objectives=[],
                explanation=f"Error: {str(e)}",
                commit_token=""
            )


@strawberry.type
class Mutation:
    @strawberry.mutation
    async def commit_oppm_plan(
        self, 
        workspace_id: str,
        project_id: str, 
        commit_token: str,
        info: Info
    ) -> bool:
        """Commit suggested OPPM plan."""
        try:
            context = info.context
            session = context.get("session")
            user_id = context.get("user_id")
            
            if not session or not user_id:
                logger.warning("Missing session context for commit_oppm_plan")
                return False
            
            # Call existing AI service function
            result = await commit_plan(
                session=session,
                project_id=project_id,
                workspace_id=workspace_id,
                user_id=user_id,
                commit_token=commit_token
            )
            
            return result.get("success", False)
        except Exception as e:
            logger.error(f"Error in commit_oppm_plan: {e}")
            return False


schema = strawberry.Schema(query=Query, mutation=Mutation)
graphql_app = GraphQLASGI(schema)

router = APIRouter()

# Mount GraphQL app at the route
router.mount("/workspaces/{workspace_id}/graphql", graphql_app)
