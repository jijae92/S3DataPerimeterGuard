import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def load_policy(name: str) -> dict:
    path = PROJECT_ROOT / "policies" / name
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def test_scp_deny_external_principals():
    policy = load_policy("scp-deny-external.json")
    statement = policy["Statement"][0]
    assert statement["Effect"] == "Deny"
    assert statement["Resource"] == "*"
    condition = statement.get("Condition", {})
    assert "aws:PrincipalOrgID" in json.dumps(condition)


def test_scp_restrict_actions_contains_acl_controls():
    policy = load_policy("scp-restrict-s3-actions.json")
    statement = policy["Statement"][0]
    assert "s3:PutBucketAcl" in statement["Action"]
    assert "s3:DeleteBucketPolicy" in statement["Action"]
    assert statement["Effect"] == "Deny"
