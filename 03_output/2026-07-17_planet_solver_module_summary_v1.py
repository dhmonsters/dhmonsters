# 추출한 Planet Solver 모듈 구조에서 함수와 핵심 상수만 간결하게 요약하는 도구
import argparse
import json
import re
from pathlib import Path


KEYWORDS = re.compile(
    r"(?i)(http|firebase|api|auth|license|token|hwid|planet|solver|capture|screen|window|"
    r"mouse|click|gpu|vulkan|model|hyung|\.param|\.bin|f1|maple|driver|update|download|"
    r"version|macro|shape|rectangle|triangle|circle|ncnn|yolo|mss|printwindow)"
)


def walk(code, depth=0):
    yield depth, code
    for child in code.get("children", []):
        yield from walk(child, depth + 1)


def flatten_strings(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, list):
        for item in value:
            yield from flatten_strings(item)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path)
    args = parser.parse_args()
    modules = json.loads(args.input.read_text(encoding="utf-8"))
    for module_name, module in modules.items():
        print(f"### {module_name}")
        for depth, code in walk(module["code"]):
            if code["name"] == "<module>":
                continue
            variables = ", ".join(code.get("varnames", [])[:14])
            print(f"{'  ' * depth}{code['qualname']}({variables})")
        print("KEY CONSTANTS")
        found = set()
        for _, code in walk(module["code"]):
            for text in flatten_strings(code.get("constants", [])):
                compact = " ".join(text.split())
                if KEYWORDS.search(compact) and compact not in found:
                    found.add(compact)
                    print(compact[:600])
        print()


if __name__ == "__main__":
    main()
