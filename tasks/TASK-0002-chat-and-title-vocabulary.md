# Task: Chat and Title vocabulary

- **Status:** todo
- **Related ADRs:** []
- **Dependencies:** [TASK-0001-agent-repository-vocabulary]

## Goal

"Chat" replaces "Conversation" and "Title" replaces "teaser" everywhere except the stored layout: `ConversationStore`, `/api/conversations`, variables, UI, docs, tests. German "Unterhaltung" becomes "Chat". Pure rename, no behaviour change.

## Acceptance Criteria

- Given the UI in English and German, When a Family Member lists, opens, renames, exports and deletes a Chat, Then all texts say "Chat" and the rename prompt refers to the Title.
- Given the code base, When the vocabulary check runs with the Chat terms added, Then no `Conversation`, `conversation` (as a domain word) or `teaser` remains outside the allowlist (stored file layout and JSON keys).
- Given the chat-title prompt in `translations/*.yaml` (English and German), When Title generation runs, Then the prompt asks for a title instead of a name, and its output format and length limit are unchanged.
- Given Chats written by the previous version, When the App starts, Then they open, continue, rename, delete and restore (Deleted Chat) as before.

## Estimated File / Module Footprint (hint, not a commitment)

- Likely `store.py`, `web.py`, `agent.py`, `static/app.js`, `static/i18n/*.js`, `tests/test_agent_web.py`, `tests/test_downloads.py`, `tests/test_questions.py`, `tests/test_vocabulary.py`, `REQUIREMENTS.md`, `DOCS.md`

## Definition of Done

- Tests green (`pytest`) · `pre-commit run --all-files` clean (ruff, mypy, mdformat) · docs updated for the requirements touched · no open ADR conflicts
- `Delivered Artifacts` block completed and accurate
- Any new external dependencies recorded in `tasks/DEPENDENCIES.md`
- Persisted keys and contracts unchanged (`env_id`, `environments`, `user_id`, id `default`, `Current user: <alias>`, Tool names, `.family_assist.yaml` keys, `/data` layout); a data directory written by the previous version still loads

## Consumed Interfaces

<!-- Filled by the Lead Agent in Phase 3 from the Delivered Artifacts of: TASK-0001-agent-repository-vocabulary -->

- _(to be filled before this task starts)_

## Delivered Artifacts

<!-- Filled by the Worker AFTER implementation. Be exact: downstream tasks depend on this information. -->

- _(not yet delivered)_
