# Build, Deploy and Roll Back

## Reproducible delivery

Reuse the project's package manager, lockfiles, build scripts and hosting provider. Separate
development/test/production configuration; document required environment variables without values.
Use least-privilege runtime/CI identities and immutable release artifacts. CI runs the project's
tests and the skill's relevant gates; installation success alone is not a product check.
Scan dependencies/images as applicable. Use SBOM/provenance when needed for the product's supply
chain; consult [SLSA](https://slsa.dev/spec/v1.2/) for artifact provenance.

## Build and rollback checks

Configure `delivery.build` to execute the real build, assert expected artifacts and smoke-start
the artifact where applicable. Report actual checks through [scenario reports](../../core/project-config.md).
A zero-exit command with no tested artifact/startup assertions cannot pass.

Configure `delivery.rollback` on a dedicated deployment environment: deploy a candidate, verify
smoke behaviour, restore the prior artifact and re-run smoke tests. Coordinate compatible database
migrations with [data](../data/workflow.md). Document irreversible data changes; swapping a container
image does not reverse them. Never run rollback drills against production without authorization.

## Release verdict

Use `sa.py review --mode release-check --profile <profile>` with critical UI/API targets.
All required current-code gates and mapped acceptance criteria must pass for `release_ready`.
Missing tests/tools, ERROR or STALE evidence block readiness. Report exact environment and scope.
Review original requirements, implementation and assertions independently before delivery.
The skill prepares a reviewable release; external publication follows the user's requested scope.
