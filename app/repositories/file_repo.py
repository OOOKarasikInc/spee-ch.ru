from app.repositories.abstract_repo import Repo


class FileRepo(Repo):
    async def download_file(self, file_id: str):
        s3_file = await self.s3_client.get_object(Bucket="bucket", Key=file_id)
        return s3_file["Body"].iter_chunks()
