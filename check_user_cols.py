import asyncio
from shared.database import async_session
from sqlalchemy import text

async def main():
    async with async_session() as s:
        r = await s.execute(text("SELECT column_name FROM information_schema.columns WHERE table_name='users'"))
        print([row[0] for row in r.fetchall()])

asyncio.run(main())
