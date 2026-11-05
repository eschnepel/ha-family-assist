# Task Index

## Task table

Execution is strictly sequential in the order below (capabilities touch overlapping files). See `tasks/adr-capability.md` for the capability each task implements.

| Slug | Title | Status | Dependencies | Worker |
| -- | -- | -- | -- | -- |
| TASK-0001-agent-repository-vocabulary | Agent Repository vocabulary | todo | - | - |
| TASK-0002-chat-and-title-vocabulary | Chat and Title vocabulary | todo | TASK-0001-agent-repository-vocabulary | - |
| TASK-0003-app-vocabulary | App vocabulary | todo | TASK-0002-chat-and-title-vocabulary | - |
| TASK-0004-rules-vocabulary | Fixed Rules and Repository Rules vocabulary | todo | TASK-0003-app-vocabulary | - |
| TASK-0005-sync-never-waits | Sync that never waits | todo | TASK-0004-rules-vocabulary | - |
| TASK-0006-push-never-waits | Push that never waits | todo | TASK-0005-sync-never-waits | - |
| TASK-0007-stale-notice | Stale notice | todo | TASK-0006-push-never-waits | - |
| TASK-0008-delete-chat-cancels-turn | Deleting a Chat cancels its running Turn | todo | TASK-0007-stale-notice | - |
| TASK-0009-remove-repository-deletes-chats | Removing an Agent Repository deletes its Chats | todo | TASK-0008-delete-chat-cancels-turn | - |
| TASK-0010-startup-removal-sweep | Interrupted removals finish at startup | todo | TASK-0009-remove-repository-deletes-chats | - |
| TASK-0011-docs-match-behaviour | Documentation matches behaviour | todo | TASK-0010-startup-removal-sweep | - |

## Refinement Log

| Date | Trigger task | Action | Reason |
| -- | -- | -- | -- |
