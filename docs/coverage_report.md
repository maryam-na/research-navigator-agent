# Coverage Report

ResearchNavigator includes a local coverage-report command for the deterministic Python codebase.

Run:

```bash
make coverage
```

or:

```bash
uv run --extra dev python -m scripts.coverage_report
```

Generated files:

```text
data/processed/coverage.json
data/processed/coverage_summary.md
```

## Optional Threshold

To fail the command below a minimum total coverage percentage:

```bash
uv run --extra dev python -m scripts.coverage_report --min-total 70
```

To summarize an existing coverage JSON file without rerunning tests:

```bash
uv run --extra dev python -m scripts.coverage_report --skip-pytest
```

## Scope

Coverage is measured for:

- `app`
- `tools`
- `scripts`
- `ui`

Coverage is a software quality signal. It does not replace the project’s deterministic golden cases, safety checks, grounding checks, graph checks, or submission validator.
