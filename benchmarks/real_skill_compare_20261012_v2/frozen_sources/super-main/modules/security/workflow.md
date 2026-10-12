# Security Across the Application Lifecycle

Security requirements apply when defining UI journeys, API permissions, data ownership and deployment.
Use [ASVS 5.0](https://owasp.org/projects/asvs) as a versioned requirement source and
[API Security Top 10](https://api-security.owasp.org/editions/2023/en/0x11-t10/) for risk scenarios.
Record applicable requirement identifiers; a clean scan is not ASVS conformance.

## Threat and access model

Identify assets, roles, tenants, trust boundaries, external integrations and abuse-sensitive flows.
Derive negative scenarios for object/field/function access, cross-tenant reads and writes,
anonymous access, revoked/expired sessions, recovery flows and privilege changes.
Implement these with framework-supported session/authentication libraries. Choose OAuth/OIDC
when appropriate using [RFC 9700](https://www.rfc-editor.org/rfc/rfc9700.html).
Use maintained password hashing, CSRF protection for cookie-based flows and narrowly defined CORS;
do not invent cryptography or equate CORS with authorization. Choose MFA based on risk.

## Input, integrations and abuse

Parameterize database queries and validate request/file sizes and formats. For URL fetching,
address SSRF including redirects and private destinations. Check upload storage and execution risks,
webhook authentication, outgoing dependency trust, rate limits and resource exhaustion.
Keep keys in the deployment's secret store/environment; never include tokens in config argv,
client bundles, evidence artifacts or research. Define rotation, revocation and audit events.

## Gates and findings

`security.authorization` executes named negative scenarios with real distinct users/tenants and
asserts absence of leaked data and unauthorized persisted effects, not only HTTP status.
`security.sast` uses local Semgrep rules; `security.dependencies` uses Trivy. Read their configured
scope and freshness. Scanner findings block their scan gate pending triage, but do not assert
that an attack was reproduced. Justified exceptions must be narrow, versioned and reviewed.
Configure `security.dast` using the project's ZAP wrapper only on an authorized disposable target;
validate authentication and endpoint coverage before accepting a no-findings result.
Missing tools are NOT-TESTED, scanner startup/parse failures are ERROR.

## Tool sources

[Semgrep](https://docs.semgrep.dev/) for rules and scan output,
[Trivy](https://trivy.dev/docs/latest/guide/) for dependency/configuration/secret scanning,
[ZAP](https://www.zaproxy.org/docs/) for runtime checks and
[NIST SSDF](https://www.nist.gov/publications/secure-software-development-framework-ssdf-version-11-recommendations-mitigating-risk)
for secure development practices. Review any automated finding before claiming exploitability.
