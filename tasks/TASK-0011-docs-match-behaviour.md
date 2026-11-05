# Task: Documentation matches behaviour

- **Status:** todo
- **Related ADRs:** [ADR-0001, ADR-0002, ADR-0003, ADR-0004]
- **Dependencies:** [TASK-0010-startup-removal-sweep]

## Goal

`REQUIREMENTS.md`, `DOCS.md` and `README.md` describe the accepted behaviour and no longer contain the known defects. Capability tasks already update the requirements they touch; this task is the final sweep.

## Acceptance Criteria

- Given R4.1, R4.3 and R6.3 to R6.5, When read, Then they match ADRs 0003 and 0004 (removal, Stale, optimistic Sync and Push, network steps outside the lock).
- Given R3.5, When read, Then it says a Chat runs one Turn at a time and a message sent meanwhile is refused (409), not "queued".
- Given R5.2, When read, Then the default Tool Allowlist includes `load_skill`, as the code does.
- Given R4.4, When read, Then it separates System Prompt (preamble + root Agent Instructions) from Agent Instructions as in the glossary.
- Given ADR 0002's "no network tool" sentence, When a reader follows its amendment, Then `REQUIREMENTS.md` R5.1 and R7.3 are consistent with the `load_skill` exception.
- Given `README.md` and `DOCS.md`, When the vocabulary check runs, Then it still passes.

## Estimated File / Module Footprint (hint, not a commitment)

- `REQUIREMENTS.md`, `family_assist/DOCS.md`, `README.md`

## Definition of Done

- Tests green (`pytest`) · `pre-commit run --all-files` clean (ruff, mypy, mdformat) · docs updated for the requirements touched · no open ADR conflicts
- `Delivered Artifacts` block completed and accurate
- Any new external dependencies recorded in `tasks/DEPENDENCIES.md`
- Persisted keys and contracts unchanged (`env_id`, `environments`, `user_id`, id `default`, `Current user: <alias>`, Tool names, `.family_assist.yaml` keys, `/data` layout); a data directory written by the previous version still loads

## Consumed Interfaces

<!-- Filled by the Lead Agent in Phase 3 from the Delivered Artifacts of: TASK-0010-startup-removal-sweep -->

- _(to be filled before this task starts)_

## Delivered Artifacts

<!-- Filled by the Worker AFTER implementation. Be exact: downstream tasks depend on this information. -->

- _(not yet delivered)_
