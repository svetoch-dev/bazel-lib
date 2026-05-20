import unittest
from copy import deepcopy

from rod.libs.py.tf.output import (
    TfOutputNotFound,
    tf_output_find,
    tf_output_registries,
)


class TestTfOutputFind(unittest.TestCase):
    def test_finds_nested_value_while_ignoring_terraform_type_metadata(self):
        tf_output = {
            "registry_output": {
                "type": ["object", {"registries": ["map", "object"]}],
                "value": {
                    "registries": {
                        "containers": {
                            "endpoint": "example.com/containers",
                        },
                    },
                },
            },
        }

        self.assertEqual(
            tf_output_find(tf_output, "registries"),
            {
                "containers": {
                    "endpoint": "example.com/containers",
                },
            },
        )

    def test_does_not_mutate_supplied_output(self):
        tf_output = {
            "registry_output": {
                "type": ["object", {"registries": ["map", "object"]}],
                "value": {"registries": {}},
            },
        }
        original = deepcopy(tf_output)

        tf_output_find(tf_output, "registries")

        self.assertEqual(tf_output, original)

    def test_returns_none_when_key_is_missing(self):
        tf_output = {
            "registry_output": {
                "type": "string",
                "value": "not-a-registry-output",
            },
        }

        self.assertIsNone(tf_output_find(tf_output, "registries"))


class TestTfOutputRegistries(unittest.TestCase):
    def test_returns_registry_endpoints(self):
        tf_output = {
            "environment": {
                "type": "object",
                "value": {
                    "registries": {
                        "containers": {
                            "endpoint": "europe-west2-docker.pkg.dev/project/containers",
                            "repository_id": "containers",
                        },
                        "charts": {
                            "endpoint": "europe-west2-docker.pkg.dev/project/charts",
                            "repository_id": "charts",
                        },
                    },
                },
            },
        }

        self.assertEqual(
            tf_output_registries(tf_output),
            {
                "containers": {
                    "endpoint": "europe-west2-docker.pkg.dev/project/containers",
                },
                "charts": {
                    "endpoint": "europe-west2-docker.pkg.dev/project/charts",
                },
            },
        )

    def test_raises_when_registries_are_missing(self):
        with self.assertRaisesRegex(TfOutputNotFound, "'registries' not found"):
            tf_output_registries(
                {
                    "environment": {
                        "type": "object",
                        "value": {"name": "production"},
                    },
                }
            )
