import grpc
from dataclasses import dataclass, field
from google.protobuf.field_mask_pb2 import FieldMask
from google.protobuf.wrappers_pb2 import BoolValue
from yandex.cloud.storage.v1.bucket_pb2 import (
    VERSIONING_DISABLED,
    AnonymousAccessFlags,
    Bucket,
    LifecycleRule,
    Versioning,
)
from yandex.cloud.access.access_pb2 import (
    ADD,
    AccessBinding,
    AccessBindingDelta,
    Subject,
    UpdateAccessBindingsRequest,
)
from yandex.cloud.storage.v1.bucket_service_pb2 import (
    CreateBucketRequest,
    GetBucketRequest,
    UpdateBucketRequest,
)
from yandex.cloud.storage.v1.bucket_service_pb2_grpc import BucketServiceStub

from rod.libs.py.utils.logger import BaseLogger, CliLogger
from rod.libs.py.yc.client import sdk_get


@dataclass
class YcBucketConfigs:
    """Configuration values used when creating a Yandex Object Storage bucket."""

    default_storage_class: str = "STANDARD"
    anonymous_access_flags: AnonymousAccessFlags = field(
        default_factory=lambda: AnonymousAccessFlags(
            read=BoolValue(value=False),
            list=BoolValue(value=False),
            config_read=BoolValue(value=False),
        )
    )
    versioning: Versioning = VERSIONING_DISABLED


class YcBucket:
    """Manage a Yandex Object Storage bucket.

    The constructor gets the bucket by name when it exists. If Yandex Cloud
    returns NOT_FOUND, it creates the bucket in the configured folder. Bucket
    protobuf fields are exposed through attribute delegation.
    """

    def __init__(
        self,
        folder_id: str,
        name: str,
        create_if_missing: bool = True,
        token: str = None,
        configs: YcBucketConfigs = None,
        logger: BaseLogger = None,
    ):
        if not configs:
            configs = YcBucketConfigs()
        if not logger:
            logger = CliLogger("rod.libs.py.yc.bucket.Bucket")

        self.sdk = sdk_get(token)
        self.folder_id = folder_id
        self.name = name
        self.logger = logger

        self._bucket = self._get()
        if self._bucket:
            self.logger.info(f"bucket {self.name} found")
        elif create_if_missing:
            self.logger.info(f"bucket {self.name} not found creating")
            self._bucket = self._create(configs)
        else:
            self.logger.info(f"bucket {self.name} not found")

    def __getattr__(self, name):
        return getattr(self._bucket, name)

    def __bool__(self):
        return self._bucket is not None

    def _get(self) -> Bucket | None:
        """Return the bucket named by this instance, or None when missing."""
        bucket_service = self.sdk.client(BucketServiceStub)

        try:
            return bucket_service.Get(GetBucketRequest(name=self.name))
        except grpc.RpcError as e:
            if e.code() == grpc.StatusCode.NOT_FOUND:
                return None
            raise

    def _create(self, configs: YcBucketConfigs) -> Bucket:
        """Create the configured bucket and return the created bucket."""
        bucket_service = self.sdk.client(BucketServiceStub)
        operation = bucket_service.Create(
            CreateBucketRequest(
                name=self.name,
                folder_id=self.folder_id,
                default_storage_class=configs.default_storage_class,
                anonymous_access_flags=configs.anonymous_access_flags,
                versioning=configs.versioning,
            )
        )

        result = self.sdk.wait_operation_and_get_result(
            operation,
            response_type=Bucket,
        )
        self.logger.info(f"bucket {self.name} created successfully")
        return result.response

    def add_lifecycle_rule(self, rule: LifecycleRule) -> None:
        """Replace bucket lifecycle rules with the provided rule."""
        bucket_service = self.sdk.client(BucketServiceStub)
        operation = bucket_service.Update(
            UpdateBucketRequest(
                name=self.name,
                update_mask=FieldMask(paths=["lifecycle_rules"]),
                lifecycle_rules=[rule],
            )
        )
        self.sdk.wait_operation_and_get_result(operation, response_type=Bucket)
        self.logger.info(f"bucket {self.name} rule updated successfully")

    def add_admin(self, subject: Subject) -> None:
        """Grant storage.admin on this bucket to the given subject."""
        bucket_service = self.sdk.client(BucketServiceStub)
        operation = bucket_service.UpdateAccessBindings(
            UpdateAccessBindingsRequest(
                resource_id=self.resource_id,
                access_binding_deltas=[
                    AccessBindingDelta(
                        action=ADD,
                        access_binding=AccessBinding(
                            role_id="storage.admin",
                            subject=subject,
                        ),
                    )
                ],
            )
        )
        self.sdk.wait_operation_and_get_result(operation)
        self.logger.info(
            f"granted storage.admin on yc s3 tf state bucket {self.name} "
            f"to {subject}."
        )
