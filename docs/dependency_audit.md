# Dependency Audit

ResearchNavigator includes an offline dependency audit for the local deterministic MVP.

Run it with:

```bash
make audit
```

or:

```bash
uv run python -m scripts.dependency_audit
```

The audit writes:

```text
data/processed/dependency_audit_report.json
```

## What It Checks

- `pyproject.toml` exists and is parseable.
- `uv.lock` exists and is parseable.
- Declared runtime and optional dependencies are represented in `uv.lock`.
- Core project dependencies are declared.
- Direct runtime dependencies have lower bounds or exact pins.
- Direct runtime dependencies are imported by current project code or flagged for review.
- Direct dependencies do not include known cloud/model-provider SDKs that would conflict with the local-first MVP.
- Runtime, optional, and locked dependency counts remain modest.

## Current Findings

The current audit is ready with zero failed checks.

Expected warnings:

- `duckdb`: planned alternative structured-storage backend, but the current MVP uses SQLite.
- `python-dotenv`: planned environment-loading utility, but current local scripts do not require environment variables.
- `rich`: planned richer CLI output, but current scripts use lightweight structured logging.
- `typer`: planned CLI framework, but current scripts use `argparse`.
- `jsonschema`: optional evaluation dependency, not required at runtime.

These are not blockers. Before final packaging, either keep them as explicitly planned dependencies or remove unused entries to reduce the dependency footprint.

## Scope

This audit is intentionally local and deterministic. It does not query external vulnerability databases. A production deployment would add an online supply-chain scan such as `pip-audit`, Dependabot, or GitHub dependency review, but that is outside this no-cloud MVP.
