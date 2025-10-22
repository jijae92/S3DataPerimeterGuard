# S3 Data Perimeter Guard
> AWS S3 데이터 접근을 네트워크·조직·정책 관점에서 자동 점검·시뮬레이션·차단하는 데이터 보안 경계(Perimeter) 검증 툴킷

## 한 줄 요약 (Tagline)
CloudTrail·Access Analyzer·Policy Simulator를 결합해 **적법한 S3 접근만 통과**시키는 DevSecOps 자동화 플랫폼.

## 목차
- [프로젝트 소개](#프로젝트-소개)
- [핵심 기능 요약](#핵심-기능-요약)
- [빠른 시작 (Quick Start)](#빠른-시작-quick-start)
- [구성 및 설정](#구성-및-설정)
- [아키텍처 개요](#아키텍처-개요)
- [운영](#운영)
- [CI/CD 통합 가이드](#cicd-통합-가이드)
- [보안·컴플라이언스](#보안컴플라이언스)
- [기여 가이드](#기여-가이드)
- [테스트 및 검증](#테스트-및-검증)
- [FAQ](#faq)
- [변경 이력](#변경-이력)
- [라이선스](#라이선스)
- [연락처 / 보안 신고](#연락처--보안-신고)
- [샘플 findings.json](#샘플-findingsjson)

## 프로젝트 소개
- **문제 정의**: S3 데이터 경계 정책(IAM Policy, S3 Bucket Policy, VPC Endpoint, AWS Organizations SCP)을 운영/테스트 환경에서 일관되게 검증하기 어려움.
- **주요 기능**: CloudTrail 이벤트 분석, Access Analyzer 기반 정책 시뮬레이션, 자동 수정 제안, Streamlit 대시보드 시각화, CI/CD 차단/승인 워크플로우.
- **기대 효과**: 비정상적인 S3 접근을 조기 탐지하고, 안전한 Policy-as-Code 교정안을 즉시 적용하여 데이터 노출 위험 감소.
- **활용 시나리오**: 신규 S3 버킷 배포 검증, 보안 감사 대응, 지속적인 데이터 경계 모니터링.

## 핵심 기능 요약
| 영역 | 컴포넌트 | 설명 |
| --- | --- | --- |
| 로그 감시 | **Analyzer Lambda** | CloudTrail 이벤트 수집 → Access Analyzer API 호출 → 이상 징후 분석 |
| 정책 시뮬레이션 | **Simulator (boto3 / Policy Simulator)** | IAM Policy + SCP + Bucket Policy + VPC Endpoint 조건을 결합 평가 |
| 정책 교정 | **Auto Remediation Builder** | 허용/차단 결과 기반으로 안전한 Policy-as-Code 스니펫 제안 |
| 알림 | **Notifier (SNS / Slack / Email)** | 위협 감지 시 실시간 경고 |
| 시각화 | **Dashboard (Streamlit / Athena)** | `/artifacts/findings.json` 기반 인사이트 제공 |
| 배포 보강 | **CI/CD Hooks (CodeBuild + Lambda)** | 코드 변경 시 자동 스캔 → 실패 시 Manual Approval |

## 빠른 시작 (Quick Start)
> ⚠️ **비밀값 금지**: 저장소에 실제 시크릿을 커밋하지 마세요. 모든 비밀은 `.env` 로컬 파일에만 보관하고, `./.env.example`를 참고하십시오.

### 사전 요구사항
- Python 3.11 이상
- AWS CLI v2 이상 및 자격 증명 구성
- SAM CLI 및 Docker (로컬 테스트용)
- Node.js 18+ (Streamlit/프런트엔드 빌드 대비)

### 1. 가상환경 및 의존성
```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
npm ci --prefix dashboard
```

### 2. 환경 변수 준비
```bash
cp .env.example .env
# 이후 .env 파일에서 AWS_REGION 등 값을 실제 환경에 맞게 수정
```

### 3. 초기 스캔 실행
```bash
make up              # venv + deps 설치
make test            # pytest 및 커버리지 검증
make simulate        # 샘플 정책 시뮬레이션 및 /artifacts/findings.json 생성
make deploy          # SAM/CDK 배포 (테스트 혹은 스테이징)
```

### 4. 수동 실행 예시
```bash
source .venv/bin/activate
python tools/simulator.py run \
  --bucket example-data-bucket \
  --policy-file policies/bucket-policy.base.json \
  --scps policies/scp-set.json \
  --iam-roles data-perimeter-role.json \
  --output artifacts/findings.json
```

## 구성 및 설정
### 환경 변수 (.env)
`.env.example` 참고 (예시 키)
- `AWS_REGION=us-east-1`
- `ANALYZER_ROLE_ARN=arn:aws:iam::123456789012:role/S3DataPerimeter-Analyzer`
- `NOTIFY_TOPIC_ARN=arn:aws:sns:us-east-1:123456789012:s3-guardrail-alerts`
- `SIMULATION_MODE=full|incremental`

### 예외 허용 파일 `.guardrails-allow.json`
```json
[
  {
    "id": "allow-temporary-cross-account",
    "reason": "파트너 계정 임시 공유",
    "expires_at": "2025-12-31T00:00:00Z",
    "created_by": "security@example.com"
  }
]
```
- `expires_at` 필드는 필수입니다. 만료 시 CI 단계가 실패하여 관리자가 갱신해야 합니다.

### IAM 최소 권한 스니펫 (읽기 전용)
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "AllowCloudTrailRead",
      "Effect": "Allow",
      "Action": ["s3:GetObject", "s3:ListBucket"],
      "Resource": [
        "arn:aws:s3:::<YOUR_CLOUDTRAIL_BUCKET>",
        "arn:aws:s3:::<YOUR_CLOUDTRAIL_BUCKET>/*"
      ]
    },
    {
      "Sid": "AllowAccessAnalyzerQuery",
      "Effect": "Allow",
      "Action": [
        "access-analyzer:ListFindings",
        "access-analyzer:GetFinding",
        "access-analyzer:StartPolicyGeneration"
      ],
      "Resource": "*"
    },
    {
      "Sid": "AllowCloudTrailLookup",
      "Effect": "Allow",
      "Action": [
        "cloudtrail:LookupEvents"
      ],
      "Resource": "*"
    }
  ]
}
```
> 주석: 배포/자동화 계정에서 추가 리소스가 필요하면 별도 역할에 `iam:PassRole`, `cloudformation:*`, `lambda:*` 등 필요한 권한을 점진적으로 확대하세요. 필요한 최소 권한 원칙을 먼저 적용한 뒤 증분 부여를 권장합니다.

## 아키텍처 개요
```mermaid
flowchart LR
  CTrail[CloudTrail Logs (S3)] --> Analyzer[Analyzer Lambda]
  Analyzer --> AccessAnalyzer[Access Analyzer API]
  Analyzer --> Simulator[Policy Simulator]
  Simulator --> FindingsS3[artifacts/findings.json]
  FindingsS3 --> Dashboard[Streamlit Dashboard]
  Simulator --> Notifier[SNS / Slack / Email]
  Dashboard --> Operators[Operators]

```
- CloudTrail 로그가 S3에 적재되면 Analyzer Lambda가 이벤트를 처리해 Access Analyzer 및 Policy Simulator API를 호출합니다.
- 정책 평가 결과와 자동 수정 제안은 `/artifacts/findings.json` 및 대시보드로 전송됩니다.
- CI/CD 파이프라인(CodeBuild, Lambda Hook)은 최신 정책 결과를 활용해 배포 승인 여부를 결정합니다.

## 운영
- **로그 위치**: CloudWatch Log Group ` /aws/lambda/s3-data-perimeter-analyzer `, ` /aws/codebuild/s3-data-perimeter-ci `.
- **모니터링 지표**: Lambda 오류율, SNS 알림 전달 성공률, CodeBuild 스캔 실패율, Access Analyzer API throttling 지표.
- **운영 시나리오 예시**: “Cross-Account S3 Access Detected → Slack Alert → Analyzer Lambda 로그 점검 → IAM/SCP 정책 수정 → `make simulate` 재검증 → 재배포”.
- **복구 절차 요약**: 이상 탐지 시 CloudWatch Logs 확인 → IAM/SCP 정책 점검 → 예외 승인 또는 정책 수정 후 재배포.
- **히스토리 키 노출 대응**: 키 즉시 폐기 → `git filter-repo`(또는 BFG)로 기록 삭제 → 강제 push → 협업자 공지 및 자격 증명 롤오버.

## CI/CD 통합 가이드
### CodeBuild buildspec.yml (요약)
```yaml
version: 0.2
phases:
  install:
    commands:
      - python -m venv .venv && source .venv/bin/activate
      - pip install -r requirements.txt
      - npm ci --prefix dashboard
  build:
    commands:
      - source .venv/bin/activate
      - python tools/simulator.py run --bucket $TARGET_BUCKET --output artifacts/findings.json
      - pytest -q
  post_build:
    commands:
      - aws s3 cp artifacts/findings.json s3://$ARTIFACT_BUCKET/$CODEBUILD_BUILD_ID/findings.json
artifacts:
  files:
    - artifacts/findings.json
```
- **CodePipeline 단계**: Source → Build(CodeBuild) → Manual Approval(위험도 HIGH 시) → Deploy(SAM/CDK). 스캔 실패 시 Build 단계에서 차단, Manual Approval 단계에서 보안 팀 확인 후 승인.

## 보안·컴플라이언스
- AWS Data Perimeter Reference Architecture (AWS Blog)와 정합.
- 규정 매핑: NIST SP 800-53 **AC-6(Least Privilege)**, **SC-7(Boundary Protection)**, ISO 27001 **A.9(Access Control)**, **A.12.6(Technical Vulnerability Management)**.
- 비밀 관리는 AWS Secrets Manager 또는 SSM Parameter Store 사용, KMS 암호화 필수.
- 로그 보존: CloudTrail 365일, Analyzer/Simulator 로그 180일 이상.
- 데이터 분류: `/artifacts/findings.json` → 내부제한(Internal Confidential).
- 취약점 신고는 [SECURITY.md](./SECURITY.md) 참고.

## 기여 가이드
- 브랜치 전략: `main`(보호), `feature/*`, `fix/*`.
- 커밋 메시지: Conventional Commits (`feat:`, `fix:`, `chore:` 등).
- PR 템플릿 (요약): 변경 요약, 테스트 결과, 보안 영향, 롤백 전략, 승인자 체크.
- 상세 기여 프로세스는 [CONTRIBUTING.md](./CONTRIBUTING.md) 참고.

## 테스트 및 검증
- 기본 테스트: `pytest --cov=tools --cov=simulator tests/` (커버리지 ≥80% 권장).
- 샘플 CloudTrail 이벤트 → Access Analyzer 호출 예시: `tests/data/cloudtrail_suspicious_event.json` 기반.
- `/artifacts/findings.json` 은 `python tools/simulator.py run --dry-run`으로 미리보기 가능.

## FAQ
1. **왜 Access Analyzer를 함께 사용하나요?** → 버킷 정책과 IAM·SCP를 통합 평가하여 예외 경로를 탐지하기 위함.
2. **예외를 영구 허용할 수 있나요?** → `expires_at` 갱신 없이 영구 허용 권장하지 않음. 갱신 프로세스를 정의하세요.
3. **Streamlit 대신 QuickSight를 사용할 수 있나요?** → 가능합니다. Athena/Glue 스키마를 동일하게 활용하세요.

## 변경 이력
- 전체 릴리스 기록은 [CHANGELOG.md](./CHANGELOG.md) 참조.

## 라이선스
- 본 프로젝트는 [LICENSE](./LICENSE) (예: MIT) 라이선스를 따릅니다.

## 연락처 / 보안 신고
- 운영 문의: ops@example.com
- 보안 취약점 신고: security@example.com (PGP: `<YOUR_PGP_KEY_ID>`)
- 자세한 절차는 [SECURITY.md](./SECURITY.md) 참고

## 샘플 findings.json
```json
{
  "metadata": {
    "scanId": "scan-2025-10-22T10-00-00Z",
    "generatedAt": "2025-10-22T10:15:42Z",
    "region": "us-east-1",
    "analyzerRole": "arn:aws:iam::123456789012:role/S3DataPerimeter-Analyzer"
  },
  "summary": {
    "totalFindings": 3,
    "high": 1,
    "medium": 1,
    "low": 1,
    "riskScore": 78
  },
  "findings": [
    {
      "ruleId": "S3-GUARD-001",
      "eventName": "GetObject",
      "principal": "arn:aws:iam::999999999999:role/ExternalVendor",
      "bucketName": "example-sensitive-bucket",
      "action": "s3:GetObject",
      "effect": "DENY",
      "condition": "PrincipalOrgID mismatch",
      "riskScore": 95,
      "recommendation": "추가된 SCP에서 해당 계정 허용 여부 검토 후 예외 승인" 
    },
    {
      "ruleId": "S3-GUARD-010",
      "eventName": "PutBucketPolicy",
      "principal": "arn:aws:iam::123456789012:user/dev-admin",
      "bucketName": "example-sensitive-bucket",
      "action": "s3:PutBucketPolicy",
      "effect": "ALLOW",
      "condition": "Simulator predicted cross-account exposure",
      "riskScore": 70,
      "recommendation": "정책 수정안 적용: generated/policy-remediation.json" 
    },
    {
      "ruleId": "S3-GUARD-021",
      "eventName": "ListBucket",
      "principal": "arn:aws:iam::123456789012:role/data-analyst",
      "bucketName": "example-sensitive-bucket",
      "action": "s3:ListBucket",
      "effect": "ALLOW",
      "condition": "VPC Endpoint vpce-abc123 일치",
      "riskScore": 28,
      "recommendation": "허용된 경로 — 모니터링만 유지" 
    }
  ]
}
```
