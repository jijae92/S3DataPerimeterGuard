# Security Policy

## Supported Versions
- `main` branch (latest release)

## Reporting a Vulnerability
1. Email `security@example.com` with the subject `S3 DATA PERIMETER GUARD - VULN REPORT`.
2. Provide affected component (Analyzer, Simulator, Dashboard, CI Hooks), reproduction steps, impact, and proposed remediation if possible.
3. Encrypt sensitive details using our PGP key `<YOUR_PGP_KEY_ID>`.
4. Expect acknowledgment within 48 hours; remediation timeline shared within 7 business days.

## Disclosure
- Do **not** open public GitHub issues for security bugs.
- Coordinate disclosure period: 30 days or mutually agreed schedule.

## Secret Exposure Response
1. Immediately revoke exposed AWS credentials/keys.
2. Run `git filter-repo` (or BFG Repo-Cleaner) to purge secrets.
3. Force-push the cleaned history and notify collaborators.
4. Rotate impacted systems and document the incident.

## Contact
- security@example.com
