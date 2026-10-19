from google.api_core.exceptions import Forbidden, PermissionDenied

from rod.libs.py.cloud.exceptions import CloudPermissionsDenied
from rod.libs.py.tf.tfvars import Env, CloudTypeEnum
from rod.libs.py.gcp.network import list_nat_gws


def nat_gw_ips(env: Env) -> list[str]:
    """
    Return NAT gateway IP addresses for an environment's cloud and region.

    GCP addresses are collected from all NAT gateways in the project and region.
    Returns the placeholder address "0.0.0.0" for Yandex Cloud or when GCP has
    no configured static NAT addresses.

    Args:
        env: Environment containing the cloud project and region to query.

    Returns:
        NAT gateway IP addresses, or a list containing the placeholder address.

    Raises:
        CloudPermissionsDenied: The caller cannot list gateways or read addresses.
        NotImplementedError: The environment uses an unsupported cloud provider.
    """
    if env.cloud.name == CloudTypeEnum.yc:
        # We havent static ip nat gws yet
        # so we allow all for now
        return ["0.0.0.0"]
    elif env.cloud.name == CloudTypeEnum.gcp:
        ips = []
        try:
            gws = list_nat_gws(env.cloud.id, env.cloud.location.region)
        except (Forbidden, PermissionDenied) as error:
            raise CloudPermissionsDenied(
                f"Cannot get NAT gateway IPs in project {env.cloud.id} "
                f"and region {env.cloud.location.region}: {error}"
            ) from error
        for gw in gws:
            ips += gw.nat_ips
        return ips or ["0.0.0.0"]
    else:
        raise NotImplementedError(f"Not implemented for {env.cloud.name.value}")
