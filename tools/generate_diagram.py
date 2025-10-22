"""Generate a Mermaid diagram describing the S3 data perimeter flow."""
from __future__ import annotations

import argparse
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping

from merge_policy import (
    _ensure_variables,
    load_exceptions,
    load_policy,
    parse_variables,
    MergeResult,
    merge_policies,
)

LOG = logging.getLogger("s3_data_perimeter.diagram")
DEFAULT_OUTPUT = Path("docs/diagrams.mmd")


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", type=Path, default=Path("policies/bucket-policy.base.json"), help="Baseline policy JSON")
    parser.add_argument(
        "--exceptions",
        type=Path,
        default=Path("policies/bucket-policy.exceptions.json"),
        help="Exceptions JSON",
    )
    parser.add_argument("--out", type=Path, default=DEFAULT_OUTPUT, help="Destination Mermaid file")
    parser.add_argument(
        "--vars",
        metavar="KEY=VALUE",
        nargs="*",
        default=[],
        help="Template vars (repeat or comma separated)",
    )
    parser.add_argument("--verbose", action="store_true", help="Enable verbose logging")
    parser.add_argument(
        "--now",
        default=None,
        help="Override current date (YYYY-MM-DD) for deterministic rendering",
    )
    return parser


def configure_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(level=level, format="%(levelname)s %(name)s - %(message)s")


def main(argv: Iterable[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    configure_logging(args.verbose)

    variables = _ensure_variables(parse_variables(args.vars))
    current_date = (
        datetime.strptime(args.now, "%Y-%m-%d").date() if args.now else datetime.now(timezone.utc).date()
    )

    base_policy = load_policy(args.base)
    exceptions = load_exceptions(args.exceptions, current_date)
    merge_result: MergeResult = merge_policies(base_policy, exceptions, variables)

    diagram = build_mermaid(merge_result.policy, exceptions, variables)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(diagram, encoding="utf-8")
    LOG.info("diagram generated at %s", args.out)
    return 0


def build_mermaid(
    policy: Mapping[str, Any],
    exceptions: Iterable[Any],
    variables: Mapping[str, str],
) -> str:
    org_id = variables["OrgId"]
    vpce_id = variables["VpcEndpointId"]
    bucket_name = variables["BucketName"]

    lines: List[str] = [
        "graph TD",
        f"    POrg[Principal in Org ({org_id})] -->|Request via trusted network| VPC[Approved VPC Endpoint {vpce_id}]",
        "    VPC -->|aws:SourceVpce match| Policy{Bucket Policy Evaluation}",
        f"    Policy -->|Allow Get/List| Bucket[S3 Bucket {bucket_name}]",
        "    PExt[Principal outside Org] -.Denied (Org mismatch).-> Policy",
        "    PVPC[Principal via other VPCe] -.Denied (VPCe mismatch).-> Policy",
    ]

    active_exceptions = list(exceptions)
    for index, entry in enumerate(active_exceptions):
        principal = entry.principal_arn if hasattr(entry, "principal_arn") else entry.get("principalArn")
        prefix = entry.prefix if hasattr(entry, "prefix") else entry.get("prefix")
        actions = entry.actions if hasattr(entry, "actions") else entry.get("actions", [])
        label_actions = ",".join(actions) if actions else "s3:GetObject"
        node_name = f"Exc{index + 1}"
        lines.append(
            f"    {node_name}[Approved Exception: {principal}] -->|Allow {label_actions} on {prefix}| Policy"
        )
        lines.append(f"    class {node_name} exception;")

    lines.extend(
        [
            "    classDef exception fill:#D5F5E3,stroke:#1E8449,stroke-width:2px;",
            "    classDef deny fill:#FADBD8,stroke:#C0392B,stroke-width:2px,stroke-dasharray: 5 5;",
            "    class PExt,PVPC deny;",
        ]
    )

    return "\n".join(lines) + "\n"


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
