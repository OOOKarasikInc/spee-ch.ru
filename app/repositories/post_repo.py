import datetime
import pathlib
import typing
import uuid

import sqlalchemy
from fastapi import UploadFile
from sqlalchemy.dialects.postgresql import insert

from app.db_schema import post_media_files_table, posts_table, threads_table
from app.exceptions import ThreadNotExists
from app.repositories.abstract_repo import Repo


class PostRepo(Repo):
    async def create_post(
        self, thread_id, files: typing.List[UploadFile], voice_message: UploadFile
    ):
        voice = str(uuid.uuid4()) + ".mp3"
        await self.s3_client.upload_fileobj(voice_message, "bucket", voice)

        mediafiles = []
        for f in files:
            mediafiles.append(
                {
                    "s3_filename": str(uuid.uuid4()) + pathlib.Path(f.filename).suffix,
                    "filename": f.filename,
                }
            )
            await self.s3_client.upload_fileobj(
                f, "bucket", mediafiles[-1]["s3_filename"]
            )

        async with self.db_engine.begin() as conn:
            # TODO replace to try block?
            get_thread_stmt = sqlalchemy.Select(threads_table).where(
                threads_table.columns["id"] == thread_id
            )
            if (await conn.execute(get_thread_stmt)).rowcount == 0:
                raise ThreadNotExists

            create_post_stmt = (
                insert(posts_table)
                .values(thread=thread_id, voice_message=voice)
                .returning(posts_table.columns["id"])
            )
            create_post_stmt = await conn.execute(create_post_stmt)
            post_id = create_post_stmt.fetchone()[0]

            create_post_media_stmt = insert(post_media_files_table)
            for mediafile in mediafiles:
                mediafile["post"] = post_id
            await conn.execute(create_post_media_stmt, mediafiles)

            update_thread_stmt = sqlalchemy.Update(threads_table).where(
                threads_table.columns["id"] == thread_id
            )
            await conn.execute(
                update_thread_stmt,
                {"last_update": datetime.datetime.now(tz=datetime.timezone.utc)},
            )

            await conn.commit()
