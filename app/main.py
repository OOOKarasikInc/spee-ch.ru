import aioboto3.s3
import botocore.exceptions
from fastapi import FastAPI, UploadFile, Form, status, Response, responses
from sqlalchemy.ext.asyncio import create_async_engine, AsyncEngine
from app.config import config
from app.db_schema import (
    boards_table,
    threads_table,
    posts_table,
    thread_media_files_table,
    post_media_files_table,
)
import pydantic
import pathlib
import typing
import aioboto3
from contextlib import asynccontextmanager
import uuid
import botocore
import sqlalchemy
from sqlalchemy import func
from sqlalchemy.dialects.postgresql import insert
import datetime


class ThreadMedia(pydantic.BaseModel):
    filename: str
    file_id: str


class Board(pydantic.BaseModel):
    slug: str
    name: str


class Post(pydantic.BaseModel):
    id: int
    voice_message: str
    media: typing.List[ThreadMedia]


class Thread(pydantic.BaseModel):
    id: int
    text: str
    media: typing.List[ThreadMedia]
    posts: typing.List[Post]


resources = {
    "db_engine": create_async_engine(config.db_uri),
}


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with resources["db_engine"].begin() as conn:
        create_b_board_stmt = (
            insert(boards_table)
            .values(slug="b", name="Бред")
            .on_conflict_do_nothing(index_elements=["slug"])
        )
        await conn.execute(create_b_board_stmt)

    boto_session = aioboto3.Session()
    s3_settings = {
        "aws_access_key_id": "minio",
        "aws_secret_access_key": "minio123",
        "endpoint_url": config.s3_url,
    }
    async with boto_session.client(service_name="s3", **s3_settings) as s3:
        try:
            await s3.create_bucket(Bucket="bucket")
        except botocore.exceptions.ClientError as e:
            if e.response["Error"]["Code"] != "BucketAlreadyOwnedByYou":
                raise e
        resources["s3"] = s3
        yield


app = FastAPI(lifespan=lifespan)


class Repo:
    def __init__(self, resources):
        self.resources = resources

    @property
    def s3_client(self):
        return self.resources["s3"]

    @property
    def db_engine(self) -> AsyncEngine:
        return self.resources["db_engine"]


class BoardNotExists(Exception):
    pass


class ThreadNotExists(Exception):
    pass


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
        threads = await thread_repo._get_threads(
            board, thread_id, 10**6
        )  # TODO rid off const
        if len(threads) == 0:
            raise ThreadNotExists
        return threads[0]


class PostRepo(Repo):
    async def create_post(
        self, thread_id, files: typing.List[UploadFile], voice_message: UploadFile
    ):
        voice = str(uuid.uuid4()) + '.mp3'
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


class BoardRepo(Repo):
    async def get_boards(self):
        async with self.db_engine.begin() as conn:
            get_boards_stmt = sqlalchemy.Select(boards_table)
            boards = (await conn.execute(get_boards_stmt)).mappings().fetchall()
        return boards

class FileRepo(Repo):
    async def download_file(self, file_id: str):
        s3_file = await self.s3_client.get_object(Bucket="bucket", Key=file_id)
        return s3_file['Body'].iter_chunks()


thread_repo = ThreadRepo(resources)
post_repo = PostRepo(resources)
board_repo = BoardRepo(resources)
file_repo = FileRepo(resources)


@app.get("/api/v0/board", status_code=200)
async def get_boards() -> typing.List[Board]:
    return await board_repo.get_boards()


@app.post("/api/v0/{board}/thread", status_code=201)
async def create_thread(
    board: str, files: typing.List[UploadFile], text: typing.Annotated[str, Form(...)]
):
    # TODO: filesize, file types
    await thread_repo.create_thread(board, files, text)
    return Response(status_code=status.HTTP_201_CREATED)


@app.get("/api/v0/{board}/thread", status_code=200)
async def get_threads(board: str) -> typing.List[Thread]:
    # TODO thread 404
    return await thread_repo.get_threads(board)


@app.get("/api/v0/{board}/thread/{thread_id}", status_code=200)
async def get_thread(board: str, thread_id: int) -> Thread:
    # TODO: board 404, thread 404
    thread = await thread_repo.get_thread(board, thread_id)
    return thread


@app.post("/api/v0/{thread_id}/post", status_code=201)
async def create_post(
    thread_id: int, files: typing.List[UploadFile], voice: UploadFile
):
    # TODO: filesize, file types, optional files
    await post_repo.create_post(thread_id, files, voice)
    return Response(status_code=status.HTTP_201_CREATED)

@app.post("/api/v0/file/{file_id}", status_code=200)
async def downlad_file(file_id: str):
    # TODO fix media type
    # TODO 404
    media_type="application/octet-stream"
    if file_id.endswith(".jpeg") or file_id.endswith(".jpg"):
        media_type="image/jpeg"
    elif file_id.endswith(".mp3"):
        media_type="audio/mpeg"
    elif file_id.endswith(".png"):
        media_type="image/x-png"
    await file_repo.download_file(file_id)
    return responses.StreamingResponse(await file_repo.download_file(file_id), media_type=media_type)