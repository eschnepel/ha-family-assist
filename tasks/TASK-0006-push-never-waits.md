# Task: Push that never waits

- **Status:** todo
- **Related ADRs:** [ADR-0004]
- **Dependencies:** [TASK-0005-sync-never-waits]

## Goal

Push (after each commit with Push Permission, or via "Push now") rebases and pushes in the background under the same rules as Sync: network steps outside the lock, never touching a file with uncommitted changes. A failed Push never fails the Turn that caused it.

## Acceptance Criteria

- Given a Turn has an uncommitted file and unpushed commits exist, When Push rebases onto changes that do not touch the pending file, Then Push succeeds and the pending file is untouched.
- Given the rebase would touch a file a Turn has pending, When Push runs, Then Push fails, nothing is modified, and the failure is recorded.
- Given a slow network push, When a Turn writes or commits, Then neither waits for the push.
- Given the rebase hits a conflict, When Push runs, Then the rebase is aborted, local commits are kept, nothing is discarded and the Agent Repository is flagged Diverged.
- Given a Push fails after a Turn's commit, When the Turn ends, Then the Turn ends normally with its commit and the failure is recorded.

## Estimated File / Module Footprint (hint, not a commitment)

- Likely `gitenv.py`, `agent.py` (push after commit), `web.py` ("Push now"), `tests/test_git.py`, `tests/test_agent_web.py`, `REQUIREMENTS.md` (R6.3, R6.4)

## Definition of Done

- Tests green (`pytest`) · `pre-commit run --all-files` clean (ruff, mypy, mdformat) · docs updated for the requirements touched · no open ADR conflicts
- `Delivered Artifacts` block completed and accurate
- Any new external dependencies recorded in `tasks/DEPENDENCIES.md`
- Persisted keys and contracts unchanged (`env_id`, `environments`, `user_id`, id `default`, `Current user: <alias>`, Tool names, `.family_assist.yaml` keys, `/data` layout); a data directory written by the previous version still loads

## Consumed Interfaces

<!-- Filled by the Lead Agent in Phase 3 from the Delivered Artifacts of: TASK-0005-sync-never-waits -->

- _(to be filled before this task starts)_

## Delivered Artifacts

<!-- Filled by the Worker AFTER implementation. Be exact: downstream tasks depend on this information. -->

- _(not yet delivered)_
