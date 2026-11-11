import ast
from pathlib import Path

import bracket


def test_production_code_does_not_import_tests() -> None:
    """
    Production code must not depend on the `tests` package (e.g. mock timestamps).
    """
    offenders = []
    for path in Path(bracket.__file__).parent.rglob("*.py"):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.ImportFrom) and (node.module or "").split(".")[0] == "tests":
                offenders.append(f"{path}:{node.lineno}")
            elif isinstance(node, ast.Import) and any(
                alias.name.split(".")[0] == "tests" for alias in node.names
            ):
                offenders.append(f"{path}:{node.lineno}")

    assert not offenders, offenders
