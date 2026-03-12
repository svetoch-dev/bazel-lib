from google.cloud import storage
from google.api_core.exceptions import NotFound
from libs.py.utils.logger import CliLogger, BaseLogger


def create_gcs_tf_state(
    project_id: str,
    bucket_name: str,
    location: str,
    logger: BaseLogger = CliLogger("libs.py.tf.state.create_gcs_tf_state"),
) -> bool:
    """
    Ensure that a Google Cloud Storage bucket for Terraform state exists.

    The function checks whether the given bucket already exists in the specified
    Google Cloud project. If it does not exist, it creates the bucket and applies
    settings suitable for Terraform state storage, including versioning, public
    access prevention, and a lifecycle rule for old object versions.

    Args:
        project_id: Google Cloud project ID where the bucket should exist.
        bucket_name: Name of the GCS bucket used for Terraform state.
        location: GCS location or region for the bucket.

    Returns:
        True if the bucket already exists or is created successfully.
        False if bucket creation fails due to an unexpected error.
    """
    client = storage.Client(project=project_id)

    try:
        bucket = client.get_bucket(bucket_name)
        logger.info(f"gcs tf state bucket {bucket_name} already exists.")
        return True
    except NotFound:
        bucket = client.bucket(bucket_name)
        bucket.location = location
        bucket.storage_class = "STANDARD"
        bucket.public_access_prevention = "enforced"
        bucket.iam_configuration.uniform_bucket_level_access_enabled = False
        bucket.versioning_enabled = True
        bucket.lifecycle_rules = [
            {
                "action": {"type": "Delete"},
                "condition": {
                    "isLive": False,  # Targets noncurrent versions
                    "numNewerVersions": 200,  # Deletes versions if there is 200 newer versions
                },
            }
        ]
        bucket = client.create_bucket(bucket)
        logger.info(f"gcs tf state bucket {bucket_name} created successfully.")
        return True
    except Exception as e:
        logger.error(f"gcs tf state bucket {bucket_name} creation error: {e}")
        return False


def create_yc_s3_tf_state() -> bool:
    return False
