from yandexcloud import SDK
from yandex.cloud.iam.v1.service_account_service_pb2 import (
    CreateServiceAccountRequest,
    ListServiceAccountsRequest,
)
from yandex.cloud.iam.v1.service_account_pb2 import ServiceAccount
from yandex.cloud.iam.v1.service_account_service_pb2_grpc import (
    ServiceAccountServiceStub,
)
from rod.libs.py.utils.logger import CliLogger, BaseLogger


def sa_create(
    folder_id: str,
    token: str,
    sa_name: str,
    logger: BaseLogger = CliLogger("rod.libs.py.yc.sa.create_sa"),
) -> ServiceAccount:
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
