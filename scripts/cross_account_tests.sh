#!/usr/bin/env bash
set -euo pipefail

# Simple integration smoke test to verify cross-account behavior using the merged policy.
# Requires the merged policy to be generated beforehand via tools/merge_policy.py.

if [[ $# -lt 1 ]]; then
  echo "Usage: $0 <external-profile> [partner-profile]" >&2
  exit 1
fi

EXTERNAL_PROFILE="$1"
PARTNER_PROFILE="${2:-$1}"
: "${BUCKET_NAME:?Set BUCKET_NAME to the protected bucket name}"
: "${TEST_OBJECT_KEY:=team-a/allowlisted-object.txt}"
: "${DENY_OBJECT_KEY:=team-b/restricted-object.txt}"

log() {
  printf '[cross-account-test] %s\n' "$*"
}

expect_access_denied() {
  local profile="$1"
  local key="$2"
  set +e
  aws s3api get-object --profile "$profile" --bucket "$BUCKET_NAME" --key "$key" /tmp/policy-test.$$.bin >/dev/null 2>&1
  local status=$?
  rm -f /tmp/policy-test.$$.bin
  set -e
  if [[ $status -eq 0 ]]; then
    log "Expected AccessDenied for profile=$profile key=$key but call succeeded"
    exit 1
  fi
  log "Access correctly denied for profile=$profile key=$key"
}

expect_access_allowed() {
  local profile="$1"
  local key="$2"
  aws s3api get-object --profile "$profile" --bucket "$BUCKET_NAME" --key "$key" /tmp/policy-test.$$.bin >/dev/null
  rm -f /tmp/policy-test.$$.bin
  log "Access allowed for profile=$profile key=$key"
}

log "Validating AccessDenied for external principal before exceptions"
expect_access_denied "$EXTERNAL_PROFILE" "$TEST_OBJECT_KEY"
aws s3api list-objects-v2 --profile "$EXTERNAL_PROFILE" --bucket "$BUCKET_NAME" >/dev/null 2>&1 || log "ListObjects denied as expected"

log "Validating scoped exception access"
expect_access_allowed "$PARTNER_PROFILE" "$TEST_OBJECT_KEY"
expect_access_denied "$PARTNER_PROFILE" "$DENY_OBJECT_KEY"

log "Tests complete"
