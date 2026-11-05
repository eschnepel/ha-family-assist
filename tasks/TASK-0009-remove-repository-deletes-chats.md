# Task: Removing an Agent Repository deletes its Chats

- **Status:** todo
- **Related ADRs:** [ADR-0003]
- **Dependencies:** [TASK-0008-delete-chat-cancels-turn]

## Goal

Removing an Agent Repository cancels the running Turns of its Chats, then permanently deletes its Checkout and Chats after an explicit confirmation that names the number of Chats and any unpushed commits or uncommitted changes. It writes a removal marker first and clears it when deletion completes.

## Acceptance Criteria

- Given an Agent Repository with Chats, When the Admin starts removal, Then the confirmation names the number of Chats and states that unpushed commits or uncommitted changes (if any) are lost; German and English.
- Given running Turns in its Chats, When removal is confirmed, Then those Turns are cancelled (rolled back) before deletion.
- Given confirmed removal, When it completes, Then its Checkout and all its Chats (including Deleted Chats) are gone, other Agent Repositories and their Chats are untouched, and the removal marker is cleared.
- Given removal is interrupted after the marker was written, When the state is inspected, Then the marker remains (TASK-0010 completes it).
- Given an Agent Repository was removed, When the same URL is added again, Then it is a new Agent Repository with no Chats.

## Estimated File / Module Footprint (hint, not a commitment)

- Likely `web.py` (remove endpoint), `config.py` (settings, removal marker), `store.py` (delete all Chats of an Agent Repository), `gitenv.py`, `static/app.js`, `static/i18n/*.js`, `tests/test_environments.py`, `tests/test_agent_web.py`, `REQUIREMENTS.md` (R4.1)

## Definition of Done

- Tests green (`pytest`) · `pre-commit run --all-files` clean (ruff, mypy, mdformat) · docs updated for the requirements touched · no open ADR conflicts
- `Delivered Artifacts` block completed and accurate
- Any new external dependencies recorded in `tasks/DEPENDENCIES.md`
- Persisted keys and contracts unchanged (`env_id`, `environments`, `user_id`, id `default`, `Current user: <alias>`, Tool names, `.family_assist.yaml` keys, `/data` layout); a data directory written by the previous version still loads
- The removal-marker format and location are documented in `Delivered Artifacts`

## Consumed Interfaces

<!-- Filled by the Lead Agent in Phase 3 from the Delivered Artifacts of: TASK-0008-delete-chat-cancels-turn -->

- _(to be filled before this task starts)_

## Delivered Artifacts

<!-- Filled by the Worker AFTER implementation. Be exact: downstream tasks depend on this information. -->

- _(not yet delivered)_
