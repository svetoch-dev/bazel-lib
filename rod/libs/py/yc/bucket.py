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

import requests

from rod.libs.py.utils.logger import BaseLogger, CliLogger
from rod.libs.py.yc.client import AuthError, YcSettings, sdk_get


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


class YcBucketObject:
    """Manage a single object in a Yandex Object Storage bucket over HTTP."""

    def __init__(
        self,
        bucket: str,
        key: str,
        token: str = None,
        logger: BaseLogger = None,
    ):
        self.logger = logger or CliLogger("rod.libs.py.yc.bucket.BucketObject")

        settings = YcSettings()
        if token:
            self.token = token
        else:
            self.token = settings.token

        if not self.token:
            raise AuthError("no auth methods found")

        self.bucket = bucket
        self.key = key
        self.url = f"https://storage.yandexcloud.net/{self.bucket}/{self.key}"

    @property
    def data(self) -> bytes | None:
        """Return object bytes, or None when the object does not exist."""
        if not self:
            return None

        response = requests.get(
            self.url,
            headers={"Authorization": f"Bearer {self.token}"},
            timeout=30,
        )

        response.raise_for_status()
        return response.content

    def create(self, data: bytes, content_type: str) -> None:
        """Create this object when it does not already exist."""
        if self:
            self.logger.info(f"create: BucketObject {self.url} already exists")
            return

        response = requests.put(
            self.url,
            headers={
                "Authorization": f"Bearer {self.token}",
                "Content-Type": content_type,
            },
            data=data,
            timeout=30,
        )
        response.raise_for_status()
        self.logger.info(f"create: BucketObject {self.url} success!!!")

    def delete(self) -> None:
        """Delete this object when it exists."""
        if not self:
            self.logger.info(f"delete: BucketObject {self.url} does not exists")
            return

        response = requests.delete(
            self.url,
            headers={"Authorization": f"Bearer {self.token}"},
            timeout=30,
        )

        if response.status_code in (200, 202, 204):
            self.logger.info(f"delete: BucketObject {self.url} success!!!")
            return

        response.raise_for_status()
        self.logger.info(f"delete: BucketObject {self.url} success!!!")

    def __bool__(self) -> bool:
        """Return True when the object exists in Yandex Object Storage."""
        response = requests.head(
            self.url,
            headers={"Authorization": f"Bearer {self.token}"},
            timeout=10,
        )

        if response.status_code == 200:
            return True

        if response.status_code == 404:
            return False

        response.raise_for_status()
        return False


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
        conifgs = configs or YcBucketConfigs()
        logger = logger or CliLogger("rod.libs.py.yc.bucket.Bucket")

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
            return bucket_service.Get(
                GetBucketRequest(name=self.name, view=GetBucketRequest.VIEW_FULL)
            )
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
        """Add a lifecycle rule unless an equivalent rule already exists."""
        bucket_service = self.sdk.client(BucketServiceStub)
        # Normalize lifecycle rules before comparing protobuf messages.
        # GetBucketRequest returns rules that apply to all bucket objects with
        # rule.filter explicitly set to an empty value, so set the same empty filter
        # on rules where it is missing.
        if not rule.HasField("filter"):
            rule.filter.SetInParent()

        if rule in self.lifecycle_rules:
            self.logger.info(f"rule is already in bucket {self.name} lifecycle_rules")
            return

        self.lifecycle_rules.append(rule)
        operation = bucket_service.Update(
            UpdateBucketRequest(
                name=self.name,
                update_mask=FieldMask(paths=["lifecycle_rules"]),
                lifecycle_rules=self.lifecycle_rules,
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
            f"granted storage.admin on yc s3 tf state bucket {self.name} to {subject.id}."
        )
