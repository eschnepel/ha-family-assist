# Task: Interrupted removals finish at startup

- **Status:** todo
- **Related ADRs:** [ADR-0003]
- **Dependencies:** [TASK-0009-remove-repository-deletes-chats]

## Goal

At every startup the Chats of marked Agent Repository ids are deleted and the markers cleared, which finishes removals that were cut off. Chats orphaned by earlier versions are adopted once, at the first startup after the update, by marking their ids, under strict guards.

## Acceptance Criteria

- Given the App stopped mid-removal, When it starts, Then the remaining Chats of the marked id are deleted and the marker is cleared.
- Given damaged, unreadable or empty settings, When the App starts, Then no Chat is deleted and no id is adopted.
- Given clean settings that list at least one Agent Repository and Chats whose id is unknown, When the App starts for the first time after the update, Then those ids are marked and their Chats deleted, and adoption never runs again.
- Given Chats without an id or with the legacy id `default`, When adoption runs, Then they are never treated as removed.
- Given a startup with no markers and adoption already done, When the App starts, Then nothing is deleted.

## Estimated File / Module Footprint (hint, not a commitment)

- Likely `__main__.py` or the startup path in `web.py`, `config.py` (markers, adoption flag), `store.py`, `tests/test_environments.py`, `tests/test_agent_web.py`, `REQUIREMENTS.md` (R4.1, R4.1a)

## Definition of Done

- Tests green (`pytest`) · `pre-commit run --all-files` clean (ruff, mypy, mdformat) · docs updated for the requirements touched · no open ADR conflicts
- `Delivered Artifacts` block completed and accurate
- Any new external dependencies recorded in `tasks/DEPENDENCIES.md`
- Persisted keys and contracts unchanged (`env_id`, `environments`, `user_id`, id `default`, `Current user: <alias>`, Tool names, `.family_assist.yaml` keys, `/data` layout); a data directory written by the previous version still loads
- The persisted adoption flag is documented in `Delivered Artifacts`

## Consumed Interfaces

<!-- Filled by the Lead Agent in Phase 3 from the Delivered Artifacts of: TASK-0009-remove-repository-deletes-chats -->

- _(to be filled before this task starts)_

## Delivered Artifacts

<!-- Filled by the Worker AFTER implementation. Be exact: downstream tasks depend on this information. -->

- _(not yet delivered)_
