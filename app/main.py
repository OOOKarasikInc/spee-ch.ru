import typing

import pydantic
from fastapi import (
    FastAPI,
    Form,
    HTTPException,
    Response,
    UploadFile,
    responses,
    status,
)

from app import exceptions
from app.repositories import BoardRepo, FileRepo, PostRepo, ThreadRepo
from app.resources import lifespan, resources


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


app = FastAPI(lifespan=lifespan)

thread_repo = ThreadRepo(resources)
post_repo = PostRepo(resources)
board_repo = BoardRepo(resources)
file_repo = FileRepo(resources)

response_404 = {
    404: {"details": "Not found"},
}

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


@app.get("/api/v0/{board}/thread", status_code=200, responses=response_404)
async def get_threads(board: str) -> typing.List[Thread]:
    try:
        threads = await thread_repo.get_threads(board)
    except exceptions.BoardNotExists:
        raise HTTPException(
            status_code=404,
            detail="Not found",
        )
    return threads


@app.get("/api/v0/{board}/thread/{thread_id}", status_code=200, responses=response_404)
async def get_thread(board: str, thread_id: int) -> Thread:
    try:
        thread = await thread_repo.get_thread(board, thread_id)
    except (exceptions.BoardNotExists, exceptions.ThreadNotExists):
        raise HTTPException(
            status_code=404,
            detail="Not found",
        )
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
    media_type = "application/octet-stream"
    if file_id.endswith(".jpeg") or file_id.endswith(".jpg"):
        media_type = "image/jpeg"
    elif file_id.endswith(".mp3"):
        media_type = "audio/mpeg"
    elif file_id.endswith(".png"):
        media_type = "image/x-png"
    try:
        file_data = await file_repo.download_file(file_id)
    except exceptions.FileNotExists:
        raise HTTPException(
            status_code=404,
            detail="Not found",
        )
    return responses.StreamingResponse(
        file_data, media_type=media_type
    )
