import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from rod.libs.py.tf.tfvars import CloudTypeEnum
from rod.scripts.init.argocd.prepare import copy as copy_step


class TestCopyTemplate(unittest.TestCase):
    """
    Verify Argo CD template selection and preservation of existing environments.
    """

    def setUp(self):
        """
        Create distinct internal and product templates in a temporary workspace.
        """
        self.root = Path(self.enterContext(tempfile.TemporaryDirectory()))
        for template in ("int", "product"):
            folder = self.root / template / "argocd"
            folder.mkdir(parents=True)
            (folder / "values.yaml").write_text(template, encoding="utf-8")
        self.enterContext(patch.object(copy_step, "PRODUCT_DIR", self.root / "product"))
        self.enterContext(patch.object(copy_step, "INTERNAL_DIR", self.root / "int"))
        self.enterContext(
            patch.object(
                copy_step,
                "common_paths",
                SimpleNamespace(argocd_environments_dir=str(self.root)),
            )
        )
        self.enterContext(
            patch.object(
                copy_step,
                "formatted_tfvars",
                return_value=SimpleNamespace(
                    envs={
                        "internal": SimpleNamespace(
                            type="internal",
                            short_name="int",
                            cloud=SimpleNamespace(name=CloudTypeEnum.gcp),
                        ),
                        "development": SimpleNamespace(
                            type="product",
                            short_name="dev",
                            cloud=SimpleNamespace(name=CloudTypeEnum.yc),
                        ),
                    }
                ),
            )
        )

    def test_copies_matching_templates_and_preserves_edits_on_rerun(self):
        """
        Verify both template types are copied and rerunning preserves user edits.
        """
        copy_step.copy_template()
        internal = self.root / "gcp-int" / "argocd" / "values.yaml"
        product = self.root / "yc-dev" / "argocd" / "values.yaml"
        self.assertEqual(internal.read_text(), "int")
        self.assertEqual(product.read_text(), "product")
        product.write_text("custom values", encoding="utf-8")

        copy_step.copy_template()

        self.assertEqual(product.read_text(), "custom values")
        self.assertEqual(internal.read_text(), "int")

    def test_missing_templates_exit_before_copying(self):
        """
        Verify either missing template causes failure without partial copies.
        """
        for attribute in ("PRODUCT_DIR", "INTERNAL_DIR"):
            with self.subTest(attribute=attribute), patch.object(
                copy_step, attribute, self.root / "missing"
            ):
                with self.assertRaises(SystemExit) as raised:
                    copy_step.copy_template()
                self.assertEqual(raised.exception.code, 1)
                self.assertFalse((self.root / "gcp-int").exists())
                self.assertFalse((self.root / "yc-dev").exists())
