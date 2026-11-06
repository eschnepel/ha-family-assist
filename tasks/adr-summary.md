# ADR Summary (architectural ground truth)

Sources: `docs/adr/0001`-`0005` (0001-0004 accepted; 0005 proposed, marked as such). Where the ADRs are silent, stack and limits come from `REQUIREMENTS.md` and are marked [REQ]. Terms follow `GLOSSARY.md`. This file is attached to every worker's context: keep it short.

## Tech stack and framework decisions

- Delivered as a Home Assistant App (not a custom integration) with its own container and ingress web UI (0001).
- Python 3 with FastAPI, vanilla-JS frontend without build step, server-sent events, the `git` CLI; targets Raspberry Pi 5 (`aarch64`) and `amd64`; no native-compile dependencies [REQ R1.3, R1.4].
- Ollama runs outside the App; a tool-calling model is mandatory (0002, [REQ R2.1, R2.4]).
- The assistant gets a small fixed catalog of Tools implemented in the backend; the Agent Repository is never loaded into the prompt (0002).

## Architecture patterns

- Backend-mediated, path-checked file Tools over a per-Agent-Repository Checkout (0002).
- Sandbox = Fixed Rules (including Commit Permission) over Repository Rules from `.family_assist.yaml`; Fixed Rules always win; the repository can never grant write Tools or lift a Fixed Rule (0002, amended).
- A Chat belongs to exactly one Agent Repository; an Agent Repository keeps its identity when URL or branch change [GLOSSARY, REQ R4.1].
- One commit per Turn that changed files; Push is optional and separately permitted [REQ R6].
- Sync and Push are optimistic background operations: fast-forward (Push: rebase) only, never touching a file with uncommitted changes, never waiting for Turns; network steps (clone, fetch, push) run outside the lock; failure of Sync or Push makes the Agent Repository Stale, the Admin sees details, Family Members are told to contact the Admin (0004).
- A Turn keeps the System Prompt and Repository Rules it started with; its reads may see newer files after a Sync (0004).
- Removing an Agent Repository first cancels the running Turns of its Chats (Questions ended, Queue slots released); deleting a single Chat likewise cancels its running Turn instead of being refused; a cancelled Turn is rolled back, leaving no commit and no uncommitted file (0003, amended).
- Removing an Agent Repository permanently deletes its Checkout and Chats; a removal marker plus a sweep at every startup finishes interrupted deletions; existing orphans are adopted once, only when settings load cleanly and list at least one Agent Repository; `default` is never treated as removed (0003).
- An Agent Repository may be local (no remote): it starts from a built-in starter `AGENTS.md` and an initial commit, has nothing to Sync or Push and is never Stale. Providing a URL publishes its whole history once to an empty remote only, whatever Push Permission says; the entry keeps its id and Chats (0005, proposed).

## Non-functional requirements

- Isolation: model-driven file access stays away from Home Assistant's secrets; attack surface limited to path-checked file operations (0001, 0002).
- Performance: several model round trips per Turn are accepted, slow on weak hardware (0002).
- Availability: updates from the remote are never blocked by running Turns (0004).
- Data safety: Chat deletion on removal is irreversible; the Admin must confirm explicitly, naming the number of Chats and any unsaved work (0003).
- Security: only ingress reaches the backend; model output is untrusted; no Tool can read secrets or anything outside the Checkout [REQ R7].

## Explicit exclusions

- No custom integration; no Home Assistant entities, services or cameras in v1 (0001).
- No shell, no script execution, no generic network access (0002); `load_skill` is the single exception: fixed host and repository (`mattpocock/skills`), four curated skills, read-only text, deliberately tracking `main` (0002, amended).
- No delete, move or rename Tools in v1 [REQ R5.1]; no SSH deploy keys in v1 [REQ R4.2].
- No hard reset and no waiting on Turns in Sync (0004).
- No restore of Chats of a removed Agent Repository (0003).
- No merge, force or re-clone when publishing a Local Agent Repository; no content import (host directory, archive) in v1; the URL of an Agent Repository that has a remote cannot be cleared (0005, proposed).
- The App adds no content filter of its own [REQ R4.6].

## Open items

None. Phase 0 closed.

## UI wording (pending Gate 2 approval)

- The model-facing text (System Prompt preamble and chat-title prompt in `family_assist/translations/*.yaml`) **is** part of the vocabulary renames (G2-2: the project owner adapts the existing Agent Repository's own files). Its structure and the `Current user:` / `Aktueller Benutzer:` line stay.
- German UI terms: Agent Repository = "Agent-Repository" (was "Agent-Umgebung"/"Umgebung"), Chat = "Chat" (was "Unterhaltung"), Title = "Titel", App = "App" (was "Add-on"), Repository Rules = "Repository-Regeln", Fixed Rules = "Feste Regeln". German UI addresses the user informally ("Du"). Stale notice (de): "Die Dateien des Assistenten sind möglicherweise nicht aktuell. Bitte wende dich an den Admin."
