# Python 3.13 PYC 메타데이터 추출기의 안전한 구조화를 검증하는 테스트
import importlib.util
import marshal
import tempfile
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).with_name("2026-07-19_maplehunter_pyc_metadata_v1.py")


def load_target():
    spec = importlib.util.spec_from_file_location("maplehunter_pyc_metadata", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class PycMetadataTest(unittest.TestCase):
    def test_extracts_nested_code_without_executing_it(self):
        module = load_target()
        code = compile("VALUE = 7\ndef route(x):\n    return x + VALUE\n", "sample.py", "exec")
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "sample.pyc"
            path.write_bytes(b"\0" * 16 + marshal.dumps(code))
            result = module.extract_pyc(path)

        self.assertEqual(result["code"]["filename"], "sample.py")
        self.assertIn("VALUE", result["code"]["names"])
        self.assertEqual(result["code"]["children"][0]["name"], "route")


if __name__ == "__main__":
    unittest.main()
