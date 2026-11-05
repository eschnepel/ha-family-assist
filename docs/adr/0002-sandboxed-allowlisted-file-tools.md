# Give the model sandboxed, allowlisted file tools instead of loading the repository into the prompt

The Agent Environment is too large for the context window (the example repository is several MB of curriculum text), and its `AGENTS.md` expects the model to look things up and write task files. The model therefore gets a small fixed catalog of file tools implemented in the backend. There is no shell, no script execution and no network tool. Every call passes through rules in `.family_assist.yaml` that live in the repository, plus built-in protections that the repository cannot lift. Writing is enabled only by the Admin's Commit Permission, never by the repository itself. We accepted that this requires a tool-calling model and several round trips per Turn (slow on weak hardware) in exchange for an attack surface limited to path-checked file operations.

## Amendment — 2026-11-04

**Reason:** The glossary renamed and sharpened several terms used in this record.
**Decision:** Read "Agent Environment" as "Agent Repository". The rules in `.family_assist.yaml` are the Repository Rules; the "built-in protections" are the Fixed Rules, which also include the Admin's Commit Permission and take precedence over the Repository Rules. Together they form the Sandbox. The decision itself is unchanged.
**Decided by:** human

## Amendment — 2026-11-04

**Reason:** `load_skill` fetches text from a third-party GitHub repository, which contradicts "no network tool" above.
**Decision:** There is no generic network access: no Tool can fetch an arbitrary URL. `load_skill` is the single deliberate exception, limited to the fixed host `raw.githubusercontent.com`, the fixed repository `mattpocock/skills`, a curated list of four skills and the Markdown resource files in their folders, read-only text. It deliberately follows the repository's `main` branch instead of a pinned commit, because the project owner follows that repository's development; the accepted risk is that an upstream change alters the assistant's behaviour without review here.
**Decided by:** human
