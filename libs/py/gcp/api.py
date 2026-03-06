from google.cloud.service_usage_v1 import (
    ServiceUsageClient,
    GetServiceRequest,
    types,
    EnableServiceRequest,
)
from google.api_core.exceptions import AlreadyExists, PermissionDenied
from libs.py.utils.logger import BaseLogger, CliLogger


def enable_apis(
    project_id: str,
    apis: list[str],
    logger: BaseLogger = CliLogger("gcp.api.enable_apis"),
) -> bool:
    """
    Enables specific Google APIs for the project.

    Args:
        project_id: The name of the project that where apis need to be enabled
        apis: list of strings representing google apis
    """
    client = ServiceUsageClient()
    enabled_apis = {}

    for api in apis:
        get_service_request = GetServiceRequest(
            name=f"projects/{project_id}/services/{api}"
        )
        enable_service_request = EnableServiceRequest(
            name=f"projects/{project_id}/services/{api}"
        )

        try:
            response = client.get_service(request=get_service_request)

            if response.state == types.State.ENABLED:
                enabled_apis[api] = True
                logger.info(f"{api} API is already enabled for project {project_id}.")
                continue

            response = client.enable_service(request=enable_service_request)
            result = response.result()
            logger.info(
                f"{api} API has been successfully enabled for project {project_id}."
            )
            enabled_apis[api] = True
        except AlreadyExists:
            logger.info(
                f"The {api} API is already in the process of being enabled for project {project_id}."
            )
            enabled_apis[api] = False
        except PermissionDenied:
            logger.error(
                f"Permission denied on project {project_id}. Ensure the service account has the 'Service Usage Admin' role."
            )
            enabled_apis[api] = False
        except Exception as e:
            logger.error(f"An error occurred while enabling API {api}: {e}")
            enabled_apis[api] = False

    return False not in enabled_apis.values()
