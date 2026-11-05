# Task: App vocabulary

- **Status:** todo
- **Related ADRs:** [ADR-0001]
- **Dependencies:** [TASK-0002-chat-and-title-vocabulary]

## Goal

"App" replaces "add-on" in `DOCS.md`, `README.md`, `config.yaml`, translations and UI. ADR 0001 keeps its wording (its amendment already says to read "add-on" as "App").

## Acceptance Criteria

- Given the docs, config and UI texts (en + de), When the vocabulary check runs with "add-on" added, Then no "add-on"/"Add-on" remains outside the allowlist (ADR files, `tasks/`, `GLOSSARY.md`).
- Given `config.yaml` and `translations/*.yaml`, When pre-commit runs, Then both remain valid and the option keys are unchanged.

## Estimated File / Module Footprint (hint, not a commitment)

- Likely `family_assist/DOCS.md`, `README.md`, `family_assist/config.yaml`, `family_assist/translations/*.yaml`, `static/i18n/*.js`, `REQUIREMENTS.md` (R1.1), `tests/test_vocabulary.py`

## Definition of Done

- Tests green (`pytest`) · `pre-commit run --all-files` clean (ruff, mypy, mdformat) · docs updated for the requirements touched · no open ADR conflicts
- `Delivered Artifacts` block completed and accurate
- Any new external dependencies recorded in `tasks/DEPENDENCIES.md`
- Persisted keys and contracts unchanged (`env_id`, `environments`, `user_id`, id `default`, `Current user: <alias>`, Tool names, `.family_assist.yaml` keys, `/data` layout); a data directory written by the previous version still loads

## Consumed Interfaces

<!-- Filled by the Lead Agent in Phase 3 from the Delivered Artifacts of: TASK-0002-chat-and-title-vocabulary -->

- _(to be filled before this task starts)_

## Delivered Artifacts

<!-- Filled by the Worker AFTER implementation. Be exact: downstream tasks depend on this information. -->

- _(not yet delivered)_
