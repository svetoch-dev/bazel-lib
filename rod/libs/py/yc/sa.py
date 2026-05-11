from typing import Optional, Tuple
from yandex.cloud.iam.v1.service_account_service_pb2 import (
    CreateServiceAccountRequest,
    ListServiceAccountsRequest,
)
from yandex.cloud.iam.v1.service_account_pb2 import ServiceAccount
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


def _find_sa_by_name(
    sa_service: ServiceAccountServiceStub,
    folder_id: str,
    sa_name: str,
) -> Optional[ServiceAccount]:
    """Return a service account whose name matches ``sa_name``.

    Only the first page is requested because callers use this helper for
    project setup folders where the service-account count is expected to be
    below the requested page size.
    """
    response = sa_service.List(
        ListServiceAccountsRequest(
            folder_id=folder_id,
            page_size=1000,
        )
    )

    return next((x for x in response.service_accounts if x.name == sa_name), None)


def sa_get(
    folder_id: str,
    sa_name: str,
    token: str = None,
    logger: BaseLogger = CliLogger("rod.libs.py.yc.sa.sa_get"),
) -> Optional[ServiceAccount]:
    """Get a Yandex Cloud service account by name from a folder.

    The API client is created from ``sdk_get``, so authentication follows the
    shared YC resolution order: explicit token, ``YC_TOKEN``, then instance
    metadata.

    Args:
        folder_id: Folder ID where the service account should exist.
        sa_name: Name of the service account to return.
        token: Optional IAM token used to authenticate Yandex Cloud API requests.
        logger: Logger used to print status messages.

    Returns:
        The matching service account, or None when it is not found.
    """
    sdk = sdk_get(token)
    sa_service = sdk.client(ServiceAccountServiceStub)
    sa = _find_sa_by_name(sa_service, folder_id, sa_name)

    if sa:
        logger.info(f"service account {sa_name} found")
    else:
        logger.info(f"service account {sa_name} not found")

    return sa


def sa_create(
    folder_id: str,
    sa_name: str,
    token: str = None,
    logger: BaseLogger = CliLogger("rod.libs.py.yc.sa.create_sa"),
) -> ServiceAccount:
    """Create a Yandex Cloud service account if it does not already exist.

    If a service account with the requested name already exists in the folder,
    returns the existing account instead of creating a new one. The API client
    and operation waiter share the SDK returned by ``sdk_get``.

    Args:
        folder_id: Folder ID where the service account should exist.
        sa_name: Name of the service account to create or return.
        token: Optional IAM token used to authenticate Yandex Cloud API requests.
        logger: Logger used to print status messages.

    Returns:
        The existing or newly created service account.
    """
    sdk = sdk_get(token)
    sa_service = sdk.client(ServiceAccountServiceStub)
    sa = _find_sa_by_name(sa_service, folder_id, sa_name)

    if sa:
        logger.info(f"service account {sa_name} already exists")
        return sa

    operation = sa_service.Create(
        CreateServiceAccountRequest(
            folder_id=folder_id,
            name=sa_name,
            description="Description sa needed for accessing tf state",
        )
    )

    result = sdk.wait_operation_and_get_result(
        operation,
        response_type=ServiceAccount,
    )

    logger.info(f"Service Account {sa_name} created successfully")
    return result.response


def sa_create_access_key(
    sa_id: str,
    description: str = "",
    token: str = None,
    logger: BaseLogger = CliLogger("rod.libs.py.yc.sa.create_sa"),
) -> Tuple[AccessKey, str]:
    """Create an AWS-compatible access key for a Yandex Cloud service account.

    The generated secret key is only available in the create response, so
    callers must persist it immediately if they need to use it later. The access
    key client is created from ``sdk_get`` and shares the common YC auth
    resolution order.

    Args:
        sa_id: Service account ID for which the access key should be created.
        description: Description to store on the created access key.
        token: Optional IAM token used to authenticate Yandex Cloud API requests.
        logger: Logger used to print status messages.

    Returns:
        A tuple containing the created access key metadata and generated secret key.
    """
    sdk = sdk_get(token)
    access_key_service = sdk.client(AccessKeyServiceStub)

    result = access_key_service.Create(
        CreateAccessKeyRequest(
            service_account_id=sa_id,
            description=description,
        )
    )

    logger.info(f"Created access key with id={result.access_key.id} for sa_id={sa_id}")

    return result.access_key, result.secret
