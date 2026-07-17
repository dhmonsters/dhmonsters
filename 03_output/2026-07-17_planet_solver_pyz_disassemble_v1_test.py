# Python 3.13 코드 객체를 Python 3.14에서 분석할 때 역어셈블 실패를 안전하게 처리하는지 검증
import importlib.util
import marshal
import struct
import unittest
import zlib
from pathlib import Path


MODULE_PATH = Path(__file__).with_name("2026-07-17_planet_solver_pyz_disassemble_v1.py")
PYZ_PATH = Path(__file__).with_name(
    "2026-07-17_planet_solver_static_analysis_v1_extracted"
) / "Planet_solver_v1.0.5.exe" / "PYZ.pyz"


def load_analyzer():
    spec = importlib.util.spec_from_file_location("pyz_analyzer", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class DescribeCodeTests(unittest.TestCase):
    def test_preserves_structure_when_cross_version_disassembly_fails(self):
        raw = PYZ_PATH.read_bytes()
        toc_offset = struct.unpack("!I", raw[8:12])[0]
        toc = dict(marshal.loads(raw[toc_offset:]))
        _, position, length = toc["core.detector"]
        code = marshal.loads(zlib.decompress(raw[position:position + length]))

        result = load_analyzer().describe_code(code)

        def walk(node):
            yield node
            for child in node.get("children", []):
                yield from walk(child)

        self.assertEqual(result["name"], "<module>")
        self.assertTrue(result["children"])
        self.assertTrue(any("instructions_error" in node for node in walk(result)))


if __name__ == "__main__":
    unittest.main()
