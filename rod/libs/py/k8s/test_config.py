import unittest

from pydantic import ValidationError

from rod.libs.py.k8s.config import (
    Cluster,
    ExecConfig,
    ExecInteractiveModeEnum,
    KubeConfig,
)


class TestKubeConfig(unittest.TestCase):
    def test_all_fields_round_trip(self):
        extensions = [
            {
                "name": "custom",
                "extension": {"nested": [1, True, None, {"custom-key": "value"}]},
            }
        ]
        config = {
            "kind": "Config",
            "apiVersion": "v1",
            "preferences": {"colors": True, "extensions": extensions},
            "clusters": [
                {
                    "name": "cluster",
                    "cluster": {
                        "server": "https://example.com",
                        "tls-server-name": "example.com",
                        "insecure-skip-tls-verify": False,
                        "certificate-authority": "ca.crt",
                        "certificate-authority-data": "Y2E=",
                        "proxy-url": "http://localhost:8080",
                        "disable-compression": True,
                        "extensions": extensions,
                    },
                }
            ],
            "users": [
                {
                    "name": "user",
                    "user": {
                        "client-certificate": "client.crt",
                        "client-certificate-data": "Y2VydA==",
                        "client-key": "client.key",
                        "client-key-data": "a2V5",
                        "token": "test-token",
                        "tokenFile": "token.txt",
                        "as": "impersonated-user",
                        "as-uid": "uid",
                        "as-groups": ["developers"],
                        "as-user-extra": {"scopes": ["view"]},
                        "username": "test-user",
                        "password": "test-password",
                        "auth-provider": {
                            "name": "oidc",
                            "config": {"id-token": "test-id-token"},
                        },
                        "exec": {
                            "command": "credential-plugin",
                            "args": ["get-token"],
                            "env": [{"name": "REGION", "value": "test-region"}],
                            "apiVersion": "client.authentication.k8s.io/v1",
                            "installHint": "Install credential-plugin",
                            "provideClusterInfo": True,
                            "interactiveMode": "Never",
                        },
                        "extensions": extensions,
                    },
                }
            ],
            "contexts": [
                {
                    "name": "context",
                    "context": {
                        "cluster": "cluster",
                        "user": "user",
                        "namespace": "default",
                        "extensions": extensions,
                    },
                }
            ],
            "current-context": "context",
            "extensions": extensions,
        }

        model = KubeConfig.model_validate(config)
        self.assertIs(
            model.users[0].user.exec.interactive_mode, ExecInteractiveModeEnum.never
        )
        self.assertEqual(
            model.model_dump(mode="json", by_alias=True, exclude_none=True), config
        )
        self.assertEqual(
            KubeConfig.model_validate_json(model.model_dump_json(by_alias=True)), model
        )

    def test_python_field_names_serialize_to_kubeconfig_keys(self):
        model = KubeConfig(
            current_context="context",
            clusters=[
                {
                    "name": "cluster",
                    "cluster": Cluster(
                        server="https://example.com",
                        certificate_authority_data="Y2E=",
                    ),
                }
            ],
        )
        data = model.model_dump(by_alias=True, exclude_none=True)
        self.assertEqual(data["current-context"], "context")
        self.assertEqual(
            data["clusters"][0]["cluster"]["certificate-authority-data"], "Y2E="
        )
        self.assertNotIn("certificate-authority", data["clusters"][0]["cluster"])

    def test_empty_config_collections_are_independent(self):
        first = KubeConfig()
        second = KubeConfig()
        first.preferences.colors = True
        first.clusters.append(
            {"name": "cluster", "cluster": {"server": "https://example.com"}}
        )
        self.assertEqual(second.clusters, [])
        self.assertIsNone(second.preferences.colors)

    def test_unknown_fields_are_rejected_at_each_level(self):
        for data in (
            {"unknown": True},
            {"preferences": {"unknown": True}},
            {
                "clusters": [
                    {"name": "cluster", "cluster": {"server": "", "unknown": True}}
                ]
            },
            {"users": [{"name": "user", "user": {"unknown": True}}]},
            {"contexts": [{"name": "context", "context": {"unknown": True}}]},
            {
                "users": [
                    {
                        "name": "user",
                        "user": {"exec": {"command": "plugin", "unknown": True}},
                    }
                ]
            },
        ):
            with self.subTest(data=data), self.assertRaises(ValidationError):
                KubeConfig.model_validate(data)

    def test_exec_interactive_modes(self):
        for mode in ExecInteractiveModeEnum:
            with self.subTest(mode=mode):
                self.assertIs(
                    ExecConfig(
                        command="plugin", interactiveMode=mode.value
                    ).interactive_mode,
                    mode,
                )
        with self.assertRaises(ValidationError):
            ExecConfig(command="plugin", interactiveMode="Sometimes")


if __name__ == "__main__":
    unittest.main()
