import json
import sys
from datetime import date
from pathlib import Path
from typing import Any, Dict, Iterable, Optional

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tools.merge_policy import (  # pylint: disable=wrong-import-position
    ExceptionEntry,
    MergeResult,
    PolicyMergeError,
    _ensure_variables,
    load_exceptions,
    load_policy,
    merge_policies,
    parse_variables,
)

POLICIES_DIR = PROJECT_ROOT / "policies"
SAMPLE_FIXTURES = PROJECT_ROOT / "tests" / "fixtures" / "sample-requests.json"


@pytest.fixture(scope="module")
def base_policy() -> Dict[str, Any]:
    return load_policy(POLICIES_DIR / "bucket-policy.base.json")


@pytest.fixture(scope="module")
def variables() -> Dict[str, str]:
    return _ensure_variables(
        parse_variables(
            [
                "BucketName=example-data-perimeter-bucket",
                "BucketArn=arn:aws:s3:::example-data-perimeter-bucket",
                "OrgId=o-exampleorg",
                "VpcEndpointId=vpce-00000000000000000",
            ]
        )
    )


@pytest.fixture()
def merged_policy_active(base_policy: Dict[str, Any], variables: Dict[str, str]) -> Dict[str, Any]:
    exceptions = load_exceptions(POLICIES_DIR / "bucket-policy.exceptions.json", current_date=date(2025, 1, 1))
    result: MergeResult = merge_policies(base_policy, exceptions, variables)
    return result.policy


@pytest.fixture()
def merged_policy_no_exceptions(base_policy: Dict[str, Any], variables: Dict[str, str]) -> Dict[str, Any]:
    result: MergeResult = merge_policies(base_policy, [], variables)
    return result.policy


def load_sample_requests() -> Iterable[Dict[str, Any]]:
    with SAMPLE_FIXTURES.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def evaluate_access(policy: Dict[str, Any], request: Dict[str, Any]) -> bool:
    """
    Simplified IAM policy evaluation sufficient for the unit-test scenarios.
    Deny overrides Allow; statements are checked in document order.
    """

    def matches_action(action_spec: Any, action: str) -> bool:
        if isinstance(action_spec, str):
            return action_spec == action or action_spec == "s3:*"
        if isinstance(action_spec, list):
            return any(matches_action(item, action) for item in action_spec)
        return False

    def matches_resource(resource_spec: Any, resource: str) -> bool:
        if isinstance(resource_spec, str):
            if resource_spec.endswith("*"):
                prefix = resource_spec[:-1]
                return resource.startswith(prefix)
            return resource_spec == resource
        if isinstance(resource_spec, list):
            return any(matches_resource(item, resource) for item in resource_spec)
        return False

    def matches_principal(principal_spec: Any, principal_arn: str, is_anonymous: bool) -> bool:
        if principal_spec == "*":
            return True
        if isinstance(principal_spec, dict):
            if "AWS" in principal_spec:
                spec = principal_spec["AWS"]
                if isinstance(spec, list):
                    return principal_arn in spec
                return spec == principal_arn
        if is_anonymous:
            return principal_spec == {"AWS": "*"}
        return False

    def get_context_value(key: str, request_context: Dict[str, Any]) -> Optional[str]:
        return request_context.get(key)

    def condition_matches(condition: Dict[str, Any], request_context: Dict[str, Any]) -> bool:
        for operator, expression in condition.items():
            if operator == "StringEquals":
                for key, expected in expression.items():
                    actual = get_context_value(key, request_context)
                    if isinstance(expected, list):
                        if actual not in expected:
                            return False
                    else:
                        if actual != expected:
                            return False
            elif operator == "StringNotEquals":
                for key, expected in expression.items():
                    actual = get_context_value(key, request_context)
                    if isinstance(expected, list):
                        if actual in expected:
                            return False
                    else:
                        if actual == expected:
                            return False
            elif operator == "Bool":
                for key, expected in expression.items():
                    actual = get_context_value(key, request_context)
                    if isinstance(expected, bool):
                        expected_val = expected
                    else:
                        expected_val = expected.lower() == "true"
                    actual_val = str(actual).lower() == "true"
                    if actual_val != expected_val:
                        return False
            elif operator == "StringEqualsIfPresent":
                for key, expected in expression.items():
                    actual = get_context_value(key, request_context)
                    if actual is None:
                        continue
                    if isinstance(expected, list):
                        if actual not in expected:
                            return False
                    else:
                        if actual != expected:
                            return False
            else:
                raise AssertionError(f"Unsupported condition operator for test harness: {operator}")
        return True

    request_context = {
        "aws:PrincipalOrgID": request.get("principalOrgId"),
        "aws:SourceVpce": request.get("sourceVpce"),
        "aws:SecureTransport": str(request.get("secureTransport", True)).lower(),
        "aws:PrincipalType": "Anonymous" if request.get("isAnonymous") else "AWS",
    }
    principal_arn = request.get("principalArn", "arn:aws:iam::external:role/Unknown")
    resource = request.get("resource")
    action = request.get("action")
    is_anonymous = request.get("isAnonymous", False)

    deny_match = False
    allow_match = False

    for statement in policy.get("Statement", []):
        if not matches_action(statement.get("Action"), action):
            continue
        if not matches_resource(statement.get("Resource"), resource):
            continue
        if not matches_principal(statement.get("Principal"), principal_arn, is_anonymous):
            continue
        condition = statement.get("Condition")
        if condition and not condition_matches(condition, request_context):
            continue
        effect = statement.get("Effect")
        if effect == "Deny":
            deny_match = True
        elif effect == "Allow":
            allow_match = True

    if deny_match:
        return False
    return allow_match


@pytest.mark.parametrize(
    "request_key",
    [
        "org_mismatch",
        "vpce_mismatch",
        "anonymous_access",
        "exception_allowed",
        "exception_prefix_miss",
        "secure_transport_false",
    ],
)
def test_requests_present_in_fixtures(request_key: str) -> None:
    identifiers = {entry["id"] for entry in load_sample_requests()}
    assert request_key in identifiers


def get_request(request_id: str) -> Dict[str, Any]:
    for entry in load_sample_requests():
        if entry["id"] == request_id:
            return entry
    raise KeyError(request_id)


def test_org_id_mismatch_denied(merged_policy_no_exceptions: Dict[str, Any]) -> None:
    request = get_request("org_mismatch")
    assert evaluate_access(merged_policy_no_exceptions, request) is False


def test_vpce_mismatch_denied(merged_policy_no_exceptions: Dict[str, Any]) -> None:
    request = get_request("vpce_mismatch")
    assert evaluate_access(merged_policy_no_exceptions, request) is False


def test_public_anonymous_denied(merged_policy_no_exceptions: Dict[str, Any]) -> None:
    request = get_request("anonymous_access")
    assert evaluate_access(merged_policy_no_exceptions, request) is False


def test_exception_allows_specific_principal(merged_policy_active: Dict[str, Any]) -> None:
    request = get_request("exception_allowed")
    policy = strip_general_allow(merged_policy_active)
    assert evaluate_access(policy, request) is True


def test_exception_scope_not_widened(merged_policy_active: Dict[str, Any]) -> None:
    request = get_request("exception_prefix_miss")
    policy = strip_general_allow(merged_policy_active)
    assert evaluate_access(policy, request) is False


def test_expired_exception_causes_failure(tmp_path: Path) -> None:
    payload = {
        "Exceptions": [
            {
                "principalArn": "arn:aws:iam::123456789012:role/PartnerAnalytics",
                "actions": ["s3:GetObject"],
                "prefix": "team-a/*",
                "expiresAt": "2024-01-01",
                "reason": "expired test entry",
            }
        ]
    }
    path = tmp_path / "expired.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(PolicyMergeError):
        load_exceptions(path, date(2025, 1, 1))


def test_secure_transport_required(merged_policy_no_exceptions: Dict[str, Any]) -> None:
    request = get_request("secure_transport_false")
    assert evaluate_access(merged_policy_no_exceptions, request) is False
def strip_general_allow(policy: Dict[str, Any]) -> Dict[str, Any]:
    filtered = [
        stmt
        for stmt in policy.get("Statement", [])
        if stmt.get("Sid") != "AllowOrgAccessViaVpce"
    ]
    new_policy = dict(policy)
    new_policy["Statement"] = filtered
    return new_policy
