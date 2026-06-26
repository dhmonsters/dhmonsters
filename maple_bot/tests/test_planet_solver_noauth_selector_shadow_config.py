# planet_solver_noauth의 selector shadow live 설정값을 검증합니다.
import ast
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _transparent_selector_shadow_calls():
    source = (ROOT / "planet_solver_noauth.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    calls = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if isinstance(func, ast.Name) and func.id == "TransparentSelectorShadow":
            calls.append(node)
    return calls


def _literal_keyword(call, name):
    for keyword in call.keywords:
        if keyword.arg == name:
            return ast.literal_eval(keyword.value)
    raise AssertionError(f"missing keyword: {name}")


class PlanetSolverNoauthSelectorShadowConfigTests(unittest.TestCase):
    def test_live_selector_shadow_uses_tuned_merge_gate_settings(self):
        calls = _transparent_selector_shadow_calls()

        self.assertEqual(len(calls), 1)
        call = calls[0]
        self.assertEqual(_literal_keyword(call, "merge_context_frames"), 6)
        self.assertEqual(_literal_keyword(call, "merge_min_size"), 175.0)
        self.assertEqual(_literal_keyword(call, "merge_size_ratio"), 1.30)


if __name__ == "__main__":
    unittest.main()
