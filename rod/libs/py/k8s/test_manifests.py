import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, call, patch

from rod.libs.py.k8s import manifests
from rod.libs.py.k8s.exceptions import K8sApiException


class TestApplyManifests(unittest.TestCase):
    """
    Verify manifest namespace selection and API error wrapping.
    """

    def setUp(self):
        """
        Create a multi-document YAML fixture and mock Kubernetes API access.
        """
        self.folder = Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.yaml_file = self.folder / "manifests.yaml"
        self.yaml_file.write_text(
            "---\n"
            "apiVersion: v1\n"
            "kind: ConfigMap\n"
            "metadata:\n"
            "  name: explicit\n"
            "  namespace: monitoring\n"
            "---\n"
            "---\n"
            "apiVersion: v1\n"
            "kind: ConfigMap\n"
            "metadata:\n"
            "  name: fallback\n",
            encoding="utf-8",
        )
        self.api_client = Mock()
        self.client_get = self.enterContext(
            patch.object(
                manifests,
                "k8s_client_get",
                return_value=SimpleNamespace(client=self.api_client),
            )
        )
        self.create_from_yaml = self.enterContext(
            patch.object(manifests.utils, "create_from_yaml")
        )

    def test_file_and_directory_preserve_document_namespaces(self):
        """
        Verify file and directory inputs honor explicit and fallback namespaces.
        """
        for source in (
            {"file_path": str(self.yaml_file)},
            {"dir_path": str(self.folder)},
        ):
            with self.subTest(source=source):
                self.create_from_yaml.reset_mock()

                manifests.apply_manifests(Mock(), namespace="argocd", **source)

                self.assertEqual(
                    self.create_from_yaml.call_args_list,
                    [
                        call(
                            self.api_client,
                            yaml_objects=[
                                {
                                    "apiVersion": "v1",
                                    "kind": "ConfigMap",
                                    "metadata": {
                                        "name": "explicit",
                                        "namespace": "monitoring",
                                    },
                                }
                            ],
                            apply=True,
                            namespace="monitoring",
                        ),
                        call(
                            self.api_client,
                            yaml_objects=[
                                {
                                    "apiVersion": "v1",
                                    "kind": "ConfigMap",
                                    "metadata": {"name": "fallback"},
                                }
                            ],
                            apply=True,
                            namespace="argocd",
                        ),
                    ],
                )

    def test_api_errors_are_wrapped(self):
        """
        Verify Kubernetes creation failures become K8sApiException errors.
        """
        self.create_from_yaml.side_effect = manifests.utils.FailToCreateError([])

        with self.assertRaises(K8sApiException):
            manifests.apply_manifests(Mock(), file_path=str(self.yaml_file))

    def test_requires_exactly_one_source_before_connecting(self):
        """
        Verify missing or conflicting inputs fail before accessing a cluster.
        """
        for source in (
            {},
            {"file_path": str(self.yaml_file), "dir_path": str(self.folder)},
            {"yaml_object": {"kind": "ConfigMap"}, "file_path": str(self.yaml_file)},
            {"yaml_object": {"kind": "ConfigMap"}, "dir_path": str(self.folder)},
        ):
            with self.subTest(source=source), self.assertRaises(ValueError):
                manifests.apply_manifests(Mock(), **source)
        self.client_get.assert_not_called()

    def test_yaml_object_is_applied_directly_with_fallback_namespace(self):
        """
        Verify a deserialized object bypasses file reading.
        """
        obj = {
            "apiVersion": "v1",
            "kind": "ConfigMap",
            "metadata": {"name": "inline", "namespace": "argocd"},
        }

        manifests.apply_manifests(Mock(), namespace="argocd", yaml_object=obj)

        self.client_get.assert_called_once()
        self.create_from_yaml.assert_called_once_with(
            self.api_client, yaml_objects=[obj], apply=True, namespace="argocd"
        )

    def test_yaml_object_api_errors_are_wrapped(self):
        """
        Verify a failing object application becomes K8sApiException.
        """
        self.create_from_yaml.side_effect = manifests.utils.FailToCreateError([])

        with self.assertRaises(K8sApiException):
            manifests.apply_manifests(Mock(), yaml_object={"kind": "ConfigMap"})

    def test_directory_includes_both_yaml_extensions_only(self):
        """
        Verify directory inputs include YAML files and ignore other extensions.
        """
        (self.folder / "other.yml").write_text(
            "kind: Namespace\nmetadata:\n  name: other\n", encoding="utf-8"
        )
        (self.folder / "ignored.txt").write_text("not YAML", encoding="utf-8")
        manifests.apply_manifests(Mock(), dir_path=str(self.folder))
        self.assertEqual(self.create_from_yaml.call_count, 3)
        names = {
            call.kwargs["yaml_objects"][0]["metadata"]["name"]
            for call in self.create_from_yaml.call_args_list
        }
        self.assertEqual(names, {"explicit", "fallback", "other"})

    def test_empty_documents_make_no_api_calls(self):
        """
        Verify blank and comment-only documents are ignored.
        """
        self.yaml_file.write_text("---\n# empty\n---\n", encoding="utf-8")
        manifests.apply_manifests(Mock(), file_path=str(self.yaml_file))
        self.create_from_yaml.assert_not_called()

    def test_missing_sources_raise_file_not_found(self):
        """
        Verify missing files and directories cannot silently succeed.
        """
        for source in (
            {"file_path": str(self.folder / "missing.yaml")},
            {"dir_path": str(self.folder / "missing")},
        ):
            with self.subTest(source=source), self.assertRaises(FileNotFoundError):
                manifests.apply_manifests(Mock(), **source)
        self.create_from_yaml.assert_not_called()

    def test_directory_api_errors_are_collected_after_all_documents(self):
        """
        Verify every document is attempted and failures surface together in order.
        """
        errors = [manifests.utils.FailToCreateError([]) for _ in range(2)]
        self.create_from_yaml.side_effect = errors

        with self.assertRaises(K8sApiException) as raised:
            manifests.apply_manifests(Mock(), dir_path=str(self.folder))

        self.assertEqual(self.create_from_yaml.call_count, 2)
        self.assertEqual(raised.exception.errors, errors)
        self.assertEqual(raised.exception.args, (errors,))


class TestApplyObject(unittest.TestCase):
    """
    Verify single-object application, namespace fallback, and error propagation.
    """

    def setUp(self):
        """
        Mock Kubernetes API access for direct object application.
        """
        self.api_client = Mock()
        self.create_from_yaml = self.enterContext(
            patch.object(manifests.utils, "create_from_yaml")
        )

    def test_applies_object_with_fallback_namespace(self):
        """
        Verify the fallback namespace is used when the object has none.
        """
        obj = {"apiVersion": "v1", "kind": "ConfigMap", "metadata": {"name": "app"}}

        manifests.apply_object(self.api_client, obj, namespace="argocd")

        self.create_from_yaml.assert_called_once_with(
            self.api_client, yaml_objects=[obj], apply=True, namespace="argocd"
        )

    def test_object_namespace_overrides_fallback(self):
        """
        Verify a declared metadata.namespace wins over the fallback.
        """
        obj = {
            "apiVersion": "v1",
            "kind": "ConfigMap",
            "metadata": {"name": "app", "namespace": "monitoring"},
        }

        manifests.apply_object(self.api_client, obj, namespace="argocd")

        self.create_from_yaml.assert_called_once_with(
            self.api_client, yaml_objects=[obj], apply=True, namespace="monitoring"
        )

    def test_api_errors_propagate_unchanged(self):
        """
        Verify wrapping to K8sApiException happens in the caller, not here.
        """
        self.create_from_yaml.side_effect = manifests.utils.FailToCreateError([])
        obj = {"apiVersion": "v1", "kind": "ConfigMap", "metadata": {"name": "app"}}

        with self.assertRaises(manifests.utils.FailToCreateError):
            manifests.apply_object(self.api_client, obj)


if __name__ == "__main__":
    unittest.main()
