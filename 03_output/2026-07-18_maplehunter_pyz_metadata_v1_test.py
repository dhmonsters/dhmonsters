# 교차 버전 바이트코드 명령 해석 없이 코드 객체 구조를 추출하는 도구 검증
import importlib.util
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).with_name("2026-07-18_maplehunter_pyz_metadata_v1.py")


def load_analyzer():
    spec = importlib.util.spec_from_file_location("maplehunter_pyz_metadata", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class DescribeCodeMetadataTests(unittest.TestCase):
    def test_extracts_nested_structure_without_instruction_disassembly(self):
        code = compile(
            "LIMIT = 7\ndef climb(target_x):\n    return target_x + LIMIT\n",
            "sample.py",
            "exec",
        )

        result = load_analyzer().describe_code_metadata(code)

        self.assertEqual(result.get("filename"), "sample.py")
        self.assertIn("LIMIT", result.get("names", []))
        self.assertEqual(result.get("children", [{}])[0].get("name"), "climb")
        self.assertNotIn("instructions", result)


if __name__ == "__main__":
    unittest.main()
