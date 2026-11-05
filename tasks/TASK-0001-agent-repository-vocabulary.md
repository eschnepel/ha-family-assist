# Task: Agent Repository vocabulary

- **Status:** todo
- **Related ADRs:** [ADR-0002]
- **Dependencies:** []

## Goal

Admins, Family Members and developers meet the glossary words "Agent Repository" and "Checkout" instead of "Agent Environment", "environment" and "repo" in the UI (en + de), docs, identifiers and tests. `gitenv.AgentEnvironment`, which really manages the Checkout, becomes `Checkout`; the configured entry (`EnvConfig`) becomes the Agent Repository entry. Pure rename: no behaviour change. The model-facing preamble is included (Gate 2 decision G2-2); adapting the existing Agent Repository's own files is done by the project owner, outside this task. This task also introduces the vocabulary check that CAP-02 to CAP-04 extend.

## Acceptance Criteria

- Given the UI in English and German, When an Admin opens the Agent Repository settings and a Family Member opens the selector, Then every label, hint, message and confirmation says "Agent Repository" (German wording per `tasks/adr-summary.md`) and no retired term remains.
- Given the code base, When the vocabulary check (`tests/test_vocabulary.py`) runs, Then it finds no retired term in identifiers, UI strings, config text or docs outside an explicit allowlist of persisted keys and contracts. Its scan excludes `GLOSSARY.md`, `docs/adr/` and `tasks/`.
- Given a data directory written by the previous version, When the App starts, Then settings, Checkouts and Chats load unchanged and every existing API round trip behaves as before.
- Given the model-facing System Prompt preamble in `translations/*.yaml` (English and German), When the rename is complete, Then it says "Agent Repository" and its root instead of "environment" and "environment root", while its structure is unchanged: the `{alias}` line (`Current user:` / `Aktueller Benutzer:`), the tool rules and all placeholders stay, and tests asserting preamble content are updated.

## Estimated File / Module Footprint (hint, not a commitment)

- Likely `family_assist/app/assistd/gitenv.py`, `config.py`, `web.py`, `agent.py`, `static/app.js`, `static/index.html`, `static/i18n/en.js` + `de.js`, `family_assist/translations/*.yaml` (option texts only), `tests/test_environments.py`, `tests/test_git.py`, new `tests/test_vocabulary.py`, `REQUIREMENTS.md`, `DOCS.md`

## Definition of Done

- Tests green (`pytest`) · `pre-commit run --all-files` clean (ruff, mypy, mdformat) · docs updated for the requirements touched · no open ADR conflicts
- `Delivered Artifacts` block completed and accurate
- Any new external dependencies recorded in `tasks/DEPENDENCIES.md`
- Persisted keys and contracts unchanged (`env_id`, `environments`, `user_id`, id `default`, `Current user: <alias>`, Tool names, `.family_assist.yaml` keys, `/data` layout); a data directory written by the previous version still loads
- `tests/test_vocabulary.py` exists, documents its allowlist, and is structured so later tasks add terms without restructuring it

## Consumed Interfaces

<!-- No dependencies: nothing is consumed from other tasks. -->

- none

## Delivered Artifacts

<!-- Filled by the Worker AFTER implementation. Be exact: downstream tasks depend on this information. -->

- _(not yet delivered)_
