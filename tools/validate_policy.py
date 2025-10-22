"""Validate policy JSON files for structural integrity and common perimeter requirements."""
from __future__ import annotations

import argparse
import json
import logging
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Sequence

LOG = logging.getLogger("s3_data_perimeter.validate")
EFFECT_VALUES = {"Allow", "Deny"}


@dataclass(frozen=True)
class ValidationResult:
    path: Path
    errors: Sequence[str]

    @property
    def ok(self) -> bool:
        return not self.errors


def load_policy(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def validate_document(document: Mapping[str, Any], allow_placeholders: bool = False) -> List[str]:
    errors: List[str] = []
    if document.get("Version") not in {None, "2012-10-17"}:
        errors.append("Version should be 2012-10-17")

    statements = document.get("Statement")
    if not isinstance(statements, list) or not statements:
        errors.append("Statement must be a non-empty list")
        return errors

    for index, statement in enumerate(statements):
        errors.extend(validate_statement(statement, index))

    placeholders = find_placeholders(document)
    if placeholders and not allow_placeholders:
        errors.append(f"Unresolved template variables detected: {', '.join(sorted(placeholders))}")
    return errors


def validate_statement(statement: Any, index: int) -> List[str]:
    if not isinstance(statement, dict):
        return [f"Statement[{index}] must be an object"]

    errors: List[str] = []
    effect = statement.get("Effect")
    if effect not in EFFECT_VALUES:
        errors.append(f"Statement[{index}] Effect must be one of {sorted(EFFECT_VALUES)}")

    action = statement.get("Action")
    if not _is_string_or_string_list(action):
        errors.append(f"Statement[{index}] Action must be a string or list of strings")

    resource = statement.get("Resource")
    if not _is_string_or_string_list(resource):
        errors.append(f"Statement[{index}] Resource must be a string or list of strings")

    condition = statement.get("Condition")
    if condition is not None and not _is_condition(condition):
        errors.append(f"Statement[{index}] Condition must be an object of operator -> key/value mappings")

    return errors


def _is_string_or_string_list(value: Any) -> bool:
    if isinstance(value, str):
        return True
    if isinstance(value, list) and all(isinstance(item, str) for item in value):
        return True
    return False


def _is_condition(value: Any) -> bool:
    if not isinstance(value, dict):
        return False
    for operator, expression in value.items():
        if not isinstance(operator, str):
            return False
        if isinstance(expression, (str, bool)):
            continue
        if isinstance(expression, list) and all(isinstance(item, (str, bool)) for item in expression):
            continue
        if isinstance(expression, dict) and all(isinstance(k, str) for k in expression.keys()):
            if all(isinstance(v, (str, bool, list)) for v in expression.values()):
                continue
        return False
    return True


def find_placeholders(document: Mapping[str, Any]) -> List[str]:
    placeholders: List[str] = []

    def scan(value: Any) -> None:
        if isinstance(value, str) and "${" in value:
            placeholders.extend(part for part in value.split("${") if "}" in part)
            return
        if isinstance(value, dict):
            for item in value.values():
                scan(item)
        elif isinstance(value, list):
            for item in value:
                scan(item)

    scan(document)
    cleaned = []
    for item in placeholders:
        name = item.split("}", 1)[0]
        cleaned.append(name)
    return cleaned


def run_validations(paths: Iterable[Path]) -> List[ValidationResult]:
    results: List[ValidationResult] = []
    for path in paths:
        errors: List[str] = []
        try:
            document = load_policy(path)
        except json.JSONDecodeError as exc:
            errors.append(f"invalid JSON: {exc}")
        else:
            allow_placeholders = path.name.endswith(".base.json") or path.name.endswith(".exceptions.json")
            errors.extend(validate_document(document, allow_placeholders=allow_placeholders))
        results.append(ValidationResult(path=path, errors=errors))
    return results


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--file",
        dest="files",
        action="append",
        type=Path,
        default=[],
        help="Policy JSON file to validate (repeat for multiple files)",
    )
    parser.add_argument("paths", metavar="POLICY", type=Path, nargs="*", help="Policy JSON files to validate")
    parser.add_argument("--json", action="store_true", help="Emit JSON output")
    parser.add_argument("--verbose", action="store_true", help="Enable debug logging")
    parser.add_argument("--dry-run", action="store_true", help="Parse without returning non-zero on failure")
    return parser


def configure_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(level=level, format="%(levelname)s %(name)s - %(message)s")


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    configure_logging(args.verbose)

    targets: List[Path] = list(args.paths) + list(args.files)
    if not targets:
        parser.error("At least one policy file must be provided via --file or positional argument.")  # type: ignore[unreachable]

    results = run_validations(targets)
    failures = [result for result in results if not result.ok]

    payload = {
        "status": "success" if not failures else "failed",
        "validated": len(results),
        "failed": len(failures),
        "details": [
            {"path": str(result.path), "errors": list(result.errors)}
            for result in results
        ],
    }

    if args.json:
        sys.stdout.write(json.dumps(payload) + "\n")
    else:
        for result in results:
            if result.ok:
                sys.stdout.write(f"validate success: {result.path}\n")
            else:
                sys.stdout.write(
                    f"validate failed: {result.path} -> {len(result.errors)} issue(s): {', '.join(result.errors)}\n"
                )

    if failures and not args.dry_run:
        return 2

    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
