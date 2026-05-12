import asyncio
from shared.database import async_session
from sqlalchemy import text

async def main():
    async with async_session() as s:
        # Check workspace membership
        r = await s.execute(text(
            "SELECT workspace_id, user_id, role FROM workspace_members WHERE user_id = '2b2571dc-b911-40fd-98c7-1b02a32b150c'"
        ))
        rows = r.fetchall()
        print("Workspace memberships:")
        for row in rows:
            print(f"  workspace_id={row[0]}, user_id={row[1]}, role={row[2]}")
        
        # Check if project exists
        r2 = await s.execute(text(
            "SELECT id, workspace_id, title FROM projects WHERE id = '479ba1f2-4702-48d5-abe1-5b1ec182cf66'"
        ))
        proj = r2.fetchone()
        if proj:
            print(f"Project found: id={proj[0]}, workspace_id={proj[1]}, title={proj[2]}")
        else:
            print("Project not found")

asyncio.run(main())
