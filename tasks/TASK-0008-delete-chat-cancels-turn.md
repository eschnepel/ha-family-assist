# Task: Deleting a Chat cancels its running Turn

- **Status:** todo
- **Related ADRs:** [ADR-0003]
- **Dependencies:** [TASK-0007-stale-notice]

## Goal

Deleting a Chat while its Turn runs cancels the Turn instead of answering 409. A waiting Question ends, the Queue slot is released and the Turn is rolled back: no commit and no uncommitted file. The Chat becomes a Deleted Chat as before. This task provides the cancellation mechanism that TASK-0009 reuses.

## Acceptance Criteria

- Given a Turn is generating, When its Chat is deleted, Then the Turn stops, the Chat is a Deleted Chat and an Admin can restore it.
- Given a Turn waits for a Question, When its Chat is deleted, Then the Question ends and the Queue slot is released.
- Given a Turn wrote files but did not commit, When its Chat is deleted, Then tracked files are reset, newly created files are removed, no commit is made, and no pending marker remains.
- Given a Turn was cancelled, When Sync or Push runs afterwards, Then they are not blocked.
- Given a Turn ends by error or limit (not cancelled), When it ends, Then it still commits what it wrote, as before.
- Given a Chat with a running Turn, When it is renamed, Then rename is still refused.

## Estimated File / Module Footprint (hint, not a commitment)

- Likely `web.py` (delete endpoint, registry of running Turns), `agent.py`, `questions.py`, `genqueue.py`, `gitenv.py` (rollback of pending paths), `tests/test_agent_web.py`, `tests/test_questions.py`, `REQUIREMENTS.md` (R3.5, R5.11)

## Definition of Done

- Tests green (`pytest`) · `pre-commit run --all-files` clean (ruff, mypy, mdformat) · docs updated for the requirements touched · no open ADR conflicts
- `Delivered Artifacts` block completed and accurate
- Any new external dependencies recorded in `tasks/DEPENDENCIES.md`
- Persisted keys and contracts unchanged (`env_id`, `environments`, `user_id`, id `default`, `Current user: <alias>`, Tool names, `.family_assist.yaml` keys, `/data` layout); a data directory written by the previous version still loads
- The cancellation entry point is documented in `Delivered Artifacts` so TASK-0009 can call it per Chat

## Consumed Interfaces

<!-- Filled by the Lead Agent in Phase 3 from the Delivered Artifacts of: TASK-0007-stale-notice -->

- _(to be filled before this task starts)_

## Delivered Artifacts

<!-- Filled by the Worker AFTER implementation. Be exact: downstream tasks depend on this information. -->

- _(not yet delivered)_
