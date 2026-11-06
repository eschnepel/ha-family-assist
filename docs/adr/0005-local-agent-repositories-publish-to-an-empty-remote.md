# Allow local Agent Repositories and publish them only to an empty remote

**Status:** proposed

An Agent Repository used to need a remote URL from the start, so the Admin had to create and connect a remote before the family could try the assistant, and a clone of an empty remote failed. A Local Agent Repository now starts as a Checkout with a built-in starter `AGENTS.md` and one initial commit, and works like any other Agent Repository except that there is nothing to Sync or Push and it is never Stale. When the Admin provides a URL, the App publishes: it pushes the whole committed history once to the entry's branch, automatically and whatever Push Permission says, but only if the remote has no refs. The entry keeps its id and its Chats.

We rejected merging into or forcing over a non-empty remote, because that can silently tangle or destroy someone else's history, and a clear refusal that leaves the Agent Repository local is easier to recover from. We also rejected clearing the URL of an Agent Repository that has a remote, which would sever it from work already published.

## Consequences

Until it is published, a Local Agent Repository has no copy outside the App's own data, so removing it discards everything and the confirmation says so. Because `AGENTS.md` is read-only for the assistant, the Admin can only change the starter instructions after publishing, by editing the remote.
