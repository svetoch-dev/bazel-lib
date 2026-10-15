from rod.libs.py.tf.tfvars import Env, CloudTypeEnum
from rod.libs.py.gcp.network import list_nat_gws


def nat_gw_ips(env: Env) -> list[str]:
    if env.cloud.name == CloudTypeEnum.yc:
        # We havent static ip nat gws yet
        # so we allow all for now
        return ["0.0.0.0"]
    elif env.cloud.name == CloudTypeEnum.gcp:
        ips = []
        gws = list_nat_gws(env.cloud.id, env.cloud.location.region)
        for gw in gws:
            ips += gw.nat_ips
        print(ips)
        return ips
    else:
        raise NotImplementedError(f"Not implemented for {env.cloud.name.value}")
