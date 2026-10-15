from google.api_core.exceptions import Forbidden, PermissionDenied

from rod.libs.py.cloud.exceptions import CloudPermissionsDenied
from rod.libs.py.tf.tfvars import Env, CloudTypeEnum
from rod.libs.py.gcp.network import list_nat_gws


def nat_gw_ips(env: Env) -> list[str]:
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
        return ips
    else:
        raise NotImplementedError(f"Not implemented for {env.cloud.name.value}")
