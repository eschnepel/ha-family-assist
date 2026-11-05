# Task: Stale notice

- **Status:** todo
- **Related ADRs:** [ADR-0004]
- **Dependencies:** [TASK-0006-push-never-waits]

## Goal

When Sync or Push fails the Agent Repository is Stale. The Admin sees the cause, Family Members see a notice telling them to contact the Admin while it lasts, and a later success clears it. Diverged is one cause.

## Acceptance Criteria

- Given the last Sync failed, When a Family Member opens a Chat of that Agent Repository, Then a notice in their language tells them to contact the Admin, and the assistant keeps working on the last good Checkout.
- Given the Agent Repository is Stale, When the Admin opens the admin page, Then the cause (error text, Diverged, unpushed commits) is shown.
- Given a Stale Agent Repository, When a Sync (or Push, whichever failed) next succeeds, Then the notice disappears without a restart.
- Given a Diverged Agent Repository, When state is queried, Then it is Stale.
- Given two Agent Repositories of which one is Stale, When a Family Member uses a Chat of the other, Then no notice is shown.

## Estimated File / Module Footprint (hint, not a commitment)

- Likely `gitenv.py` (state), `web.py` (state in API), `static/app.js`, `static/index.html`, `static/style.css`, `static/i18n/*.js`, `tests/test_agent_web.py`, `tests/test_environments.py`, `REQUIREMENTS.md`

## Definition of Done

- Tests green (`pytest`) · `pre-commit run --all-files` clean (ruff, mypy, mdformat) · docs updated for the requirements touched · no open ADR conflicts
- `Delivered Artifacts` block completed and accurate
- Any new external dependencies recorded in `tasks/DEPENDENCIES.md`
- Persisted keys and contracts unchanged (`env_id`, `environments`, `user_id`, id `default`, `Current user: <alias>`, Tool names, `.family_assist.yaml` keys, `/data` layout); a data directory written by the previous version still loads
- English and German notice texts follow `tasks/adr-summary.md`

## Consumed Interfaces

<!-- Filled by the Lead Agent in Phase 3 from the Delivered Artifacts of: TASK-0006-push-never-waits -->

- _(to be filled before this task starts)_

## Delivered Artifacts

<!-- Filled by the Worker AFTER implementation. Be exact: downstream tasks depend on this information. -->

- _(not yet delivered)_
