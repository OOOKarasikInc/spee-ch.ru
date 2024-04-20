import pydantic_settings

ALLOWED_MEDIA_EXTENTIONS = {
    "jpeg": "image/jpeg",
    "jpg": "image/jpeg",
    "png": "image/x-png",
}
ALLOWED_EXTENTIONS = {**ALLOWED_MEDIA_EXTENTIONS, "mp3": "audio/mpeg"}


class Config(pydantic_settings.BaseSettings):
    postgres_host: str
    postgres_port: str
    postgres_user: str
    postgres_password: str
    postgres_db: str

    s3_access_key_id: str
    s3_url: str
    s3_secret_access_key: str

    @property
    def db_uri(self):
        # TODO: escape special characters
        return f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"

    @property
    def allowed_meida_extenions(self):
        return ALLOWED_MEDIA_EXTENTIONS

    @property
    def allowed_extenions(self):
        return ALLOWED_EXTENTIONS


config = Config()
