"""
Azure Blob Storage Manager
Handles file upload/download from Azure Storage
"""

import logging
import os
import tempfile
from typing import List, Optional
from azure.storage.blob import BlobServiceClient, BlobClient
from azure.identity import DefaultAzureCredential

logger = logging.getLogger(__name__)


class AzureBlobManager:
    """
    Manages Azure Blob Storage operations for test files
    """

    def __init__(self):
        """Initialize Azure Blob Manager"""
        # Use environment variables for configuration
        self.account_url = os.getenv('AZURE_STORAGE_ACCOUNT_URL')
        self.account_key = os.getenv('AZURE_STORAGE_ACCOUNT_KEY')

        if not self.account_url:
            raise ValueError("AZURE_STORAGE_ACCOUNT_URL environment variable not set")

        # Initialize blob service client
        if self.account_key:
            self.blob_service_client = BlobServiceClient(
                account_url=self.account_url,
                credential=self.account_key
            )
        else:
            # Use managed identity
            self.blob_service_client = BlobServiceClient(
                account_url=self.account_url,
                credential=DefaultAzureCredential()
            )

        logger.info(f"Initialized Azure Blob Manager: {self.account_url}")

    def list_files(self, container_name: str, prefix: Optional[str] = None) -> List[str]:
        """
        List all files in a container

        Args:
            container_name: Container name
            prefix: Optional prefix to filter files

        Returns:
            List of blob paths
        """
        logger.info(f"Listing files in container {container_name} (prefix: {prefix})")

        container_client = self.blob_service_client.get_container_client(container_name)

        blobs = container_client.list_blobs(name_starts_with=prefix)

        file_paths = [blob.name for blob in blobs]

        logger.info(f"Found {len(file_paths)} files in {container_name}")

        return file_paths

    def download_file(
        self,
        container_name: str,
        blob_path: str,
        download_to_temp: bool = True,
        local_path: Optional[str] = None
    ) -> str:
        """
        Download file from blob storage

        Args:
            container_name: Container name
            blob_path: Blob path
            download_to_temp: If True, download to temp directory
            local_path: If download_to_temp is False, download to this path

        Returns:
            Local file path
        """
        logger.info(f"Downloading {blob_path} from {container_name}")

        blob_client = self.blob_service_client.get_blob_client(
            container=container_name,
            blob=blob_path
        )

        if download_to_temp:
            # Create temp file
            suffix = os.path.splitext(blob_path)[1]
            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
            local_path = temp_file.name
            temp_file.close()

        # Download blob
        with open(local_path, 'wb') as f:
            download_stream = blob_client.download_blob()
            f.write(download_stream.readall())

        logger.info(f"Downloaded to {local_path}")

        return local_path

    def upload_file(
        self,
        container_name: str,
        local_file_path: str,
        blob_path: str,
        overwrite: bool = True
    ) -> str:
        """
        Upload file to blob storage

        Args:
            container_name: Container name
            local_file_path: Local file path
            blob_path: Destination blob path
            overwrite: Whether to overwrite existing blob

        Returns:
            Blob URL
        """
        logger.info(f"Uploading {local_file_path} to {container_name}/{blob_path}")

        blob_client = self.blob_service_client.get_blob_client(
            container=container_name,
            blob=blob_path
        )

        with open(local_file_path, 'rb') as f:
            blob_client.upload_blob(f, overwrite=overwrite)

        blob_url = blob_client.url
        logger.info(f"Uploaded to {blob_url}")

        return blob_url

    def delete_file(self, container_name: str, blob_path: str):
        """
        Delete file from blob storage

        Args:
            container_name: Container name
            blob_path: Blob path to delete
        """
        logger.info(f"Deleting {blob_path} from {container_name}")

        blob_client = self.blob_service_client.get_blob_client(
            container=container_name,
            blob=blob_path
        )

        blob_client.delete_blob()

        logger.info(f"Deleted {blob_path}")

    def create_container(self, container_name: str):
        """
        Create a container if it doesn't exist

        Args:
            container_name: Container name
        """
        logger.info(f"Creating container {container_name}")

        container_client = self.blob_service_client.get_container_client(container_name)

        try:
            container_client.create_container()
            logger.info(f"Container {container_name} created")
        except Exception as e:
            if 'ContainerAlreadyExists' in str(e):
                logger.info(f"Container {container_name} already exists")
            else:
                raise

    def setup_container_structure(self, container_name: str):
        """
        Setup folder structure for pre-CDR and post-CDR files

        Args:
            container_name: Container name
        """
        logger.info(f"Setting up container structure in {container_name}")

        # Create container if it doesn't exist
        self.create_container(container_name)

        # Blob storage doesn't have real folders, but we can create placeholder blobs
        # The structure will be created automatically when files are uploaded

        logger.info(f"Container structure ready")
