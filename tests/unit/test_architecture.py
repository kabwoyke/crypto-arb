"""Structural rules from CLAUDE.md. These fail if the layering is broken."""

import ast
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[2] / "src" / "oddtrue"
EXCHANGE_NAMES = ("binance", "bitget")
NO_FLOAT_PACKAGES = ("engine", "ledger", "exchanges")


def _py_files(package: str) -> list[Path]:
    return sorted((SRC / package).rglob("*.py"))


def _imported_modules(path: Path) -> set[str]:
    tree = ast.parse(path.read_text())
    mods: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            mods.update(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            mods.add(node.module)
    return mods


def test_package_layout_matches_claude_md() -> None:
    expected = {
        "core", "exchanges", "marketdata", "math", "engine",
        "inventory", "ledger", "accounts", "api", "workers",
    }  # fmt: skip
    present = {p.name for p in SRC.iterdir() if p.is_dir() and not p.name.startswith("__")}
    assert expected <= present


@pytest.mark.parametrize("path", _py_files("math"), ids=lambda p: p.name)
def test_math_package_has_no_forbidden_imports(path: Path) -> None:
    forbidden = ("oddtrue.engine", "oddtrue.exchanges", "oddtrue.ledger")
    bad = [m for m in _imported_modules(path) if m.startswith(forbidden)]
    assert not bad, f"math/ must stay pure; {path.name} imports {bad}"


@pytest.mark.parametrize("path", _py_files("engine"), ids=lambda p: p.name)
def test_engine_never_imports_exchange_sdks_or_concrete_adapters(path: Path) -> None:
    bad = [
        m
        for m in _imported_modules(path)
        if m.startswith(tuple(f"oddtrue.exchanges.{n}" for n in EXCHANGE_NAMES))
    ]
    assert not bad, f"engine must use ExchangeAdapter only; {path.name} imports {bad}"


def test_exchange_names_appear_only_inside_exchanges_package() -> None:
    offenders: list[str] = []
    for pkg in (p.name for p in SRC.iterdir() if p.is_dir() and p.name not in {"exchanges"}):
        for path in _py_files(pkg):
            text = path.read_text().lower()
            offenders += [f"{path.relative_to(SRC)}:{n}" for n in EXCHANGE_NAMES if n in text]
    assert not offenders, offenders


@pytest.mark.parametrize("package", NO_FLOAT_PACKAGES)
def test_no_float_in_money_critical_packages(package: str) -> None:
    offenders: list[str] = []
    for path in _py_files(package):
        for node in ast.walk(ast.parse(path.read_text())):
            is_float_name = isinstance(node, ast.Name) and node.id == "float"
            is_float_literal = isinstance(node, ast.Constant) and isinstance(node.value, float)
            if is_float_name or is_float_literal:
                offenders.append(f"{path.relative_to(SRC)}:{node.lineno}")
    assert not offenders, f"float is banned in {package}/: {offenders}"
