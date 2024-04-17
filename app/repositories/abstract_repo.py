from sqlalchemy.ext.asyncio import AsyncEngine


class Repo:
    def __init__(self, resources):
        self.resources = resources

    @property
    def s3_client(self):
        return self.resources["s3"]

    @property
    def db_engine(self) -> AsyncEngine:
        return self.resources["db_engine"]
