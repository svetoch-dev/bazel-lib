import unittest
from unittest.mock import Mock, patch

from kubernetes.client.exceptions import ApiException

from rod.libs.py.k8s.api import KubernetesApi, PodCommandError, get_error_details


class TestKubernetesApi(unittest.TestCase):
    def setUp(self):
        self.clock = self.enterContext(
            patch("rod.libs.py.k8s.api.time.monotonic", return_value=0)
        )
        self.create_client = self.enterContext(
            patch("rod.libs.py.k8s.api.k8s_client_get")
        )
        self.client = self.create_client.return_value
        self.environment = Mock()
        self.api = KubernetesApi(self.environment)

    def test_client_is_reused_before_40_minutes(self):
        self.create_client.assert_called_once_with(self.environment)
        self.clock.return_value = 40 * 60 - 1
        self.assertIs(self.api.api, self.client)
        self.create_client.assert_called_once()
        self.client.v1.api_client.close.assert_not_called()

    def test_client_is_replaced_at_40_minutes(self):
        replacement = Mock()
        self.create_client.return_value = replacement
        self.clock.return_value = 40 * 60
        self.assertIs(self.api.api, replacement)
        self.assertEqual(self.create_client.call_count, 2)
        for name in (
            "v1",
            "custom",
            "apps",
            "batch",
            "networking",
            "rbac",
            "storage",
            "autoscaling",
            "policy",
            "scheduling",
            "coordination",
            "discovery",
        ):
            api_client = getattr(self.client, name).api_client
            api_client.close.assert_called_once_with()
            api_client.rest_client.pool_manager.clear.assert_called_once_with()
        self.assertIs(self.api.api, replacement)
        self.assertEqual(self.create_client.call_count, 2)
        self.create_client.assert_called_with(self.environment)
        replacement.v1.api_client.close.assert_not_called()

    def test_refresh_interval_restarts_after_client_replacement(self):
        replacement = Mock()
        self.create_client.return_value = replacement
        self.clock.return_value = 40 * 60
        self.assertIs(self.api.api, replacement)

        self.clock.return_value = 80 * 60 - 1
        self.assertIs(self.api.api, replacement)
        self.assertEqual(self.create_client.call_count, 2)

        next_client = Mock()
        self.create_client.return_value = next_client
        self.clock.return_value = 80 * 60
        self.assertIs(self.api.api, next_client)
        self.assertEqual(self.create_client.call_count, 3)
        replacement.v1.api_client.close.assert_called_once_with()

    def test_failed_refresh_keeps_old_client_and_retries(self):
        self.clock.return_value = 40 * 60
        self.create_client.side_effect = RuntimeError("authentication failed")
        with self.assertRaisesRegex(RuntimeError, "authentication failed"):
            self.api.api
        self.client.v1.api_client.close.assert_not_called()
        self.assertIs(self.api._api, self.client)

        replacement = Mock()
        self.create_client.side_effect = None
        self.create_client.return_value = replacement
        self.assertIs(self.api.api, replacement)
        self.assertEqual(self.create_client.call_count, 3)

    def test_list_resources_passes_namespace_and_selector(self):
        for kind, method in (
            ("pods", "list_namespaced_pod"),
            ("statefulsets", "list_namespaced_stateful_set"),
            ("persistentvolumeclaims", "list_namespaced_persistent_volume_claim"),
        ):
            with self.subTest(kind=kind):
                resource = Mock()
                resource.to_dict.return_value = {
                    "metadata": {"name": "example-postgres-clone-a1b2"}
                }
                list_method = getattr(self.client, method)
                list_method.return_value.items = [resource]
                self.assertEqual(
                    self.api.list_resources(kind, "database", "run-id=abcd"),
                    [
                        {
                            "metadata": {"name": "example-postgres-clone-a1b2"},
                            "kind": kind,
                        }
                    ],
                )
                list_method.assert_called_once_with(
                    "database", label_selector="run-id=abcd"
                )

    def test_exec_returns_stdout_and_passes_command_without_shell(self):
        with patch("rod.libs.py.k8s.api.stream.stream") as stream:
            response = stream.return_value
            response.returncode = 0
            response.read_stdout.return_value = "f\n"
            self.assertEqual(
                self.api.exec_in_pod(
                    "database",
                    "example-postgres-clone-a1b2-0",
                    ["psql", "-Atc", "SQL"],
                ),
                "f\n",
            )
            stream.assert_called_once_with(
                self.client.v1.connect_get_namespaced_pod_exec,
                "example-postgres-clone-a1b2-0",
                "database",
                command=["psql", "-Atc", "SQL"],
                container="postgres",
                stderr=True,
                stdin=False,
                stdout=True,
                tty=False,
                _preload_content=False,
            )
            response.run_forever.assert_called_once_with()
            response.read_stdout.assert_called_once_with()
            response.read_stderr.assert_called_once_with()
            response.close.assert_called_once_with()

    def test_exec_nonzero_exit_preserves_output(self):
        with patch("rod.libs.py.k8s.api.stream.stream") as stream:
            response = stream.return_value
            response.returncode = 1
            response.read_stdout.return_value = "partial result"
            response.read_stderr.return_value = "SQL failed"
            with self.assertRaises(PodCommandError) as raised:
                self.api.exec_in_pod(
                    "database",
                    "example-postgres-clone-a1b2-0",
                    ["psql"],
                )
            self.assertEqual(raised.exception.stdout, "partial result")
            self.assertEqual(raised.exception.stderr, "SQL failed")
            self.assertEqual(raised.exception.return_code, 1)
            response.close.assert_called_once_with()

    def test_exec_missing_exit_code_is_an_error(self):
        with patch("rod.libs.py.k8s.api.stream.stream") as stream:
            response = stream.return_value
            response.returncode = None
            with self.assertRaisesRegex(RuntimeError, "did not return an exit code"):
                self.api.exec_in_pod(
                    "database",
                    "example-postgres-clone-a1b2-0",
                    ["psql"],
                )
            response.close.assert_called_once_with()

    def test_exec_closes_websocket_when_reading_or_running_fails(self):
        for method in ("run_forever", "read_stdout", "read_stderr"):
            with self.subTest(method=method):
                with patch("rod.libs.py.k8s.api.stream.stream") as stream:
                    response = stream.return_value
                    getattr(response, method).side_effect = RuntimeError("disconnected")
                    with self.assertRaisesRegex(RuntimeError, "disconnected"):
                        self.api.exec_in_pod(
                            "database",
                            "example-postgres-clone-a1b2-0",
                            ["psql"],
                        )
                    response.close.assert_called_once_with()


class TestErrors(unittest.TestCase):
    def test_api_error_with_and_without_body(self):
        error = ApiException(status=403, reason="Forbidden")
        self.assertEqual(
            get_error_details(error), "Kubernetes API returned 403: Forbidden"
        )
        error.body = '{"message": "permission denied"}'
        self.assertEqual(
            get_error_details(error),
            'Kubernetes API returned 403: Forbidden\n{"message": "permission denied"}',
        )

    def test_regular_error(self):
        self.assertEqual(get_error_details(RuntimeError("failed")), "failed")

    def test_pod_command_error_attributes_and_message(self):
        error = PodCommandError(
            namespace="database",
            pod="example-postgres-clone-a1b2-0",
            command=["psql", "-c", "SQL"],
            return_code=2,
            stdout=" partial output\n",
            stderr=" SQL failed\n",
        )
        self.assertEqual(error.namespace, "database")
        self.assertEqual(error.pod, "example-postgres-clone-a1b2-0")
        self.assertEqual(error.command, ["psql", "-c", "SQL"])
        self.assertEqual(error.return_code, 2)
        self.assertEqual(error.stdout, " partial output\n")
        self.assertEqual(error.stderr, " SQL failed\n")
        self.assertEqual(
            str(error),
            "Command 'psql' in pod database/example-postgres-clone-a1b2-0 exited with code 2\n"
            "stderr:\nSQL failed\n"
            "stdout before failure:\npartial output",
        )

    def test_pod_command_error_without_output(self):
        error = PodCommandError(
            namespace="database",
            pod="example-postgres-clone-a1b2-0",
            command=["psql"],
            return_code=1,
            stdout="",
            stderr=" \n",
        )
        self.assertEqual(
            str(error),
            "Command 'psql' in pod database/example-postgres-clone-a1b2-0 exited with code 1",
        )
