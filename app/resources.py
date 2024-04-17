from contextlib import asynccontextmanager

import aioboto3
import aioboto3.s3
import botocore
import botocore.exceptions
from fastapi import FastAPI
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import create_async_engine

from app.config import config
from app.db_schema import boards_table

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
        "aws_access_key_id": config.s3_access_key_id,
        "aws_secret_access_key": config.s3_secret_access_key,
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
