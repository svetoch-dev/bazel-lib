from google.cloud import compute_v1
from pydantic import BaseModel


class NatGw(BaseModel):
    """
    Describe a NAT gateway and its configured static IP addresses.

    Args:
        name: NAT gateway name.
        router: Name of the router containing the gateway.
        region: Region containing the router.
        nat_ips: Resolved static external IP addresses for the gateway.
        network: Network URL associated with the router.
    """

    name: str
    router: str
    region: str
    nat_ips: list[str]
    network: str


def list_nat_gws(project_id: str, location: str) -> list[NatGw]:
    """
    List NAT gateways in a GCP project and region.

    Resolves each configured static address URL to its IP address. Gateways
    without configured static addresses are included with an empty IP list.
    Cloud API errors propagate to the caller.

    Args:
        project_id: GCP project containing the routers and addresses.
        location: Region in which to list routers.

    Returns:
        NAT gateways from all routers in the requested project and region.
    """
    client = compute_v1.RoutersClient()
    addresses_client = compute_v1.AddressesClient()

    request = compute_v1.ListRoutersRequest(
        project=project_id,
        region=location,
    )

    nats: list[NatGw] = []

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

    return nats
