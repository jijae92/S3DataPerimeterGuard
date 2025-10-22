# S3 Data-Perimeter Guard – Operations Guide

## Architecture Overview
The guard enforces an S3-centric perimeter layered across identity, network, and administration controls:

- **Bucket policy** combines OrgId (`aws:PrincipalOrgID`) and VPC endpoint (`aws:SourceVpce`) restrictions, blocks public/anonymous access, and denies ACL/policy mutations.
- **Service control policies** extend protection to the organization: `scp-deny-external.json` blocks out-of-org access, while `scp-restrict-s3-actions.json` denies risky S3 administration except for designated roles.
- **Exception handling** is centralised through `.exception-requests/*.json` and merged into `policies/bucket-policy.base.json` by `tools/merge_policy.py`.
- **Pipeline automation** (CodePipeline + CodeBuild + Manual Approval + CDK deploy) validates, tests, and deploys the guardrails.

View the control flow diagram in [`docs/diagrams.mmd`](./diagrams.mmd) or regenerate via `python tools/generate_diagram.py ...`.

## Data Perimeter Principles
1. **Organizational scope** – Only principals from `${OrgId}` may access bucket resources.
2. **Network guardrail** – Traffic must originate from the approved interface VPC endpoint `${VpcEndpointId}`.
3. **Public exposure blocked** – Anonymous/public access and ACL/policy overrides are denied.
4. **Transport hygiene** – `aws:SecureTransport = false` requests are denied to enforce TLS (optional but recommended).
5. **Encryption guidance** – PutObject callers should set `x-amz-server-side-encryption` (AES256 or aws:kms), enforced via exceptions when applicable.

## Local Execution Workflow
```bash
# 1. Environment prep
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
npm ci --prefix iac/cdk

# 2. Merge and validate policies
python tools/merge_policy.py \
  --base policies/bucket-policy.base.json \
  --exceptions policies/bucket-policy.exceptions.json \
  --requests-dir .exception-requests \
  --out build/bucket-policy.merged.json \
  --vars BucketName=<bucket>,OrgId=<org>,VpcEndpointId=<vpce>
python tools/validate_policy.py --file build/bucket-policy.merged.json

# 3. Synthesize CDK with explicit context
npx cdk synth \
  -c bucketName=<bucket> \
  -c orgId=<org> \
  -c vpcEndpointId=<vpce>
```
Optional: `pytest -q` to exercise the policy evaluator and exception expiry tests.

## Pipeline Integration & Least-Privilege Guidance
- **Required parameters**: `ORG_ID`, `VPCe_ID`, `BUCKET_NAME`, `BUCKET_ARN` feed CodeBuild/CodePipeline via parameter overrides.
- **Buildspec** automates validation (`tools/validate_policy.py --file ...`) and fails on malformed or expired exception requests.
- **Manual approval** stage displays statement and exception counts (`STATEMENT_COUNT`, `EXCEPTION_COUNT`) exported from CodeBuild. Security reviewers approve only when the summary matches expectations.
- **IAM scoping**: grant CodeBuild the minimum necessary IAM permissions (CloudWatch logs, artifact bucket, CDK deployment role). Use dedicated roles for the pipeline and avoid wildcard `*` resource policies wherever feasible.

## Exception Lifecycle
1. **Request submission**: Teams add JSON to `.exception-requests/<team>-<purpose>.json`, using:
   ```json
   {
     "principalArn": "arn:aws:iam::123456789012:role/PartnerReader",
     "actions": ["s3:GetObject"],
     "prefix": "partner-x/*",
     "expiresAt": "2025-12-31",
     "reason": "POC 파일 읽기만 허용"
   }
   ```
2. **Pull request review**: CI merges baseline + exceptions + requests. Any expired entry raises a failure (blocking merge).
3. **Manual approval**: Security reviews the pipeline summary and approves deployment if conditions are satisfied.
4. **Deployment**: Upon approval, CDK updates the stack and policy; CodeBuild artifacts include `build/bucket-policy.merged.json`.
5. **Expiry enforcement**: Once `expiresAt` passes, subsequent builds fail until the request is renewed or removed. Remove stale files to maintain compliance.

## Testing & Validation
- `pytest -q`: validates six policy scenarios (Org/VPC mismatches, anonymous access, exception scope, expiry failure, SecureTransport enforcement).
- `scripts/cross_account_tests.sh <external-profile> <partner-profile>`: optional smoke test using AWS CLI profiles to confirm AccessDenied vs. scoped allow.
## Definition of Done (DoD)
- `pytest` suite passes with ≥90% success rate and overall coverage ≥80%.
- Public, OrgId, VPCe, and exception scenarios must be covered by automated tests.
- Expired exceptions trigger automatic build failure (merge policy check).
- README and DEMO remain in sync with the deployed behaviour.

## CI Rules
- Protect `main`; deployments run only via reviewed pull requests.
- Pull requests introducing exception request files require at least one explicit human approval.
- CodeBuild logs must surface policy statement and exception counts plus a summary banner of enforced rules.
- Any expired exception detected causes the build to fail immediately.

## Additional Notes
- Regenerate diagrams: `python tools/generate_diagram.py --vars BucketName=<bucket>,OrgId=<org>,VpcEndpointId=<vpce>`.
- Optional Terraform stub (`iac/terraform`) mirrors CDK behaviour using the merged policy artifact.
