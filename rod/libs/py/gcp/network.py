from google.api_core.exceptions import Forbidden, PermissionDenied
from google.cloud import compute_v1
from pydantic import BaseModel


class NetworkPermissionsDenied(Exception):
    """The caller does not have permission to access network resources."""


class NatGw(BaseModel):
    name: str
    router: str
    region: str
    nat_ips: list[str]
    network: str


def list_nat_gws(project_id: str, location: str) -> list[NatGw]:
    client = compute_v1.RoutersClient()
    addresses_client = compute_v1.AddressesClient()

    request = compute_v1.ListRoutersRequest(
        project=project_id,
        region=location,
    )

    nats: list[NatGw] = []

    try:
        for router in list(client.list(request=request)):
            for nat in router.nats:
                nats.append(
                    NatGw(
                        name=nat.name,
                        router=router.name,
                        region=location,
                        nat_ips=[
                            addresses_client.get(
                                project=project_id,
                                region=location,
                                address=address_url.rsplit("/", 1)[-1],
                            ).address
                            for address_url in nat.nat_ips
                        ],
                        network=router.network,
                    )
                )
    except (Forbidden, PermissionDenied) as error:
        raise NetworkPermissionsDenied(
            f"Cannot list NAT gateways in project {project_id} "
            f"and region {location}: {error}"
        ) from error

    return nats
