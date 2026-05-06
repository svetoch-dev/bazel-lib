from typing import Tuple
from yandexcloud import SDK
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
from yandex.cloud.iam.v1.iam_token_service_pb2 import CreateIamTokenRequest
from yandex.cloud.iam.v1.iam_token_service_pb2_grpc import IamTokenServiceStub

from rod.libs.py.utils.logger import CliLogger, BaseLogger


def sa_create(
    folder_id: str,
    token: str,
    sa_name: str,
    logger: BaseLogger = CliLogger("rod.libs.py.yc.sa.create_sa"),
) -> ServiceAccount:
    """
    Create a Yandex Cloud service account if it does not already exist.

    If a service account with the requested name already exists in the folder,
    returns the existing account instead of creating a new one.

    Args:
        folder_id: Folder ID where the service account should exist.
        token: IAM token used to authenticate Yandex Cloud API requests.
        sa_name: Name of the service account to create or return.
        logger: Logger used to print status messages.

    Returns:
        The existing or newly created service account.
    """
    sdk = SDK(iam_token=token)
    sa_service = sdk.client(ServiceAccountServiceStub)
    response = sa_service.List(
        ListServiceAccountsRequest(
            folder_id=folder_id,
            page_size=1000,
        )
    )
    sa = next((x for x in response.service_accounts if x.name == sa_name), None)

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
    token: str,
    description: str,
    logger: BaseLogger = CliLogger("rod.libs.py.yc.sa.create_sa"),
) -> Tuple[AccessKey, str]:
    """
    Create an AWS-compatible access key for a Yandex Cloud service account.

    The generated secret key is only available in the create response, so
    callers must persist it immediately if they need to use it later.

    Args:
        sa_id: Service account ID for which the access key should be created.
        token: IAM token used to authenticate Yandex Cloud API requests.
        description: Description to store on the created access key.
        logger: Logger used to print status messages.

    Returns:
        A tuple containing the created access key metadata and generated secret key.
    """
    sdk = SDK(iam_token=token)

    access_key_service = sdk.client(AccessKeyServiceStub)

    result = access_key_service.Create(
        CreateAccessKeyRequest(
            service_account_id=sa_id,
            description=description,
        )
    )

    logger.info(f"Created access key with id={result.access_key.id} for sa_id={sa_id}")

    return result.access_key, result.secret
