"""Find source responsibilities without importing the app or model runtimes.

Examples:
    python tools/code_index.py
    python tools/code_index.py realtime
    python tools/code_index.py _save_config --json
"""
from __future__ import annotations

import argparse
import ast
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "src" / "osr_screen_tcode"


def source_index() -> list[dict]:
    """Return module descriptions and declared methods from source text only."""
    result = []
    for path in sorted(SOURCE.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8-sig"), filename=str(path))
        relative = path.relative_to(ROOT).as_posix()
        functions = []
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                functions.append({"name": node.name, "line": node.lineno,
                                  "signature": f"{node.name}({ast.unparse(node.args)})"})
            elif isinstance(node, ast.ClassDef):
                for method in node.body:
                    if isinstance(method, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        name = f"{node.name}.{method.name}"
                        functions.append({"name": name, "line": method.lineno,
                                          "signature": f"{name}({ast.unparse(method.args)})"})
        result.append({"file": relative, "description": (ast.get_docstring(tree) or "").split("\n")[0],
                       "functions": functions})
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("query", nargs="?", default="", help="Part of a module path or function name.")
    parser.add_argument("--json", action="store_true", help="Emit a machine-readable index.")
    args = parser.parse_args()
    query = args.query.casefold()
    selected = []
    for item in source_index():
        if not query or query in item["file"].casefold():
            selected.append(item)
        else:
            matches = [entry for entry in item["functions"] if query in entry["name"].casefold()]
            if matches:
                selected.append({**item, "functions": matches})
    if args.json:
        print(json.dumps(selected, ensure_ascii=False, indent=2))
        return
    for item in selected:
        print(f"{item['file']} — {item['description']}")
        if query:
            for function in item["functions"]:
                print(f"  {function['line']}: {function['signature']}")
        else:
            print(f"  {len(item['functions'])} functions/methods")


if __name__ == "__main__":
    main()
