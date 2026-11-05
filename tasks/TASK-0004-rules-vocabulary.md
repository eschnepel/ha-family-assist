# Task: Fixed Rules and Repository Rules vocabulary

- **Status:** todo
- **Related ADRs:** [ADR-0002]
- **Dependencies:** [TASK-0003-app-vocabulary]

## Goal

`Rules` becomes `RepositoryRules` and `BUILTIN_*` becomes Fixed Rules naming. Commit Permission is described as one of the Fixed Rules. The admin page's effective-rules view, docs and requirements use "Repository Rules" and "Fixed Rules" consistently. No behaviour change.

## Acceptance Criteria

- Given the code and docs, When the vocabulary check runs with the new terms, Then `BUILTIN_*` and the unqualified class name `Rules` no longer appear outside the allowlist.
- Given the Sandbox tests, When they run unchanged in behaviour, Then they pass: every `AGENTS.md` and `.family_assist.yaml` is read-only, `.git` is hidden, a repository rule matching the root `AGENTS.md` is ignored with an admin warning, and write Tools stay unavailable while Commit Permission is off even if the Tool Allowlist lists them.
- Given the admin page in English and German, When an Admin views the effective rules, Then the view is labelled as Repository Rules (read-only) and the German wording follows `tasks/adr-summary.md`.
- Given `REQUIREMENTS.md` R5.3 to R5.6 and R6.1, When read, Then they use Fixed Rules / Repository Rules and describe Commit Permission as a Fixed Rule.

## Estimated File / Module Footprint (hint, not a commitment)

- Likely `rules.py`, `tools.py`, `agent.py`, `web.py`, `static/app.js`, `static/i18n/*.js`, `tests/test_tools.py`, `tests/test_vocabulary.py`, `REQUIREMENTS.md`

## Definition of Done

- Tests green (`pytest`) · `pre-commit run --all-files` clean (ruff, mypy, mdformat) · docs updated for the requirements touched · no open ADR conflicts
- `Delivered Artifacts` block completed and accurate
- Any new external dependencies recorded in `tasks/DEPENDENCIES.md`
- Persisted keys and contracts unchanged (`env_id`, `environments`, `user_id`, id `default`, `Current user: <alias>`, Tool names, `.family_assist.yaml` keys, `/data` layout); a data directory written by the previous version still loads

## Consumed Interfaces

<!-- Filled by the Lead Agent in Phase 3 from the Delivered Artifacts of: TASK-0003-app-vocabulary -->

- _(to be filled before this task starts)_

## Delivered Artifacts

<!-- Filled by the Worker AFTER implementation. Be exact: downstream tasks depend on this information. -->

- _(not yet delivered)_
