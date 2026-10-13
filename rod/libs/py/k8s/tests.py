import unittest
from pathlib import Path


def load_tests(loader, tests, pattern):
    return loader.discover(
        start_dir=str(Path(__file__).parent),
        pattern="test_*.py",
    )


if __name__ == "__main__":
    unittest.main(verbosity=2)
