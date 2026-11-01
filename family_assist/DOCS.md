# Family Assist

A chat assistant for the family, backed by Ollama. Its behaviour and files come from one git repository (the Agent Environment) that an admin configures in the add-on's UI.

## Setup

1. Set `ollama_url` (and `ollama_api_key` if your Ollama needs one) and `default_model` in the add-on options. The model must support tool calling.
2. Open Family Assist, go to **Admin**, enter the repository URL (https), the branch and, for private repositories, an access token. Save; the first Sync starts automatically.

   Instead of a token you can choose **GitHub CLI sign-in**: click *Sign in with GitHub*, open the shown link and enter the code. Note that this grants access to all repositories of that GitHub account; a fine-grained token limited to the one repository is the narrower choice.
3. Optionally enable **Commit Permission** (the assistant may change files; every changed turn becomes a commit) and **Push Permission**.

## Rules inside the repository

Optional file `.family_assist.yaml` in the repository root, with three optional lists:

- `hidden`: paths (`.gitignore` syntax) the assistant cannot see.
- `readonly`: paths (`.gitignore` syntax) the assistant can read but not change.
- `tools`: restricts the assistant to the listed tools (`list_dir`, `find`, `grep`, `read_file`, `create_file`, `write_file`, `append_file`, `replace_in_file`).

`.git`, `.family_assist.yaml` and every `AGENTS.md` are always protected. The root `AGENTS.md` is the system prompt; an optional `modell:` in its front matter selects the model.

## Options

| Option | Meaning |
| -- | -- |
| `ollama_url`, `ollama_api_key` | Ollama endpoint and optional API key (used only by the backend) |
| `default_model`, `vision_model` | Chat model and optional model for messages with photos |
| `num_ctx` | Context window requested from Ollama |
| `sync_interval_minutes` | Periodic Sync; 0 disables |
| `queue_enabled`, `max_parallel_generations` | FIFO queue for generations |
| `max_tool_calls_per_turn`, `max_tool_result_kb` | Limits per turn |
