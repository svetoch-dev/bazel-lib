import unittest
from unittest.mock import call, patch

from google.api_core.exceptions import NotFound, PermissionDenied
from google.cloud import compute_v1

from rod.libs.py.gcp.network import NatGw, list_nat_gws


class TestListNatGws(unittest.TestCase):
    @patch("rod.libs.py.gcp.network.compute_v1.AddressesClient")
    @patch("rod.libs.py.gcp.network.compute_v1.RoutersClient")
    def test_resolves_address_urls_to_ips(self, routers_client, addresses_client):
        address_prefix = (
            "https://www.googleapis.com/compute/v1/projects/project"
            "/regions/europe-west1/addresses"
        )
        routers_client.return_value.list.return_value = [
            compute_v1.Router(
                name="router",
                network="networks/default",
                nats=[
                    compute_v1.RouterNat(
                        name="nat",
                        nat_ips=[f"{address_prefix}/nat-1", f"{address_prefix}/nat-2"],
                    )
                ],
            )
        ]
        addresses_client.return_value.get.side_effect = [
            compute_v1.Address(address="203.0.113.1"),
            compute_v1.Address(address="203.0.113.2"),
        ]

        result = list_nat_gws("project", "europe-west1")

        self.assertEqual(
            result,
            [
                NatGw(
                    name="nat",
                    router="router",
                    region="europe-west1",
                    nat_ips=["203.0.113.1", "203.0.113.2"],
                    network="networks/default",
                )
            ],
        )
        self.assertEqual(
            addresses_client.return_value.get.call_args_list,
            [
                call(project="project", region="europe-west1", address="nat-1"),
                call(project="project", region="europe-west1", address="nat-2"),
            ],
        )
        routers_client.return_value.list.assert_called_once_with(
            request=compute_v1.ListRoutersRequest(
                project="project", region="europe-west1"
            )
        )

    @patch("rod.libs.py.gcp.network.compute_v1.AddressesClient")
    @patch("rod.libs.py.gcp.network.compute_v1.RoutersClient")
    def test_nat_without_address_urls_keeps_empty_ips(
        self, routers_client, addresses_client
    ):
        routers_client.return_value.list.return_value = [
            compute_v1.Router(name="router", nats=[compute_v1.RouterNat(name="nat")])
        ]

        result = list_nat_gws("project", "europe-west1")

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].nat_ips, [])
        addresses_client.return_value.get.assert_not_called()

    @patch("rod.libs.py.gcp.network.compute_v1.AddressesClient")
    @patch("rod.libs.py.gcp.network.compute_v1.RoutersClient")
    def test_no_nat_gateways_returns_empty_list(self, routers_client, addresses_client):
        for routers in ([], [compute_v1.Router(name="router")]):
            with self.subTest(routers=routers):
                routers_client.return_value.list.return_value = routers

                self.assertEqual(list_nat_gws("project", "europe-west1"), [])

                addresses_client.return_value.get.assert_not_called()

    @patch("rod.libs.py.gcp.network.compute_v1.AddressesClient")
    @patch("rod.libs.py.gcp.network.compute_v1.RoutersClient")
    def test_returns_all_nats_across_routers(self, routers_client, addresses_client):
        address_prefix = "projects/project/regions/europe-west1/addresses"
        routers_client.return_value.list.return_value = iter(
            [
                compute_v1.Router(
                    name="router-1",
                    network="networks/first",
                    nats=[
                        compute_v1.RouterNat(
                            name="nat-1", nat_ips=[f"{address_prefix}/ip-1"]
                        ),
                        compute_v1.RouterNat(
                            name="nat-2", nat_ips=[f"{address_prefix}/ip-2"]
                        ),
                    ],
                ),
                compute_v1.Router(name="empty-router"),
                compute_v1.Router(
                    name="router-2",
                    network="networks/second",
                    nats=[
                        compute_v1.RouterNat(
                            name="nat-3", nat_ips=[f"{address_prefix}/ip-3"]
                        )
                    ],
                ),
            ]
        )
        ips = {
            "ip-1": "203.0.113.1",
            "ip-2": "203.0.113.2",
            "ip-3": "203.0.113.3",
        }
        addresses_client.return_value.get.side_effect = (
            lambda *, project, region, address: compute_v1.Address(address=ips[address])
        )

        result = list_nat_gws("project", "europe-west1")

        self.assertEqual(
            result,
            [
                NatGw(
                    name="nat-1",
                    router="router-1",
                    region="europe-west1",
                    nat_ips=["203.0.113.1"],
                    network="networks/first",
                ),
                NatGw(
                    name="nat-2",
                    router="router-1",
                    region="europe-west1",
                    nat_ips=["203.0.113.2"],
                    network="networks/first",
                ),
                NatGw(
                    name="nat-3",
                    router="router-2",
                    region="europe-west1",
                    nat_ips=["203.0.113.3"],
                    network="networks/second",
                ),
            ],
        )

    @patch("rod.libs.py.gcp.network.compute_v1.AddressesClient")
    @patch("rod.libs.py.gcp.network.compute_v1.RoutersClient")
    def test_router_listing_error_propagates(self, routers_client, addresses_client):
        error = PermissionDenied("Router access denied")
        routers_client.return_value.list.side_effect = error

        with self.assertRaises(PermissionDenied) as raised:
            list_nat_gws("project", "europe-west1")

        self.assertIs(raised.exception, error)
        addresses_client.return_value.get.assert_not_called()

    @patch("rod.libs.py.gcp.network.compute_v1.AddressesClient")
    @patch("rod.libs.py.gcp.network.compute_v1.RoutersClient")
    def test_address_lookup_error_propagates(self, routers_client, addresses_client):
        address_prefix = "projects/project/regions/europe-west1/addresses"
        routers_client.return_value.list.return_value = [
            compute_v1.Router(
                name="router",
                nats=[
                    compute_v1.RouterNat(
                        name="nat",
                        nat_ips=[f"{address_prefix}/ip-1", f"{address_prefix}/missing"],
                    )
                ],
            )
        ]
        error = NotFound("Address not found")
        addresses_client.return_value.get.side_effect = [
            compute_v1.Address(address="203.0.113.1"),
            error,
        ]

        with self.assertRaises(NotFound) as raised:
            list_nat_gws("project", "europe-west1")

        self.assertIs(raised.exception, error)
        self.assertEqual(addresses_client.return_value.get.call_count, 2)


if __name__ == "__main__":
    unittest.main()
