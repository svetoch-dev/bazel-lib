import json
import uuid

from google.cloud import storage
from google.api_core.exceptions import NotFound
from rod.libs.py.utils.logger import CliLogger, BaseLogger
from rod.libs.py.yc.bucket import YcBucketConfigs, YcBucket, YcBucketObject

from yandex.cloud.storage.v1.bucket_pb2 import VERSIONING_ENABLED, LifecycleRule
from google.protobuf.wrappers_pb2 import Int64Value, StringValue
from yandex.cloud.access.access_pb2 import Subject


def empty_state_file() -> bytes:
    """Return a minimal empty Terraform state file payload."""
    state = {
        "version": 4,
        "terraform_version": "1.14.4",
        "serial": 1,
        "lineage": str(uuid.uuid4()),
        "outputs": {},
        "resources": [],
        "check_results": None,
    }
    return json.dumps(state, indent=2).encode("utf-8")


def create_gcs_tf_state(
    project_id: str,
    bucket_name: str,
    location: str,
    logger: BaseLogger = None,
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
    logger = logger or CliLogger("rod.libs.py.tf.state.create_gcs_tf_state")

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


def create_yc_s3_tf_state(
    folder_id: str,
    bucket_name: str,
    sa_id: str,
    secrets_state: str,
    logger: BaseLogger = None,
) -> bool:
    """Ensure that a Yandex Object Storage bucket for Terraform state exists.

    The bucket is created with versioning enabled, receives a lifecycle rule
    that removes old noncurrent object versions when the rule is not already
    present, and grants storage.admin to the service account that will read and
    write Terraform state. It also writes an empty secrets state file so that
    the secrets backend exists before secret import runs.

    Args:
        folder_id: Yandex Cloud folder ID where the bucket should exist.
        bucket_name: Name of the S3-compatible bucket used for Terraform state.
        sa_id: Service account ID to grant storage.admin on the bucket.
        secrets_state: Object key for the empty secrets Terraform state file.
        logger: Logger used to print status messages.

    Returns:
        True if the bucket exists or is created successfully and the service
        account admin binding and empty secrets state object are applied. False
        if bucket setup, lifecycle configuration, access binding update, or
        secrets state object creation fails.
    """
    logger = logger or CliLogger("rod.libs.py.tf.state.create_yc_s3_tf_state")

    configs = YcBucketConfigs()
    configs.versioning = VERSIONING_ENABLED

    try:
        bucket = YcBucket(folder_id, bucket_name, configs=configs, logger=logger)

        noncurrent_rule = LifecycleRule(
            id=StringValue(value="delete-old-noncurrent-versions"),
            enabled=True,
            noncurrent_expiration=LifecycleRule.NoncurrentExpiration(
                noncurrent_days=Int64Value(value=200),
            ),
        )

        bucket.add_lifecycle_rule(noncurrent_rule)
    except Exception as e:
        logger.error(f"yc s3 tf state bucket {bucket_name} creation error: {e}")
        return False

    try:
        subject = Subject(
            id=sa_id,
            type="serviceAccount",
        )
        bucket.add_admin(subject)

    except Exception as e:
        logger.error(f"yc s3 tf state bucket {bucket_name} access binding error: {e}")
        return False

    try:
        bucket_object = YcBucketObject(bucket_name, secrets_state)
        bucket_object.create(empty_state_file(), "application/json")
    except Exception as e:
        logger.error(
            f"yc s3 tf state bucket {bucket_name} could not create empty state file: {e}"
        )
        return False

    return True
