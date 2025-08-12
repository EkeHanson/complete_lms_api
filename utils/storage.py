import os
import uuid
import logging
from django.conf import settings
from supabase import create_client
import boto3
from azure.storage.blob import BlobServiceClient
from django.core.files.uploadedfile import InMemoryUploadedFile, TemporaryUploadedFile

logger = logging.getLogger(__name__)

class StorageService:
    def upload_file(self, file_obj, file_name, content_type):
        raise NotImplementedError("Subclasses must implement upload_file")

    def get_public_url(self, file_name):
        raise NotImplementedError("Subclasses must implement get_public_url")

    def delete_file(self, file_name):
        raise NotImplementedError("Subclasses must implement delete_file")

class LocalStorageService:
    def upload_file(self, file_obj, file_name, content_type=None):
        media_root = "media"
        os.makedirs(media_root, exist_ok=True)
        file_path = os.path.join(media_root, file_name)
        with open(file_path, "wb") as f:
            f.write(file_obj.read())
        return True

    def get_public_url(self, file_name):
        return f"/media/{file_name}"

class SupabaseStorageService(StorageService):
    def __init__(self):
        self.client = create_client(settings.SUPABASE_URL, settings.SUPABASE_KEY)
        self.bucket = settings.SUPABASE_BUCKET

    def upload_file(self, file_obj, file_name, content_type):
        try:
            # Handle Django's InMemoryUploadedFile or TemporaryUploadedFile
            if isinstance(file_obj, (InMemoryUploadedFile, TemporaryUploadedFile)):
                file_data = file_obj.read()  # Read file content as bytes
            else:
                file_data = file_obj  # Assume file_obj is already in a compatible format (e.g., bytes)

            res = self.client.storage.from_(self.bucket).upload(
                path=file_name,
                file=file_data,
                file_options={"content-type": content_type, "cache-control": "3600", "upsert": "true"}
            )
            # Check if upload was successful by inspecting response for 'path'
            if hasattr(res, 'path') and res.path:
                logger.info(f"Successfully uploaded {file_name} to Supabase")
                return True
            else:
                # Handle error case
                error_msg = getattr(res, 'error', str(res)) if hasattr(res, 'error') else str(res)
                logger.error(f"Failed to upload {file_name} to Supabase: {error_msg}")
                return False
        except Exception as e:
            logger.error(f"Error uploading to Supabase: {str(e)}", exc_info=True)
            raise

    def get_public_url(self, file_name):
        try:
            url = self.client.storage.from_(self.bucket).get_public_url(file_name)
            logger.debug(f"Generated public URL for {file_name}: {url}")
            return url
        except Exception as e:
            logger.error(f"Error generating public URL in Supabase: {str(e)}")
            raise

    def delete_file(self, file_name):
        try:
            res = self.client.storage.from_(self.bucket).remove([file_name])
            logger.info(f"Successfully deleted {file_name} from Supabase")
            return True
        except Exception as e:
            logger.error(f"Error deleting {file_name} from Supabase: {str(e)}")
            return False

class S3StorageService(StorageService):
    def __init__(self):
        self.client = boto3.client(
            's3',
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            region_name=settings.AWS_REGION
        )
        self.bucket = settings.AWS_S3_BUCKET

    def upload_file(self, file_obj, file_name, content_type):
        try:
            self.client.upload_fileobj(
                file_obj,  # boto3 handles InMemoryUploadedFile directly
                self.bucket,
                file_name,
                ExtraArgs={'ContentType': content_type, 'ACL': 'public-read'}
            )
            logger.info(f"Successfully uploaded {file_name} to S3")
            return True
        except Exception as e:
            logger.error(f"Error uploading to S3: {str(e)}", exc_info=True)
            raise

    def get_public_url(self, file_name):
        try:
            url = f"https://{self.bucket}.s3.{settings.AWS_REGION}.amazonaws.com/{file_name}"
            logger.debug(f"Generated public URL for {file_name}: {url}")
            return url
        except Exception as e:
            logger.error(f"Error generating public URL in S3: {str(e)}")
            raise

    def delete_file(self, file_name):
        try:
            self.client.delete_object(Bucket=self.bucket, Key=file_name)
            logger.info(f"Successfully deleted {file_name} from S3")
            return True
        except Exception as e:
            logger.error(f"Error deleting {file_name} from S3: {str(e)}")
            return False

class AzureStorageService(StorageService):
    def __init__(self):
        self.client = BlobServiceClient.from_connection_string(settings.AZURE_CONNECTION_STRING)
        self.container = settings.AZURE_CONTAINER

    def upload_file(self, file_obj, file_name, content_type):
        try:
            container_client = self.client.get_container_client(self.container)
            blob_client = container_client.get_blob_client(file_name)
            blob_client.upload_blob(file_obj, blob_type="BlockBlob", content_settings={'content_type': content_type})
            logger.info(f"Successfully uploaded {file_name} to Azure")
            return True
        except Exception as e:
            logger.error(f"Error uploading to Azure: {str(e)}", exc_info=True)
            raise

    def get_public_url(self, file_name):
        try:
            url = f"https://{settings.AZURE_ACCOUNT_NAME}.blob.core.windows.net/{self.container}/{file_name}"
            logger.debug(f"Generated public URL for {file_name}: {url}")
            return url
        except Exception as e:
            logger.error(f"Error generating public URL in Azure: {str(e)}")
            raise

    def delete_file(self, file_name):
        try:
            container_client = self.client.get_container_client(self.container)
            blob_client = container_client.get_blob_client(file_name)
            blob_client.delete_blob()
            logger.info(f"Successfully deleted {file_name} from Azure")
            return True
        except Exception as e:
            logger.error(f"Error deleting {file_name} from Azure: {str(e)}")
            return False

def get_storage_service():
    storage_type = getattr(settings, 'STORAGE_TYPE', 'supabase').lower()
    if storage_type == 'supabase':
        return SupabaseStorageService()
    elif storage_type == 's3':
        return S3StorageService()
    elif storage_type == 'azure':
        return AzureStorageService()
    else:
        return LocalStorageService()
