import argparse
import unittest
from unittest.mock import Mock, patch

from kubernetes.client.exceptions import ApiException

from rod.scripts.pg.backup_restore import backup_restore


class TestTimestamp(unittest.TestCase):
    def test_invalid_timezone_components_are_rejected(self):
        for offset in ("+00:60", "-00:60", "+01:99", "+16:00", "+24:00"):
            with self.subTest(offset=offset):
                with self.assertRaises(argparse.ArgumentTypeError):
                    backup_restore.parse_timestamp(f"2026-01-07T00:00:00{offset}")

    def test_valid_timezone_and_fraction_are_preserved(self):
        for offset in ("+00:00", "+05:30", "-03:30", "+15:59"):
            with self.subTest(offset=offset):
                timestamp = f"2026-01-07T00:00:00.123456789{offset}"
                self.assertEqual(backup_restore.parse_timestamp(timestamp), timestamp)

    def test_default_timezone_is_utc(self):
        for timestamp in ("2026-01-07", "2026.01.07 00:00:00", "2026-01-07T00:00:00Z"):
            with self.subTest(timestamp=timestamp):
                self.assertEqual(
                    backup_restore.parse_timestamp(timestamp),
                    "2026-01-07T00:00:00+00:00",
                )


class TestCloneStorage(unittest.TestCase):
    def setUp(self):
        self.k8s = Mock()
        self.args = argparse.Namespace(
            postgres="example-postgres-cluster",
            namespace="database",
            database="example",
            timestamp="2026-01-07T00:00:00+00:00",
            k8s_resource_poll_interval_seconds=5,
            postgres_recovery_poll_interval_seconds=3,
        )
        self.source = {
            "metadata": {
                "name": self.args.postgres,
                "namespace": self.args.namespace,
                "uid": "source-uid",
            },
            "spec": {
                "teamId": "example",
                "postgresql": {"version": "15"},
                "volume": {"size": "20Gi"},
            },
        }
        self.enterContext(
            patch.object(
                backup_restore, "find_source_cluster", return_value=self.source
            )
        )
        self.enterContext(
            patch.object(
                backup_restore.uuid, "uuid4", return_value=Mock(hex="a1b2" + "0" * 28)
            )
        )

    def test_retained_storage_prevents_creation_and_cleanup(self):
        self.k8s.list_resources.return_value = [{"metadata": {"name": "retained-pvc"}}]
        with self.assertRaisesRegex(RuntimeError, "PVCs already exist"):
            backup_restore.run_check(self.args, self.k8s)
        self.k8s.list_resources.assert_called_once_with(
            "persistentvolumeclaims",
            "database",
            "cluster-name=example-postgres-cluster-clone-a1b2",
        )
        self.k8s.create_postgresql.assert_not_called()
        self.k8s.exec_in_pod.assert_not_called()
        self.k8s.delete_postgresqls.assert_not_called()
        self.k8s.delete_persistentvolumeclaims.assert_not_called()

    def test_storage_lookup_failure_prevents_creation(self):
        error = ApiException(status=403, reason="Forbidden")
        self.k8s.list_resources.side_effect = error
        with self.assertRaises(ApiException) as raised:
            backup_restore.run_check(self.args, self.k8s)
        self.assertIs(raised.exception, error)
        self.k8s.create_postgresql.assert_not_called()
        self.k8s.delete_persistentvolumeclaims.assert_not_called()

    def test_no_existing_storage_allows_creation(self):
        self.k8s.list_resources.return_value = []
        error = ApiException(status=409, reason="Conflict")
        self.k8s.create_postgresql.side_effect = error
        self.k8s.get_postgresql.side_effect = ApiException(status=404)
        with self.assertRaises(ApiException) as raised:
            backup_restore.run_check(self.args, self.k8s)
        self.assertIs(raised.exception, error)
        self.k8s.create_postgresql.assert_called_once()
        self.k8s.delete_postgresqls.assert_not_called()
        self.k8s.delete_persistentvolumeclaims.assert_not_called()


if __name__ == "__main__":
    unittest.main()
