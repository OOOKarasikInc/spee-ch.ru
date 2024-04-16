import os


class Config:
    def __init__(self):
        self.db_uri = f"postgresql+asyncpg://postgres:password@{os.getenv('POSTGRES_HOST', 'localhost')}/app_db"
        self.s3_url = os.getenv("S3_URL", "http://localhost:9000")


config = Config()
