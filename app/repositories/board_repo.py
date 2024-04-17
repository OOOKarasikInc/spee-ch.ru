import sqlalchemy

from app.db_schema import boards_table
from app.repositories.abstract_repo import Repo


class BoardRepo(Repo):
    async def get_boards(self):
        async with self.db_engine.begin() as conn:
            get_boards_stmt = sqlalchemy.Select(boards_table)
            boards = (await conn.execute(get_boards_stmt)).mappings().fetchall()
        return boards
