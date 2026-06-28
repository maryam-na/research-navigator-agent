# Local Tickets

This folder stores local project tickets as separate Markdown files.

Ticket instances and the ticket overview are local workspace state and should not be pushed to the repository.
The repository only tracks this README and `tickets/TEMPLATE.md`.

## Naming

Use one file per ticket:

```text
tickets/TICKET-0001-short-slug.md
```

Keep ticket IDs stable once created. Prefer one user-facing outcome per ticket.

## Structure

Start from `tickets/TEMPLATE.md`. Each ticket should include:

- description of the user problem
- scope and explicit out of scope
- implementation notes or affected areas
- definition of done
- tests or checks
- visual checks for Streamlit/UI changes
- safety and local-first considerations

## Status

Use one of these statuses:

- `todo`
- `in_progress`
- `blocked`
- `done`

When a ticket is implemented, update the ticket with the branch name, commit hash, checks run, and any follow-up work.

## Overview

Keep `tickets/INDEX.md` as the local ticket overview list. It should include each ticket ID, status, priority, title, and short notes. Update it whenever tickets are created, started, blocked, or completed.

## Guardrails

- Do not commit or push ticket instance files.
- Do not commit or push `tickets/INDEX.md`.
- Do not store secrets, private data, or long paper excerpts in tickets.
- Keep tickets aligned with the project specs and safety policy.
- Preserve the local-only MVP scope unless the user explicitly changes it.
