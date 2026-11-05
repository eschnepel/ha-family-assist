# ADR Capabilities (Phase 1)

Derived thematically from ADRs 0001-0004 (all accepted, amended 2026-11-04) and `GLOSSARY.md`. The App already exists, so each capability is the **delta** that makes behaviour or vocabulary match the ADRs. Every capability is end-to-end demonstrable, deliberately narrow, and says what it does *not* cover. File structure is not prescribed.

**Unchanged by every capability** (contracts and persisted data): `env_id`, `environments`, `user_id`, the id `default`, the `Current user: <alias>` line, the Tool names, the keys of `.family_assist.yaml`, and the stored layout in `/data`. A data directory written by the previous version must keep loading.

## A. Vocabulary (no behaviour change)

### CAP-01 Agent Repository vocabulary

- **Outcome:** Family Members, Admins, doc readers and developers meet "Agent Repository" and "Checkout" instead of "Agent Environment", "environment" and "repo" in the UI (en + de), docs, identifiers and tests; `gitenv.AgentEnvironment` becomes `Checkout`.
- **Demonstrable by:** a vocabulary check finds no retired term outside the persisted-key allowlist; the full suite passes; an old data directory loads unchanged.
- **Not covered:** any behaviour change.
- **ADRs:** 0002 (amended) · **Depends on:** -

### CAP-02 Chat and Title vocabulary

- **Outcome:** "Chat" replaces "Conversation" and "Title" replaces "teaser" everywhere except the stored layout (`ConversationStore`, `/api/conversations`, variables, UI, docs).
- **Demonstrable by:** same vocabulary check for these terms; suite passes; old Chats still open, rename and delete.
- **ADRs:** - (glossary) · **Depends on:** CAP-01

### CAP-03 App vocabulary

- **Outcome:** "App" replaces "add-on" in `DOCS.md`, `README.md`, `config.yaml`, translations and UI.
- **Demonstrable by:** vocabulary check; the App still builds and starts.
- **ADRs:** 0001 (amended) · **Depends on:** CAP-02

### CAP-04 Fixed Rules and Repository Rules vocabulary

- **Outcome:** `Rules` becomes `RepositoryRules`, `BUILTIN_*` becomes Fixed Rules naming, Commit Permission is described as a Fixed Rule, and the admin page's effective-rules view and docs use these terms.
- **Demonstrable by:** vocabulary check; Sandbox tests unchanged and green (every `AGENTS.md` and `.family_assist.yaml` read-only, `.git` hidden, a repository rule matching the root `AGENTS.md` still ignored with a warning).
- **ADRs:** 0002 (amended) · **Depends on:** CAP-03

## B. Updating from the remote

### CAP-05 Sync that never waits

- **Outcome:** A manual or periodic Sync updates the Checkout in the background while Turns run, without waiting for them and without ever losing a Turn's unsaved files.
- **Demonstrable by:** (1) Turn has an uncommitted file, remote changed other files → Sync succeeds, the file is untouched and the Turn still commits it. (2) Remote changed that same file → Sync fails, the file is unmodified, the failure is recorded. (3) Slow fetch → a Turn's write is not delayed. (4) A Turn keeps its System Prompt and Repository Rules; its reads may see newer files.
- **Not covered:** the user-visible notice (CAP-07) and Push (CAP-06).
- **ADRs:** 0004 (amended) · **Depends on:** CAP-04

### CAP-06 Push that never waits

- **Outcome:** Push, after each commit with Push Permission or via "Push now", rebases and pushes in the background under the same rules as CAP-05: network outside the lock, never touching a file with uncommitted changes.
- **Demonstrable by:** same four scenarios for Push; a rebase conflict aborts, keeps local commits and flags Diverged.
- **ADRs:** 0004 (amended) · **Depends on:** CAP-05

### CAP-07 Stale notice

- **Outcome:** When Sync or Push fails the Agent Repository is Stale: the Admin sees the cause, Family Members see a notice to contact the Admin while it lasts, and a later success clears it. Diverged is one cause.
- **Demonstrable by:** force a failure → notice in en and de for a Family Member, details for the Admin; fix the cause and Sync → notice disappears; the assistant keeps working on the last good Checkout.
- **Not covered:** resolving Diverged inside the App.
- **ADRs:** 0004 · **Depends on:** CAP-06

## C. Removing Chats and Agent Repositories

### CAP-08 Deleting a Chat cancels its running Turn

- **Outcome:** Deleting a Chat while its Turn runs cancels the Turn instead of answering 409: a waiting Question ends, the Queue slot is released, and the Turn is rolled back (no commit, no uncommitted file). The Chat becomes a Deleted Chat as before.
- **Demonstrable by:** delete during generation, during a Question and during a file write → Turn stops, no stuck pending marker, Sync and Push still work, Admin can restore the Deleted Chat. Rename stays refused while a Turn runs.
- **ADRs:** 0003 (amended) · **Depends on:** CAP-07

### CAP-09 Removing an Agent Repository deletes its Chats

- **Outcome:** Removal cancels the running Turns of its Chats, then permanently deletes Checkout and Chats after an explicit confirmation naming the number of Chats and any unpushed commits or uncommitted changes.
- **Demonstrable by:** remove with running Turns, with unsaved work and without → confirmation text correct, Turns cancelled, Checkout and Chats gone, other Agent Repositories untouched, re-adding the same URL starts empty.
- **ADRs:** 0003 (amended) · **Depends on:** CAP-08

### CAP-10 Interrupted removals finish at startup

- **Outcome:** Removal first writes a removal marker; at every startup the Chats of marked ids are deleted and the marker cleared. Chats orphaned by earlier versions are adopted once.
- **Demonstrable by:** stop the App mid-removal → restart finishes it; damaged or empty settings → nothing deleted; adoption runs only with clean settings listing at least one Agent Repository; `default` never treated as removed.
- **ADRs:** 0003 · **Depends on:** CAP-09

## D. Documentation

### CAP-11 Documentation matches behaviour

- **Outcome:** `REQUIREMENTS.md`, `DOCS.md` and `README.md` describe the accepted behaviour: R4.1, R4.3, R6.3-R6.5 per ADRs 0003/0004; defects R3.5 ("queued" vs 409), R5.2 (`load_skill` in the default Tool Allowlist), R4.4 wording; ADR 0002's no-network rule points to its amendment.
- **Demonstrable by:** a reviewer walks each changed requirement against its capability's tests.
- **ADRs:** all · **Depends on:** CAP-10

## Mapping and scope

| Follow-up | Capability |
| -- | -- |
| GF-1 / GF-2 / GF-3 / GF-4 | CAP-01 / CAP-02 / CAP-03 / CAP-04 |
| GF-6 | CAP-05, CAP-06 |
| GF-7 | CAP-07 |
| GF-9 | CAP-08 |
| GF-5 | CAP-09, CAP-10 |
| GF-8 | CAP-11 |

**Out of scope:** resolving Diverged in the App, documenting the Agent Repository contract (suggestion, undecided), pinning `load_skill` (decided against), restoring Chats of a removed Agent Repository, renaming a Chat while its Turn runs.

**Order:** strictly as numbered. The renames come first so later work uses final names; all capabilities touch overlapping files, so no parallel execution is planned.

**GATE 1: awaiting human approval.**
