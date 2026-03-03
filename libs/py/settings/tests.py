import unittest
from libs.py.settings.tfvars import tfvars


class TestTfVarsSettings(unittest.TestCase):
    """Test suite test if the terraform.tfvars.json is parsed properly."""

    def test_tfvars_are_parsed(self):
        cfg = tfvars()

        assert cfg.envs != {}


if __name__ == "__main__":
    unittest.main()
