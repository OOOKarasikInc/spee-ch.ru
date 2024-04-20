import datetime
import pathlib
import typing
import uuid

import sqlalchemy
from fastapi import UploadFile
from sqlalchemy import func
from sqlalchemy.dialects.postgresql import insert

from app.config import config
from app.db_schema import (
    boards_table,
    post_media_files_table,
    posts_table,
    thread_media_files_table,
    threads_table,
)
from app.exceptions import BoardNotExists, FileTypeNotSupported, ThreadNotExists
from app.repositories.abstract_repo import Repo


class ThreadRepo(Repo):
    async def get_threads(self, board):
        return await self._get_threads(board)

    async def _get_threads(
        self, board, thread_id: typing.Optional[int] = None, post_limit=3
    ):
        async with self.db_engine.begin() as conn:
            get_board_stmt = sqlalchemy.Select(boards_table).where(
                boards_table.columns["slug"] == board
            )
            if (await conn.execute(get_board_stmt)).rowcount == 0:
                raise BoardNotExists

            get_threads_stmt = sqlalchemy.Select(
                threads_table.columns["text"],
                threads_table.columns["id"],
                func.array(
                    sqlalchemy.Select(
                        func.json_build_object(
                            "file_id",
                            thread_media_files_table.columns["s3_filename"],
                            "filename",
                            thread_media_files_table.columns["filename"],
                        )
                    ).where(
                        thread_media_files_table.columns["thread"]
                        == threads_table.columns["id"]
                    )
                ).label("media"),
                func.array(
                    sqlalchemy.Select(
                        func.json_build_object(
                            "id",
                            posts_table.columns["id"],
                            "voice_message",
                            posts_table.columns["voice_message"],
                            "media",
                            func.array(
                                sqlalchemy.Select(
                                    func.json_build_object(
                                        "file_id",
                                        post_media_files_table.columns["s3_filename"],
                                        "filename",
                                        post_media_files_table.columns["filename"],
                                    )
                                ).where(
                                    post_media_files_table.columns["post"]
                                    == posts_table.columns["id"]
                                )
                            ),
                        )
                    )
                    .where(posts_table.columns["thread"] == threads_table.columns["id"])
                    .order_by("id")
                    .limit(post_limit)
                ).label("posts"),
            )
            if thread_id is not None:
                get_threads_stmt = get_threads_stmt.where(
                    threads_table.columns["id"] == thread_id
                )
            get_threads_stmt = get_threads_stmt.order_by(
                threads_table.columns["last_update"].desc()
            )
            threads = (await conn.execute(get_threads_stmt)).mappings().fetchall()
        return threads

    async def create_thread(self, board, files: typing.List[UploadFile], text):
        mediafiles = []
        for f in files:
            file_extension = pathlib.Path(f.filename).suffix[1:]
            if file_extension not in config.allowed_meida_extenions:
                raise FileTypeNotSupported(
                    f"Типы поддерживаемых медиафайлов: {', '.join(config.allowed_meida_extenions)}"
                )
            mediafiles.append(
                {
                    "s3_filename": f"{str(uuid.uuid4())}.{file_extension}",
                    "filename": f.filename,
                }
            )
            await self.s3_client.upload_fileobj(
                f, "bucket", mediafiles[-1]["s3_filename"]
            )
        async with self.db_engine.begin() as conn:
            get_board_stmt = sqlalchemy.Select(boards_table).where(
                boards_table.columns["slug"] == board
            )
            if (await conn.execute(get_board_stmt)).rowcount == 0:
                raise BoardNotExists

            create_thread_stmt = (
                insert(threads_table)
                .values(
                    text=text,
                    board=board,
                    last_update=datetime.datetime.now(tz=datetime.timezone.utc),
                )
                .returning(threads_table.columns["id"])
            )
            create_thread_result = await conn.execute(create_thread_stmt)
            thread_id = create_thread_result.fetchone()[0]

            create_thread_media_stmt = insert(thread_media_files_table)
            for mediafile in mediafiles:
                mediafile["thread"] = thread_id
            await conn.execute(create_thread_media_stmt, mediafiles)

            await conn.commit()

    async def get_thread(self, board, thread_id):
        threads = await self._get_threads(board, thread_id, 10**6)  # TODO rid off const
        if len(threads) == 0:
            raise ThreadNotExists
        return threads[0]
