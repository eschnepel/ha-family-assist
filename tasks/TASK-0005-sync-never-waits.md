# Task: Sync that never waits

- **Status:** todo
- **Related ADRs:** [ADR-0004]
- **Dependencies:** [TASK-0004-rules-vocabulary]

## Goal

A manual or periodic Sync updates the Checkout in the background while Turns run: it never waits for them, never overwrites a Turn's uncommitted files, and its network steps run outside the lock. Failure is recorded on the Agent Repository (the user-visible notice is TASK-0007).

## Acceptance Criteria

- Given a Turn has written an uncommitted file and the remote changed other files, When Sync runs, Then it succeeds, the Turn's file is untouched and the Turn still commits it.
- Given a Turn has written an uncommitted file and the remote changed that same file, When Sync runs, Then Sync fails, no file is modified, and the failure and its cause are recorded.
- Given a slow fetch is in progress, When a Turn writes a file or commits, Then neither waits for the fetch.
- Given a Turn started before a Sync that changed the Agent Instructions or Repository Rules, When the Turn continues, Then it keeps the System Prompt and Repository Rules it started with, and its reads may see newer files.
- Given no local commits and no pending files, When Sync runs, Then the Checkout equals the remote branch afterwards, reached by fast-forward and never by `git reset --hard`.
- Given an Agent Repository that has a remote and whose URL or branch changed, and a Turn has pending files or the Checkout holds unpushed commits, When Sync runs, Then it fails with the cause recorded and nothing is deleted.
- Given the admin presses "Sync now", When Sync is busy or fails, Then the request returns promptly with the outcome; there is no "try again shortly" wait.

## Estimated File / Module Footprint (hint, not a commitment)

- Likely `gitenv.py` (the `Checkout` class), `web.py` (sync endpoint, periodic Sync), `tests/test_git.py`, `tests/test_environments.py`, `REQUIREMENTS.md` (R4.3, R6.5)

## Definition of Done

- Tests green (`pytest`) · `pre-commit run --all-files` clean (ruff, mypy, mdformat) · docs updated for the requirements touched · no open ADR conflicts
- `Delivered Artifacts` block completed and accurate
- Any new external dependencies recorded in `tasks/DEPENDENCIES.md`
- Persisted keys and contracts unchanged (`env_id`, `environments`, `user_id`, id `default`, `Current user: <alias>`, Tool names, `.family_assist.yaml` keys, `/data` layout); a data directory written by the previous version still loads
- Tests include a concurrent-Turn scenario for each of the criteria above

## Consumed Interfaces

<!-- Filled by the Lead Agent in Phase 3 from the Delivered Artifacts of: TASK-0004-rules-vocabulary -->

- _(to be filled before this task starts)_

## Delivered Artifacts

<!-- Filled by the Worker AFTER implementation. Be exact: downstream tasks depend on this information. -->

- _(not yet delivered)_
