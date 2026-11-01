# Family Assist - Requirements

Settled requirements from the design interview. Terms follow [GLOSSARY.md](./GLOSSARY.md); decisions with lasting consequences are in [docs/adr](./docs/adr).

## 1. Product

- R1.1 Family Assist is a Home Assistant add-on ("app") named "Family Assist" (slug `family_assist`) with an ingress web UI. See ADR 0001.
- R1.2 It is a generative-AI chat for family members, backed by Ollama. Home Assistant provides authentication, ingress and hosting only. Home Assistant entities, services and cameras are out of scope for v1.
- R1.3 Target platform is a Raspberry Pi 5. The add-on builds for `aarch64` and `amd64` (the latter for local testing). It has no native-compile dependencies.
- R1.4 Stack: Python 3 with FastAPI, a vanilla-JS frontend without build step, server-sent events for streaming, and the `git` CLI.
- R1.5 The UI is available in German and English. The assistant's own language is whatever the Agent Environment prescribes.

## 2. Ollama

- R2.1 Ollama runs outside the add-on (separate host or Ollama add-on). It is never bundled.
- R2.2 Add-on options: `ollama_url`, `ollama_api_key` (optional, password type), `default_model`, `vision_model` (optional), `sync_interval_minutes` (default 60, 0 disables), `queue_enabled` (default true), `max_parallel_generations` (default 1, 1-4), `max_tool_calls_per_turn` (default 25), `max_tool_result_kb` (default 32).
- R2.3 The API key is used only by the backend's Ollama client. It never appears in prompts, tool results, logs or responses to the browser (the admin page only shows whether a key is set). Use HTTPS if Ollama is not on the local network.
- R2.4 A tool-calling model is mandatory. The admin page warns when the configured model reports no tool capability.
- R2.5 The model is `default_model`, unless the front matter of the root `AGENTS.md` sets `modell:`. Family members do not choose models.
- R2.6 Photos can be attached to a message and are passed to Ollama as images. They use `vision_model` when set, otherwise the main model.
- R2.7 Requests go through a FIFO queue when `queue_enabled`; at most `max_parallel_generations` generations run at once and the UI shows the queue position. With the queue disabled, requests go straight to Ollama. Streaming is used; the Ollama read timeout is 10 minutes.

## 3. People and conversations

- R3.1 Family members are Home Assistant users. Home Assistant administrators are admins.
- R3.2 The assistant is told only "Current user: <alias>". The alias defaults to the Home Assistant name; the admin can override it per user. The app does not parse repository-specific profile files.
- R3.3 An admin can act as any family member. A visible banner shows when acting as; conversations then belong to that family member.
- R3.4 Conversations are stored per family member in `/data`. A family member sees only their own conversations; an admin can read all (by acting as). Family members are told that the admin can read conversations.
- R3.5 Messages are queued per conversation: only one turn per conversation runs at a time.

## 4. Agent Environment

- R4.1 Exactly one Agent Environment (one git repository) is configured by the admin in the admin UI: URL (https), branch, token, Commit Permission, Push Permission, aliases.
- R4.2 Private repositories are supported with an HTTPS personal access token (fine-grained, write access only when Commit/Push Permission is used). The token is stored in `/data`, never shown again, and passed to `git` only per call; it is not written to `.git/config` or to the stored URL. SSH deploy keys are not supported in v1.
- R4.2a Alternatively the admin can sign in with the GitHub CLI (device flow): the admin page shows a one-time code and `https://github.com/login/device`, the app polls until the sign-in completes, then triggers a Sync. The CLI keeps its credentials in `/data/gh`; git receives its token per call exactly like a personal access token, and the token is never shown, logged or readable by the assistant. The sign-in grants access to all repositories of that GitHub account (a GitHub CLI limitation), which the admin page states; a fine-grained token is the narrower option. Admins can sign out from the same page.
- R4.3 Sync: a manual "Sync now" button plus a periodic pull of the configured branch every `sync_interval_minutes`. A failed Sync keeps the last good checkout.
- R4.4 The root `AGENTS.md` is the system prompt, preceded by a short fixed app preamble (tool rules, current user, date). The repository can never override the tool sandbox.
- R4.5 A nested `AGENTS.md` is appended to the tool result the first time the assistant reads in its folder during a conversation (32 KB cap each), unless that folder is a Hidden Path.
- R4.6 The app adds no content filter of its own; behaviour comes from the repository's `AGENTS.md`.

## 5. Tools and sandbox (ADR 0002)

- R5.1 The assistant has a fixed catalog of tools implemented in the backend, with no shell, no script execution and no network access:

  | Tool | Kind | Purpose |
  | -- | -- | -- |
  | `list_dir` | read | list a folder |
  | `find` | read | glob for file names |
  | `grep` | read | regex search in text files |
  | `read_file` | read | read a file, optionally a line range |
  | `create_file` | write | create a new file, fails if it exists |
  | `write_file` | write | create or overwrite a whole file |
  | `append_file` | write | append text to a file |
  | `replace_in_file` | write | one or several exact-string replacements, all-or-nothing, each string must match exactly once |

  There is no delete, move or rename in v1.
- R5.2 Tool Allowlist: only listed tools are usable. A call to an unlisted tool is rejected with an error result. Without `tools` in `.family_assist.yaml` the list is the four read tools, plus the four write tools when Commit Permission is on.
- R5.3 `.family_assist.yaml` (optional, repo root) is the single repository config file, a YAML mapping with the optional lists `tools`, `hidden` and `readonly`. Invalid YAML or a wrongly typed key is ignored with an admin warning. `tools` holds tool names; when present, only the listed tools are enabled, and it can only narrow the catalog, never grant write tools while Commit Permission is off. Unknown names are ignored with an admin warning.
- R5.4 `hidden` and `readonly` hold `.gitignore`-syntax patterns (globs, `/` anchoring, `!` negation). Root file only; nested copies are not supported. They apply to everyone including admins and are maintained outside Home Assistant.
- R5.5 A Hidden Path behaves as if it does not exist: absent from `list_dir`, `find`, `grep` and context loading; reads and writes return "not found". A Hidden Path's nested `AGENTS.md` is never loaded. A rule that matches the root `AGENTS.md` is ignored with an admin warning.
- R5.6 Built-in protections that no rule can lift: `.git` is hidden; `.family_assist.yaml` and every `AGENTS.md` are read-only.
- R5.7 Paths are resolved with `realpath` and must stay inside the checkout (symlinks cannot escape); the resolved path is checked against the rules again.
- R5.8 The rules are defined only in the repository; the admin UI shows the effective rules read-only. Rule changes take effect after Sync.
- R5.9 Limits: write files are capped at 256 KB; each tool result at `max_tool_result_kb`; each turn at `max_tool_calls_per_turn` calls. When the limit is reached the turn ends with a visible note.
- R5.10 Tool calls are shown in the chat, collapsed by default; expanding shows the full call and result in a scrollable mini panel. They are always visible to the admin.

## 6. Writing back to git

- R6.1 Write tools exist only when the admin enables Commit Permission in the UI, never from the repository.
- R6.2 One commit per turn that changed files, with an app-generated message such as `Assist (Richard): Mathe/Klasse-5/Richard/Bruchrechnung.md`. Author is the alias; committer is `Family Assist <family-assist@localhost>`; an `Acted-By: <admin alias>` trailer is added when acting as another family member.
- R6.3 Push Permission is a separate admin switch, off by default. When on, the app rebases onto the remote branch and pushes after each commit. When off, the UI shows the number of unpushed commits and a "Push now" button.
- R6.4 On a rebase conflict the app aborts the rebase, keeps local commits, and flags the environment as "diverged" for the admin. Nothing is discarded.
- R6.5 Git operations are serialized with one lock.

## 7. Security

- R7.1 Only Home Assistant ingress can reach the backend (source address check); identity comes from ingress headers and is resolved against Home Assistant's user list; admin status is never taken from the client.
- R7.2 Model output is untrusted: the UI escapes HTML before rendering a restricted Markdown subset and sets a strict content security policy.
- R7.2a Math (`$...$`, `$$...$$`, `\(...\)`, `\[...\]`) is typeset with a vendored KaTeX and Mermaid code blocks are rendered with a vendored Mermaid in strict mode. Diagrams are shown as images, so nothing inside them can run or restyle the page; a diagram that fails to render falls back to its source. Both libraries load on demand and need no internet access.
- R7.3 The model has no tool that can read the Ollama API key, the git token, add-on options or anything outside the checkout.

## 8. Example Agent Environment

`Lernbegleiter` (private, `eschnepel/Lernbegleiter`) is the reference Agent Environment: a root `AGENTS.md` with YAML front matter, per-student profiles, glossaries and generated curriculum files. It ships this config file:

```yaml
# .family_assist.yaml
hidden:
  - /Scripts/
readonly:
  - Lehrplan-*/
  - GLOSSARY-TEMPLATE.md
  - AUFGABE-TEMPLATE.md
```

It has no `tools` key, so the default list applies.

## 9. Implementation notes

- Added during implementation: option `num_ctx` (default 16384). Ollama otherwise truncates long prompts silently.
- Home Assistant does not pass the user's language to ingress apps, so the UI language follows the browser language (German or English), with a manual switch.
- Past turns are replayed to the model as plain user and assistant text only; tool exchanges are kept for the current turn so that long conversations stay within the context window.
