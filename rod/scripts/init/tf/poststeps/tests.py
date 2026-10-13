import unittest
import sys
from pathlib import Path


if __name__ == "__main__":
    suite = unittest.defaultTestLoader.discover(
        start_dir=str(Path(__file__).resolve().parent),
        pattern="test_*.py",
    )
    result = unittest.TextTestRunner(verbosity=2).run(suite)

    if result.wasSuccessful():
        sys.exit(0)
    else:
        sys.exit(1)
