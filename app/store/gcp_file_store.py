from fastapi import UploadFile
from google.cloud import storage
import os
import logging

logging.basicConfig(
    level=logging.INFO,  # Only output messages at INFO level and above
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)


class GCPStore:
    def __init__(self):
        self.BUCKET_NAME = "capitalreport_file_storage"
        self.logger = logging.getLogger(__name__)

    def upload_stream_to_gcs(self, file: UploadFile):
        current_dir = os.path.dirname(os.path.abspath(__file__))
        json_file_path = os.path.join(current_dir, "credentials.json")
        client = storage.Client.from_service_account_json(json_file_path)
        destination_blob_name = file.filename
        self.logger.info(f"Blob name: {destination_blob_name}")
        bucket = client.bucket(self.BUCKET_NAME)
        self.logger.info(f"Bucket name: {bucket}")
        blob = bucket.blob(destination_blob_name)
        file.file.seek(0)
        self.logger.info("Uploading the file to GCP Storage.")
        blob.upload_from_file(file.file)
        self.logger.info("Uploading complete.")
        return self.generate_signed_url(blob)

    def generate_signed_url(self, blob):
        presigned_url = blob.generate_signed_url(
            version="v4",
            expiration=3600,  # 1 hour
            method="GET",
            response_disposition="inline"
        )
        self.logger.info("Created pre-signed url.")
        return presigned_url
