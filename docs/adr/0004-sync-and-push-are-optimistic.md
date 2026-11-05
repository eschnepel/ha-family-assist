# Make Sync and Push optimistic: they never wait and never overwrite uncommitted work

**Status:** accepted

Sync and Push used to be serialized with file writes and were refused ("try again shortly") while a Turn held uncommitted changes, which lasts as long as a Question is waiting. Waiting for running Turns would stall every update behind a slow model or an unanswered Question, so Sync and Push now run in the background without waiting. Because the old Sync ended in `git reset --hard`, which was safe only thanks to that refusal and would otherwise silently destroy a Turn's unsaved writes, they update the Checkout by fast-forward (Push by rebase) and never touch a file with uncommitted changes. They fail only when incoming changes hit a file a Turn has pending, or on a network or merge conflict; the Agent Repository is then Stale, the Admin sees the details, and Family Members are told to contact the Admin.

A Turn keeps the System Prompt and Repository Rules it started with, while its reads may see newer files after a Sync. We accepted that a Turn can observe files changing under it, and that Family Members occasionally see a Stale notice that waiting would have avoided, in exchange for updates that are never blocked.

## Amendment — 2026-11-04

**Reason:** One lock serialized all git operations, including network steps, so a Turn's write or commit could wait behind a slow fetch: the mirror image of what this ADR prevents.
**Decision:** Network steps (clone, fetch, push) run outside the lock; only the local steps (fast-forward or rebase, file write, commit) take it. A failed Push makes the Agent Repository Stale just like a failed Sync.
**Decided by:** human
