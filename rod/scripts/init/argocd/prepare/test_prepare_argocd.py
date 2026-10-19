import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import yaml

from rod.libs.py.tf.tfvars import CloudTypeEnum
from rod.scripts.init.argocd.prepare import prepare_argocd as step


class TestPrepareArgocd(unittest.TestCase):
    """
    Verify bootstrap ordering, Helm inputs, rendered manifests, and failures.
    """

    def setUp(self):
        """
        Create local image metadata and isolate Helm and cluster operations.
        """
        self.root = Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.images = self.root / "images"
        (self.images / "argocd").mkdir(parents=True)
        (self.images / "argocd" / "image_tag.txt").write_text(
            "v1.2.3\n", encoding="utf-8"
        )
        self.paths = SimpleNamespace(
            argocd_crds_dir=str(self.root / "crds"),
            argocd_environments_dir=str(self.root / "environments"),
            argocd_dir=str(self.root / "argocd"),
            argocd_chart_dir=str(self.root / "charts"),
            deps_images_dir=str(self.images),
            tfvars_file=str(self.root / "terraform.tfvars.json"),
        )
        self.internal = SimpleNamespace(
            type="internal",
            short_name="int",
            cloud=SimpleNamespace(name=CloudTypeEnum.gcp),
            registry=SimpleNamespace(url="registry.example.com/project"),
            dns=SimpleNamespace(domain="example.com."),
        )
        self.enterContext(patch.object(step, "common_paths", self.paths))
        self.enterContext(patch.object(step, "HELM_EXECUTABLE", "helm-test"))
        self.enterContext(
            patch.object(
                step,
                "formatted_tfvars",
                return_value=SimpleNamespace(
                    envs={
                        "development": SimpleNamespace(type="product"),
                        "internal": self.internal,
                    }
                ),
            )
        )
        self.rendered = [
            [
                "apiVersion: v1",
                "kind: ConfigMap",
                "metadata:",
                "  name: argocd",
                "  namespace: argocd",
            ],
            [
                "apiVersion: argoproj.io/v1alpha1",
                "kind: Application",
                "metadata:",
                "  name: root",
                "  namespace: argocd",
            ],
        ]
        self.commands = self.enterContext(
            patch.object(
                step,
                "run_command",
                side_effect=[
                    (0, [], []),
                    (0, [], self.rendered[0]),
                    (0, [], self.rendered[1]),
                ],
            )
        )
        self.apply = self.enterContext(patch.object(step, "apply_manifests"))

    def test_bootstrap_applies_crds_then_rendered_charts(self):
        """
        Verify chart ordering and that flushed temporary manifests are readable.
        """
        events = []
        documents = []
        temp_paths = []

        def record_apply(env, **source):
            """
            Read manifests while their temporary files are still available.

            Args:
                env: Target environment supplied to manifest application.
                source: Manifest file or directory arguments.
            """
            self.assertIs(env, self.internal)
            if "dir_path" in source:
                events.append("crds")
                self.assertEqual(
                    source["dir_path"], self.paths.argocd_crds_dir + "/argocd"
                )
            else:
                events.append("apply")
                file = Path(source["file_path"])
                temp_paths.append(file)
                documents.append(yaml.safe_load(file.read_text()))

        def record_command(command, **options):
            """
            Return rendered chart output and record command execution order.

            Args:
                command: Helm command arguments.
                options: Output and failure handling options.

            Returns:
                Successful command result containing rendered chart lines.
            """
            events.append(command[1])
            self.assertTrue(options["raise_exception"])
            self.assertFalse(options["print_stdout"])
            if command[1] == "dependency":
                return 0, [], []
            return 0, [], self.rendered[len(documents)]

        self.apply.side_effect = record_apply
        self.commands.side_effect = record_command
        step.prepare_argocd()
        self.assertEqual(
            events, ["crds", "dependency", "template", "apply", "template", "apply"]
        )
        self.assertEqual(
            [obj["metadata"]["name"] for obj in documents], ["argocd", "root"]
        )
        self.assertTrue(all(not file.exists() for file in temp_paths))
        commands = [call.args[0] for call in self.commands.call_args_list]
        self.assertEqual(
            commands[0],
            [
                "helm-test",
                "dependency",
                "update",
                self.paths.argocd_chart_dir + "/argocd/",
            ],
        )
        argocd = commands[1]
        for value in (
            self.paths.argocd_environments_dir + "/gcp-int/argocd/values.yaml",
            self.paths.argocd_chart_dir + "/globals.yaml",
            "argocd.global.image.repository=registry.example.com/project/argocd",
            "argocd.global.image.tag=v1.2.3",
            "global.env.dns.domain=example.com",
        ):
            self.assertIn(value, argocd)
        self.assertIn(self.paths.argocd_dir + "/envs.yaml", commands[2])
        self.assertIn("tfvars=" + self.paths.tfvars_file, commands[2])

    def test_helm_failures_exit_before_later_steps(self):
        """
        Verify failures in dependency update or either render stop bootstrap.
        """
        for failure_index in range(3):
            with self.subTest(failure_index=failure_index):
                outcomes = [
                    (0, [], []),
                    (0, [], self.rendered[0]),
                    (0, [], self.rendered[1]),
                ]
                outcomes[failure_index] = step.CommandException(1, "helm failed")
                self.commands.reset_mock()
                self.apply.reset_mock()
                self.commands.side_effect = outcomes
                with self.assertRaises(SystemExit) as raised:
                    step.prepare_argocd()
                self.assertEqual(raised.exception.code, 1)
                self.assertEqual(self.commands.call_count, failure_index + 1)
                self.assertEqual(self.apply.call_count, 2 if failure_index == 2 else 1)

    def test_manifest_failures_stop_bootstrap(self):
        """
        Verify failure at any manifest stage prevents later installation work.
        """
        for failure_index in range(3):
            with self.subTest(failure_index=failure_index):
                self.commands.reset_mock()
                self.commands.side_effect = [
                    (0, [], []),
                    (0, [], self.rendered[0]),
                    (0, [], self.rendered[1]),
                ]
                self.apply.reset_mock()
                self.apply.side_effect = [None] * failure_index + [
                    step.K8sApiException("apply failed")
                ]
                with self.assertRaises(SystemExit) as raised:
                    step.prepare_argocd()
                self.assertEqual(raised.exception.code, 1)
                self.assertEqual(self.apply.call_count, failure_index + 1)
                self.assertEqual(self.commands.call_count, (0, 2, 3)[failure_index])
