# Task: Publish a Local Agent Repository

- **Status:** todo
- **Related ADRs:** [ADR-0005, ADR-0004]
- **Dependencies:** [TASK-0011-local-agent-repository]

## Goal

When the Admin provides the URL of an empty remote for a Local Agent Repository, the App publishes it: it pushes the whole committed history once to the entry's branch, automatically and regardless of Push Permission. The entry keeps its id and Chats and becomes an ordinary Agent Repository. If the remote is not empty, nothing is pushed, merged or forced.

## Acceptance Criteria

- Given a Local Agent Repository and the URL of a remote that has no refs, When the Admin saves the URL, Then the full local history is pushed to the entry's branch once, even if Push Permission is off, the entry keeps its id, name and Chats, and the URL is stored.
- Given Publish succeeded, When Sync and Push run afterwards, Then they behave as for any Agent Repository with a remote, and Push follows Push Permission again.
- Given the remote already has commits (even only a README), When the Admin saves the URL, Then nothing is pushed, merged, forced or re-cloned, the URL is not stored, the entry stays local, and the Admin sees why.
- Given invalid or missing sign-in, an unknown URL or a network error, When the Admin saves the URL, Then Publish fails with the cause shown, the entry stays local, the URL is not stored, and saving again retries; the entry is never Stale because of it.
- Given a Turn has uncommitted changes, When the URL is saved, Then only committed history is pushed, the pending files are untouched, and Publish does not wait for the Turn.
- Given Publish uses the configured sign-in (token or GitHub CLI), When it pushes, Then it uses the same authentication as Push and never prints the token.
- Given the Admin edits an entry that already has a remote, When the URL changes, Then the existing behaviour of TASK-0005 applies and Publish is not involved.
- Given the Admin saves a URL for a Local Agent Repository, When the form returns, Then the Admin sees progress and the result in English and German.

## Estimated File / Module Footprint (hint, not a commitment)

- Likely `gitenv.py` (`Checkout.publish`, empty-remote check via the remote's refs), `web.py` (settings save, error mapping), `static/app.js`, `static/i18n/*.js`, `tests/test_git.py` (local bare repositories as remotes), `tests/test_environments.py`, `REQUIREMENTS.md` (R4.1, R6.3)

## Definition of Done

- Tests green (`pytest`) · `pre-commit run --all-files` clean (ruff, mypy, mdformat) · docs updated for the requirements touched · no open ADR conflicts
- `Delivered Artifacts` block completed and accurate
- Any new external dependencies recorded in `tasks/DEPENDENCIES.md`
- Persisted keys and contracts unchanged (`env_id`, `environments`, `user_id`, id `default`, `Current user: <alias>`, Tool names, `.family_assist.yaml` keys, `/data` layout); a data directory written by the previous version still loads
- Tests use local bare repositories as empty and non-empty remotes; no network access

## Consumed Interfaces

<!-- Filled by the Lead Agent in Phase 3 from the Delivered Artifacts of: TASK-0011-local-agent-repository -->

- _(to be filled before this task starts)_

## Delivered Artifacts

<!-- Filled by the Worker AFTER implementation. Be exact: downstream tasks depend on this information. -->

- _(not yet delivered)_
