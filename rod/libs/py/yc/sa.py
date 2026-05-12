from typing import Optional, Tuple
from yandex.cloud.iam.v1.service_account_service_pb2 import (
    CreateServiceAccountRequest,
    ListServiceAccountsRequest,
)
from yandex.cloud.iam.v1.service_account_pb2 import ServiceAccount as YcServiceAccount
from yandex.cloud.iam.v1.service_account_service_pb2_grpc import (
    ServiceAccountServiceStub,
)
from yandex.cloud.iam.v1.awscompatibility.access_key_pb2 import AccessKey
from yandex.cloud.iam.v1.awscompatibility.access_key_service_pb2 import (
    CreateAccessKeyRequest,
)
from yandex.cloud.iam.v1.awscompatibility.access_key_service_pb2_grpc import (
    AccessKeyServiceStub,
)
from rod.libs.py.utils.logger import CliLogger, BaseLogger
from rod.libs.py.yc.client import sdk_get


class YcServiceAccount:
    """Manage a Yandex Cloud service account in a folder.

    By default, the account is created when it is missing. Set
    ``create_if_missing`` to False when the caller only needs to look up an
    existing account.
    """

    def __init__(
        self,
        folder_id: str,
        name: str,
        token: str = None,
        logger: BaseLogger = None,
        create_if_missing: bool = True,
    ):
        if not logger:
            logger = CliLogger("rod.libs.py.yc.sa.ServiceAccount")

        self.sdk = sdk_get(token)
        self.folder_id = folder_id
        self.name = name
        self.logger = logger

        self._sa = self._find()
        if self._sa:
            self.logger.info(f"service account {self.name} found")
        elif create_if_missing:
            self.logger.info(f"service account {self.name} not found creating")
            self._sa = self.create()
        else:
            self.logger.info(f"service account {self.name} not found")

    def __getattr__(self, name):
        return getattr(self._sa, name)

    def __bool__(self):
        return self._sa is not None

    def _find(self) -> Optional[YcServiceAccount]:
        """Return the service account whose name matches this instance.

        Only the first page is requested because callers use this helper for
        project setup folders where the service-account count is expected to be
        below the requested page size.
        """
        sa_service = self.sdk.client(ServiceAccountServiceStub)
        response = sa_service.List(
            ListServiceAccountsRequest(
                folder_id=self.folder_id,
                page_size=1000,
            )
        )

        return next((x for x in response.service_accounts if x.name == self.name), None)

    def create(self) -> YcServiceAccount:
        """Create the configured Yandex Cloud service account.

        Returns:
            The newly created service account returned by Yandex Cloud.
        """
        sa_service = self.sdk.client(ServiceAccountServiceStub)

        operation = sa_service.Create(
            CreateServiceAccountRequest(
                folder_id=self.folder_id,
                name=self.name,
                description="Description sa needed for accessing tf state",
            )
        )

        result = self.sdk.wait_operation_and_get_result(
            operation,
            response_type=YcServiceAccount,
        )

        self.logger.info(f"Service Account {self.name} created successfully")
        return result.response

    def create_access_key(
        self,
        description: str = "",
    ) -> Tuple[AccessKey, str]:
        """Create an AWS-compatible access key for this service account.

        The generated secret key is only available in the create response, so
        callers must persist it immediately if they need to use it later.

        Args:
            description: Description to store on the created access key.

        Returns:
            A tuple containing the created access key metadata and generated secret key.
        """
        access_key_service = self.sdk.client(AccessKeyServiceStub)

        result = access_key_service.Create(
            CreateAccessKeyRequest(
                service_account_id=self.id,
                description=description,
            )
        )

        self.logger.info(
            f"Created access key with id={result.access_key.id} for sa_id={self.id}"
        )

        return result.access_key, result.secret
