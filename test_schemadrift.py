import importlib.util
import pathlib
import sys
import unittest


ROOT = pathlib.Path(__file__).resolve().parent
TEST_PATH = ROOT / "tests" / "test_schemadrift.py"
SPEC = importlib.util.spec_from_file_location("schemadrift_fixture_tests", TEST_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)
globals().update(
    {name: getattr(MODULE, name) for name in dir(MODULE) if name.endswith("Test")}
)


if __name__ == "__main__":
    unittest.main(module=SPEC.name, verbosity=2)
