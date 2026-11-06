# Follow-ups from the glossary grill (2026-11-04)

Input for Phase 0 (`tasks/adr-summary.md`) and Phase 1 (capabilities). These are **not** TASK files yet. `GLOSSARY.md` is final and is the authority for all terms below. Persisted keys and contracts stay unchanged: `env_id`, `environments`, `user_id`, the id `default`, the `Current user: <alias>` line, the tool names (`ask_user`, `load_skill`) and the keys of `.family_assist.yaml`.

| ID | Change | Source | Touches (rough size) |
| -- | -- | -- | -- |
| GF-1 | Rename Agent Environment → Agent Repository. `gitenv.AgentEnvironment` (really the checkout handler) becomes `Checkout`; `EnvConfig` becomes the Agent Repository entry. | Round 1-2 | UI + `de.js`/`en.js`, DOCS, REQUIREMENTS, code, tests (~100+ hits) |
| GF-2 | Rename Conversation → Chat (`ConversationStore`, `/api/conversations`, variables, docs) and `teaser` → Title (`make_teaser`, `truncate_teaser`). Stored file layout and keys stay. | Round 1 | code, tests, UI, docs (~120 hits) |
| GF-3 | Rename Add-on → App in DOCS, README, `config.yaml` text, translations, UI. | Round 1 | docs/config (~14 hits) |
| GF-4 | `Rules` → `RepositoryRules`, `BUILTIN_HIDDEN`/`BUILTIN_READONLY` → Fixed Rules naming; REQUIREMENTS R5.6 and R6.1 describe Commit Permission as a Fixed Rule. | Round 2-3 | `rules.py`, `tools.py`, tests, REQUIREMENTS |
| GF-5 | Removal deletes Chats and Checkout permanently (**ADR 0003**): removal marker, startup sweep, one-time adoption of existing orphans, explicit confirmation naming Chat count and unsaved work, updated REQUIREMENTS R4.1/R4.1a. | Round 2, 4 | `web.py`, store, settings, UI confirm dialog, tests |
| GF-6 | Optimistic Sync and Push (**ADR 0004**): fast-forward only, never touch pending files, no BusyError wait, network steps outside the lock, Stale on failure of Sync or Push; REQUIREMENTS R4.3, R6.3-R6.5 (reword R6.5). | Round 3 | `gitenv.py`, `web.py`, tests with a concurrent Turn |
| GF-7 | Stale notice: Family Members see "contact the Admin" while an Agent Repository is Stale, the Admin sees the details; Diverged is one cause of Stale. | Round 3 | API state field, UI banner (en + de), tests |
| GF-9 | Cancel running Turns when their Chat is deleted or their Agent Repository is removed (**ADR 0003 amendment**): a registry of running Turn tasks, deletion cancels instead of answering 409, Questions ended, Queue slots released. Rename stays refused while a Turn runs. The cancelled Turn is rolled back (tracked files reset, created files removed, no commit). | Phase 0 | `web.py`, `agent.py`, `questions.py`, `genqueue.py`, tests |
| GF-8 | Align remaining docs with the glossary (REQUIREMENTS, DOCS, README, UI copy) once GF-1 to GF-4 land; Deleted Chat restore stays Admin-only. Known doc defects to fix on the way: R5.2 omits `load_skill` from the default Tool Allowlist (code includes it); R3.5 says messages are "queued" per Chat but the code answers 409 while a Turn runs; R4.4 phrasing of System Prompt vs Agent Instructions. | all | docs |

## Suggested order

1. GF-4, GF-1, GF-2, GF-3: mechanical renames, no behaviour change; do first so later work uses the final names.
1. GF-6, then GF-7 (Stale depends on the failure path of GF-6).
1. GF-9, then GF-5 (removal cancels running Turns, so GF-5 depends on GF-9).
1. GF-8 last.

## ADR status

- 0003, 0004: `accepted`, each with a 2026-11-04 amendment.
- 0001, 0002: amendments recorded (terminology; `load_skill` exception, unpinned by decision).

## Not decided (suggestion only)

- Document the contract Agent Repository authors can rely on (the `Current user: <alias>` line, `ask_user`, `load_skill`, `.family_assist.yaml` keys) in `DOCS.md`.
