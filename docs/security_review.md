# Security Review

This document summarizes the security posture of ResearchNavigator Agent for the deterministic local baseline.

## Scope

The review covers:

- local paper ingestion
- statement extraction
- SQLite storage
- graph construction
- gap and hypothesis generation
- experiment-plan generation
- Streamlit dashboard
- policy checks
- evaluation and validation scripts
- ADK-facing local wrapper

The local baseline does not include cloud deployment, external web search, model training, fine-tuning, email sending, or production credentials.

## Security Goals

- Keep papers and generated artifacts local.
- Treat paper text as untrusted data.
- Preserve evidence provenance.
- Prevent prompt-injected paper text from becoming agent instructions.
- Avoid invented citations and unsupported claims.
- Keep hypotheses clearly speculative.
- Block external or high-risk tool actions in the local baseline.
- Detect and sanitize sensitive context in proposed tool arguments.

## Threat Model

| Threat | Example | Mitigation |
| --- | --- | --- |
| Prompt injection in papers | A paper says "ignore previous instructions" | `tools/safety_tools.py` detects known injection phrases and policy docs require treating paper text as data |
| Overclaiming | Generated text says a hypothesis is proven | Overclaiming checks, speculative labels, and evaluation warnings |
| Fake citations | Output cites papers outside the local corpus | Local evidence IDs and fake-citation policy in `specs/safety_policy.md` |
| Graph explosion | Too many noisy statements create an unusable graph | Statement filtering, deduplication, graph caps, and project stats |
| Sensitive context leakage | Tool args contain emails, API keys, private URLs, or home paths | `tools/policy_tools.py` detects and sanitizes sensitive patterns |
| Unauthorized external action | An agent tries to email, deploy, train, or browse externally | `specs/policies.yaml` blocks high-risk tools in the local environment |
| Unlicensed paper use | User adds restricted papers | `data/papers/manifest.json` records license/source notes and docs require open-access or synthetic papers |

## Implemented Controls

- `tools/safety_tools.py`: prompt-injection, overclaiming, hypothesis safety, and grounding checks.
- `tools/policy_tools.py`: role/environment allowlists, blocked tools, sensitive-context detection, and sanitization.
- `tools/extraction_tools.py`: deterministic statement filtering and deduplication.
- `tools/evaluation_tools.py`: grounding, safety, testability, traceability, warnings, and failed checks.
- `tools/logging_tools.py`: structured local logs for operational visibility.
- `scripts/validate_submission.py`: submission-readiness checks for docs, artifacts, evals, screenshots, sample outputs, and corpus size.
- `specs/policies.yaml`: deterministic local policy rules.
- `specs/safety_policy.md`: human-readable safety requirements.

## Blocked By Default

The local baseline policy blocks:

- `send_email`
- `deploy_cloud`
- `external_web_search`
- `train_model`
- `fine_tune_model`
- `write_outside_workspace`

## Data Handling

- Input PDFs live under `data/papers/`.
- Processed artifacts live under `data/processed/`.
- The dashboard reads local files only.
- The deterministic local baseline does not send papers, statements, or outputs to remote services.

## Residual Risks

- Rule-based extraction can miss nuanced claims.
- Prompt-injection detection is pattern-based, not exhaustive.
- Citation support is statement-ID based, not full bibliographic verification.
- The ADK wrapper is designed for local review and should not be deployed publicly without additional review.
- Streamlit is intended for local review, not public hosting.

## Review Checklist Before Submission

Run:

```bash
make demo
make eval
make validate
make test
```

Confirm:

- no failed checks in `data/processed/evaluation_report.json`
- golden evals pass
- submission validator reports `Ready: True`
- paper manifest matches local PDFs
- screenshots and sample outputs are present
- generated hypotheses remain speculative

## Production Hardening Needed Before Deployment

Before any real deployment, add:

- authenticated user access
- stricter file upload validation
- structured audit logs
- full ADK trajectory evaluations
- richer citation validation
- dependency vulnerability scanning
- explicit human approval gates for report export and new paper ingestion
