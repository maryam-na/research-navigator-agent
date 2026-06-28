## Summary

Describe what changed and why.

## Validation

- [ ] `make lint`
- [ ] `make typecheck`
- [ ] `make test`
- [ ] `make eval`
- [ ] `make validate`

## Safety Checklist

- [ ] Preserves local-only operation
- [ ] Does not add cloud deployment or external calls without explicit approval
- [ ] Keeps generated outputs grounded in local evidence IDs
- [ ] Does not weaken prompt-injection, citation, or overclaiming checks
- [ ] Updates docs/specs if behavior changes

## Notes For Reviewers

Call out any known limitations, warnings, or follow-up work.
