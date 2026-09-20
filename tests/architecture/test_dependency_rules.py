"""Fitness function: source-code dependencies must point inward.

    composition_root -> infrastructure -> application -> domain

Parses every module's imports (no code is executed) and fails on any forbidden edge.
"""

import ast
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
OWN_PACKAGES = {"domain", "application", "infrastructure", "composition_root", "main_flow"}
# Cross-cutting logging/tracing library shared by every microservice (replaces stdlib logging).
SHARED_LIBRARIES = {"shared_logging"}
FRAMEWORKS = {
    "fastapi",
    "starlette",
    "pydantic",
    "uvicorn",
    "sounddevice",
    "numpy",
    "httpx",
    "dotenv",
}


def imported_modules(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            assert node.level == 0, f"{path}: relative imports are not allowed"
            modules.add(node.module or "")
    return modules


def python_files(package: str, subpackage: str = "") -> list[Path]:
    base = ROOT / package / subpackage
    return sorted(p for p in base.rglob("*.py") if "__pycache__" not in p.parts)


def violations(
    files: list[Path], forbidden_prefixes: set[str], allow_third_party: bool
) -> list[str]:
    problems = []
    for path in files:
        for module in imported_modules(path):
            top = module.split(".")[0]
            forbidden = any(module == p or module.startswith(p + ".") for p in forbidden_prefixes)
            third_party = (
                top not in sys.stdlib_module_names
                and top not in OWN_PACKAGES
                and top not in SHARED_LIBRARIES
            )
            if forbidden or (third_party and not allow_third_party):
                problems.append(f"{path.relative_to(ROOT)} imports {module}")
    return problems


def test_domain_depends_on_nothing_but_the_standard_library():
    files = python_files("domain")
    assert files, "domain package not found"
    problems = violations(
        files, {"application", "infrastructure", "composition_root"}, allow_third_party=False
    )
    assert not problems, "\n".join(problems)


def test_application_does_not_depend_on_infrastructure_or_frameworks():
    files = python_files("application")
    assert files
    problems = violations(
        files,
        {"infrastructure", "composition_root"} | FRAMEWORKS,
        allow_third_party=False,
    )
    assert not problems, "\n".join(problems)


def test_inbound_adapters_do_not_touch_outbound_adapters_or_the_composition_root():
    files = python_files("infrastructure", "inbound")
    assert files
    problems = violations(
        files, {"infrastructure.outbound", "composition_root"}, allow_third_party=True
    )
    assert not problems, "\n".join(problems)


def test_outbound_adapters_do_not_touch_inbound_adapters_or_the_composition_root():
    files = python_files("infrastructure", "outbound")
    assert files
    problems = violations(
        files, {"infrastructure.inbound", "composition_root"}, allow_third_party=True
    )
    assert not problems, "\n".join(problems)


@pytest.mark.parametrize("package", ["domain", "application", "infrastructure"])
def test_nothing_below_the_composition_root_imports_it(package):
    problems = violations(python_files(package), {"composition_root"}, allow_third_party=True)
    assert not problems, "\n".join(problems)


def test_main_flow_does_not_import_adapters():
    problems = violations(
        python_files("main_flow"),
        {"infrastructure.inbound", "infrastructure.outbound"},
        allow_third_party=True,
    )
    assert not problems, "\n".join(problems)


@pytest.mark.parametrize("package", ["domain", "application", "composition_root", "main_flow"])
def test_no_print_calls_outside_infrastructure(package):
    problems = []
    for path in python_files(package):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == "print"
            ):
                problems.append(f"{path.relative_to(ROOT)}:{node.lineno} calls print()")
    assert not problems, "\n".join(problems)


def test_no_utils_common_or_helpers_modules():
    banned = {"utils", "common", "helpers"}
    problems = []
    for package in ("domain", "application", "infrastructure", "composition_root", "main_flow"):
        for path in python_files(package):
            parts = {p.removesuffix(".py") for p in path.relative_to(ROOT).parts}
            if parts & banned:
                problems.append(str(path.relative_to(ROOT)))
    assert not problems, "\n".join(problems)
