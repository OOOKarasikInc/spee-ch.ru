from app.repositories.abstract_repo import Repo
from botocore.exceptions import ClientError
from app.exceptions import FileNotExists


class FileRepo(Repo):
    async def download_file(self, file_id: str):
        try:
            s3_file = await self.s3_client.get_object(Bucket="bucket", Key=file_id)
        except ClientError as ex:
            if ex.response["Error"]["Code"] == "NoSuchKey":
                raise FileNotExists
            else:
                raise
        return s3_file["Body"].iter_chunks()
