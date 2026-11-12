"""AST-only import direction guard for the site backend and Fleet module.

This is a preventative architectural check, not a sandbox or security boundary.
It inspects regular imports, relative imports and literal dynamic imports;
computed imports and reflection cannot be proven safe by static scanning.
"""

from __future__ import annotations

import ast
import importlib.util
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, order=True)
class ImportViolation:
    path: str
    line: int
    imported: str
    reason: str

    def format(self) -> str:
        return f"{self.path}:{self.line}: {self.reason}: {self.imported}"


def _module_for(path: Path, package_root: Path, prefix: str) -> tuple[str, str]:
    relative = path.relative_to(package_root).with_suffix("")
    parts = relative.parts
    if parts[-1] == "__init__":
        name = ".".join((prefix, *parts[:-1]))
        return name, name
    name = ".".join((prefix, *parts))
    return name, name.rpartition(".")[0]


def _imports(tree: ast.AST, package: str) -> list[tuple[int, str]]:
    """Conservatively expand `from package import child` as potential module edges."""
    edges: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            edges.extend((node.lineno, alias.name) for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                target = importlib.util.resolve_name(
                    "." * node.level + (node.module or ""), package
                )
            else:
                target = node.module or ""
            # `from app import domain` only references app.domain; treating
            # the namespace package itself as a forbidden edge would be
            # a false positive for a valid domain-to-domain import.
            if target and (target != "app" or any(a.name == "*" for a in node.names)):
                edges.append((node.lineno, target))
            for alias in node.names:
                if target and alias.name != "*":
                    edges.append((node.lineno, f"{target}.{alias.name}"))
        elif isinstance(node, ast.Call) and node.args:
            # Literal importlib.import_module('...') / __import__('...').
            func = node.func
            is_import = (
                isinstance(func, ast.Name) and func.id in {"__import__", "import_module"}
            ) or (
                isinstance(func, ast.Attribute)
                and func.attr == "import_module"
                and isinstance(func.value, ast.Name)
                and func.value.id == "importlib"
            )
            literal = node.args[0]
            if is_import and isinstance(literal, ast.Constant) and isinstance(literal.value, str):
                name = literal.value
                if name.startswith("."):
                    # importlib.import_module('.child', package='...') needs a
                    # literal package; unknown expressions cannot be resolved.
                    for keyword in node.keywords:
                        if (
                            keyword.arg == "package"
                            and isinstance(keyword.value, ast.Constant)
                            and isinstance(keyword.value.value, str)
                        ):
                            name = importlib.util.resolve_name(name, keyword.value.value)
                            break
                    else:
                        continue
                edges.append((node.lineno, name))
    return sorted(set(edges))


def _at_or_below(name: str, prefix: str) -> bool:
    return name == prefix or name.startswith(prefix + ".")


def _type_only_import_lines(tree: ast.AST) -> set[int]:
    """Find imports under recognized typing guards, not runtime if/else arms.

    This exemption applies only to the NEW site rules. Existing domain,
    repository and Fleet restrictions remain unchanged.
    """
    type_checking_names: set[str] = set()
    typing_names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module == "typing":
            type_checking_names.update(
                alias.asname or alias.name for alias in node.names if alias.name == "TYPE_CHECKING"
            )
        elif isinstance(node, ast.Import):
            typing_names.update(
                alias.asname or alias.name for alias in node.names if alias.name == "typing"
            )

    def is_typing_guard(condition: ast.expr) -> bool:
        return (isinstance(condition, ast.Name) and condition.id in type_checking_names) or (
            isinstance(condition, ast.Attribute)
            and condition.attr == "TYPE_CHECKING"
            and isinstance(condition.value, ast.Name)
            and condition.value.id in typing_names
        )

    lines: set[int] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.If) or not is_typing_guard(node.test):
            continue
        for statement in node.body:
            for descendant in ast.walk(statement):
                if isinstance(descendant, (ast.Import, ast.ImportFrom, ast.Call)):
                    lines.add(descendant.lineno)
    return lines


def _reason(module: str, imported: str) -> str | None:
    if _at_or_below(module, "app.repositories") and any(
        _at_or_below(imported, target) for target in ("app.services", "app.api")
    ):
        return "repository must not depend on application services or API"

    if (
        _at_or_below(module, "app.domain")
        and _at_or_below(imported, "app")
        and not _at_or_below(imported, "app.domain")
    ):
        return "domain must not depend on application or infrastructure"

    if _at_or_below(module, "app.services") and _at_or_below(imported, "app.api"):
        return "site service must not depend on HTTP API"

    if _at_or_below(module, "app.rag") and any(
        _at_or_below(imported, target) for target in ("app.api", "app.services")
    ):
        return "RAG implementation must not depend on HTTP API or services"

    if _at_or_below(module, "app.llm") and _at_or_below(imported, "app.api"):
        return "LLM provider must not depend on HTTP API"

    if _at_or_below(module, "fleet_hub.services") and (
        _at_or_below(imported, "fleet_hub.api") or _at_or_below(imported, "app.api")
    ):
        return "Fleet service must not depend on HTTP API"

    if _at_or_below(module, "fleet_hub.api") and _at_or_below(imported, "fleet_hub.api"):
        parts = imported.split(".")
        if len(parts) < 3:
            return None  # Importing the API package alone is not a router edge.
        target = ".".join(parts[:3])
        if target in {"fleet_hub.api.dependencies", "fleet_hub.api.__init__"}:
            return None
        if module == target or module.startswith(target + "."):
            return None
        return "Fleet router must not import another router"

    return None


def scan_import_boundaries(repo_root: Path) -> list[ImportViolation]:
    """Scan each owned Python package. Missing roots and syntax errors fail closed."""
    repo_root = repo_root.resolve()
    roots = (
        (repo_root / "backend/app/domain", "app", repo_root / "backend/app"),
        (repo_root / "backend/app/repositories", "app", repo_root / "backend/app"),
        (repo_root / "backend/app/services", "app", repo_root / "backend/app"),
        (repo_root / "backend/app/rag", "app", repo_root / "backend/app"),
        (repo_root / "backend/app/llm", "app", repo_root / "backend/app"),
        (
            repo_root / "portfolio/fleet_hub/backend/src/fleet_hub/api",
            "fleet_hub",
            repo_root / "portfolio/fleet_hub/backend/src/fleet_hub",
        ),
        (
            repo_root / "portfolio/fleet_hub/backend/src/fleet_hub/services",
            "fleet_hub",
            repo_root / "portfolio/fleet_hub/backend/src/fleet_hub",
        ),
    )
    failures: list[ImportViolation] = []
    for folder, prefix, package_root in roots:
        if not folder.is_dir():
            raise FileNotFoundError(f"Required architecture root missing: {folder}")
        files = sorted(folder.rglob("*.py"))
        if not files:
            raise FileNotFoundError(f"No Python modules in architecture root: {folder}")
        for path in files:
            module, package = _module_for(path, package_root, prefix)
            relative = path.relative_to(repo_root).as_posix()
            tree = ast.parse(path.read_text(encoding="utf-8-sig"), filename=relative)
            type_only_lines = _type_only_import_lines(tree)
            for line, imported in _imports(tree, package):
                reason = _reason(module, imported)
                if (
                    reason
                    and line in type_only_lines
                    and any(
                        _at_or_below(module, layer)
                        for layer in ("app.services", "app.rag", "app.llm")
                    )
                ):
                    continue
                if reason:
                    failures.append(ImportViolation(relative, line, imported, reason))
    return sorted(set(failures))


def main() -> int:
    repo_root = Path(__file__).resolve().parents[2]
    try:
        failures = scan_import_boundaries(repo_root)
    except (SyntaxError, OSError, ImportError, ValueError) as exc:
        print(f"Import boundary check failed to scan: {exc}")
        return 1
    if failures:
        print(f"Import boundaries: FAIL ({len(failures)} forbidden imports)")
        for failure in failures:
            print(f"  {failure.format()}")
        return 1
    print("Import boundaries: PASS (domain, repositories, site services/RAG/LLM, Fleet)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
