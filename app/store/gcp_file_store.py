from fastapi import UploadFile
from google.cloud import storage
from google.cloud import storage


class GCPStore:
    def __init__(self):
        self.BUCKET_NAME = "capitalreport_file_storage"

    def upload_stream_to_gcs(self, file: UploadFile):
        # client = storage.Client()
        client = storage.Client.from_service_account_json(
            "/Users/yogenderbutola/.gcp/stable-smithy-270416-42ec379dd1b9.json"
        )
        # client = storage.Client.from_service_account_json("stable-smithy-270416-42ec379dd1b9.json")

        destination_blob_name = file.filename
        bucket = client.bucket(self.BUCKET_NAME)
        blob = bucket.blob(destination_blob_name)
        file.file.seek(0)
        blob.upload_from_file(file.file)
        # return f"https://storage.cloud.google.com/{self.BUCKET_NAME}/{destination_blob_name}"
        # return blob.public_url
        return self.generate_signed_url(blob)

    def generate_signed_url(self, blob):
        presigned_url = blob.generate_signed_url(
            version="v4",
            expiration=3600,  # 1 hour
            method="GET",
            response_disposition="inline"
        )

        return presigned_url

