# Task: Local Agent Repository

- **Status:** todo
- **Related ADRs:** [ADR-0005, ADR-0003, ADR-0004]
- **Dependencies:** [TASK-0010-startup-removal-sweep]

## Goal

An Admin can add an Agent Repository without a URL. The App creates a Local Agent Repository: a Checkout on the entry's branch, started from a short built-in starter `AGENTS.md` and an initial commit. The family can chat with it right away. It has nothing to Sync or Push and is never Stale, Commit Permission works as usual, and removal tells the Admin that no remote copy exists. Publishing it to a remote is TASK-0012.

## Acceptance Criteria

- Given the Admin adds an Agent Repository with a name and an empty URL, When it is saved, Then a Checkout is initialised on the entry's branch (default `main`) containing the starter `AGENTS.md`, one initial commit exists, and the entry appears in the Agent Repository selector.
- Given a Local Agent Repository, When a Family Member starts a Chat, Then the assistant follows the starter Agent Instructions and the Sandbox applies as for any Agent Repository (the starter `AGENTS.md` is read-only for the assistant).
- Given the starter text, When the language setting is English or German, Then the starter is in that language (selected as for the System Prompt preamble), is short, contains no personal data, and says it can be replaced by publishing the repository and editing it on the remote.
- Given a Local Agent Repository, When periodic Sync runs or the Admin presses "Sync now", Then the outcome is "nothing to sync", it returns promptly, no failure is recorded and the Agent Repository is never Stale.
- Given a Local Agent Repository, When the Admin looks for Push or "Push now", Then they are unavailable (UI) and refused with a clear message (API); the admin page shows the entry as local and not published.
- Given a Local Agent Repository and Commit Permission on, When a Turn changes files, Then the changes are committed locally exactly as for any Agent Repository.
- Given an Agent Repository that has a remote, When the Admin clears its URL, Then this is refused with an explanation.
- Given the Admin removes a Local Agent Repository, When the confirmation appears, Then it says that no remote copy exists and that everything, including its commits, is lost, in addition to the Chat count of TASK-0009; confirmed removal behaves as in TASK-0009 and TASK-0010.
- Given a data directory written by the previous version, When the App starts, Then all existing entries (all with a URL) load unchanged.

## Estimated File / Module Footprint (hint, not a commitment)

- Likely `config.py` (entry validation allows an empty URL), `gitenv.py` (`Checkout` initialisation, local state, Sync and Push guards), `web.py` (settings and status endpoints), a packaged starter-template file (en + de), `static/app.js`, `static/index.html`, `static/i18n/*.js`, `tests/test_environments.py`, `tests/test_git.py`, `REQUIREMENTS.md` (R4.1, R4.3, R6)

## Definition of Done

- Tests green (`pytest`) · `pre-commit run --all-files` clean (ruff, mypy, mdformat) · docs updated for the requirements touched · no open ADR conflicts
- `Delivered Artifacts` block completed and accurate
- Any new external dependencies recorded in `tasks/DEPENDENCIES.md`
- Persisted keys and contracts unchanged (`env_id`, `environments`, `user_id`, id `default`, `Current user: <alias>`, Tool names, `.family_assist.yaml` keys, `/data` layout); a data directory written by the previous version still loads
- The starter template's location and the persisted representation of a local entry (empty URL) are documented in `Delivered Artifacts`

## Consumed Interfaces

<!-- Filled by the Lead Agent in Phase 3 from the Delivered Artifacts of: TASK-0010-startup-removal-sweep -->

- _(to be filled before this task starts)_

## Delivered Artifacts

<!-- Filled by the Worker AFTER implementation. Be exact: downstream tasks depend on this information. -->

- _(not yet delivered)_
