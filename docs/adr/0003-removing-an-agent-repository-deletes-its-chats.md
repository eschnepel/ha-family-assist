# Removing an Agent Repository permanently deletes its Chats

**Status:** accepted

A Chat belongs to exactly one Agent Repository and is meaningless without it: its file references, Tool results and Agent Instructions all come from that repository. Until now removal only hid the Chats, and re-adding the same URL created a new Agent Repository with a new id, so they stayed on disk, unreachable and never purged. Routing them through Deleted Chat does not help either, because a restore would have no Agent Repository to return to. Removal therefore deletes the Checkout and all its Chats permanently, and the Admin must explicitly confirm when the Checkout holds unpushed commits or uncommitted changes, since those are lost with it.

Deleting the Chats can be cut off, for example when the App stops or storage is briefly unavailable, so removal first writes a removal marker for the Agent Repository's id, and a sweep at every startup deletes the Chats of marked ids and then clears the marker. We rejected sweeping every Chat whose Agent Repository id is missing from the settings: a damaged or restored settings file would then delete every Family Member's Chats. Chats orphaned by earlier versions are adopted once, at the first startup after the update, by marking their ids, and only when the settings load cleanly and list at least one Agent Repository; the legacy id `default` is never treated as removed.

## Consequences

Removal is irreversible for Family Members' Chats, so the confirmation text must name the number of Chats that will be deleted.

## Amendment — 2026-11-04

**Reason:** A Turn can be running when its Chat or Agent Repository disappears and would then save into a Chat that should no longer exist. Today deleting a Chat is refused while a Turn runs, and removing an Agent Repository does not look at running Turns.
**Decision:** Removing an Agent Repository first cancels the running Turns of all its Chats, ends their waiting Questions and releases their Queue slots, and only then deletes. Deleting a single Chat likewise cancels its running Turn instead of being refused. A cancelled Turn is rolled back: everything it wrote but did not commit is restored (tracked files reset, newly created files removed), leaving no commit and no uncommitted file, while Turns that end by error or limit still commit what they wrote.
**Decided by:** human
