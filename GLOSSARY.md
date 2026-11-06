# Family Assist

A Home Assistant app that lets Family Members chat with a locally hosted generative AI whose behaviour, knowledge and working files come from an Agent Repository. Terms of an Agent Repository's own content, such as students or curricula, belong to that repository's own glossary, not here.

## Language

**App**:
Family Assist as installed in Home Assistant, with its own container and web interface.
_Avoid_: Add-on, custom integration, integration

## People and chats

**Family Member**:
A Home Assistant user who chats with the assistant. In technical contexts (code, APIs, the contract with Agent Repositories) a Family Member is called a User.
_Avoid_: Student, child, account

**Admin**:
A Family Member who is a Home Assistant administrator and configures the Agent Repositories.
_Avoid_: Parent, owner, superuser

**Acting As**:
An Admin using the assistant in the name of another Family Member, so that the Chat belongs to that Family Member; it is also how an Admin reads that Family Member's Chats.
_Avoid_: Impersonation, switching user

**Alias**:
The name by which the assistant knows a Family Member; an Agent Repository can use it to find that person's profile.
_Avoid_: Nickname, display name, username

**Chat**:
A thread of Turns owned by exactly one Family Member and belonging to exactly one Agent Repository; it is deleted together with that Agent Repository.
_Avoid_: Conversation, session, chat history

**Title**:
The short name of a Chat, generated from its first message and renamable by its owner.
_Avoid_: Teaser, name, subject

**Deleted Chat**:
A Chat its owner deleted, which an Admin can still restore until its retention period ends.
_Avoid_: Trash, archived chat

**Turn**:
One message from a Family Member together with the assistant's complete reply, including everything the assistant read or changed to produce it.
_Avoid_: Request, exchange

**Question**:
A single question the assistant puts to the Family Member in the middle of a Turn; the Turn waits for the answer, which the Family Member or an Admin Acting As may give.
_Avoid_: Prompt, form, clarification

**Queue**:
The first-in-first-out line in which Turns wait while the model is busy with other Turns.
_Avoid_: Backlog, job list

## Agent Repository

**Agent Repository**:
A git repository and branch with an optional remote, configured by the Admin, whose `AGENTS.md` and supporting files define how the assistant behaves and what it can read or change. It remains the same Agent Repository when its URL or branch is changed. The Admin may configure several; each Chat belongs to exactly one.
_Avoid_: Agent Environment, agent directory, workspace, project, repo (when meaning the Checkout)

**Checkout**:
The local working copy of an Agent Repository's branch, which is what the assistant reads and changes.
_Avoid_: Clone, working directory, local repo

**Local Agent Repository**:
An Agent Repository that has no remote yet and exists only as its Checkout, started from a built-in starter `AGENTS.md`; it has nothing to Sync or Push and is never Stale.
_Avoid_: Draft repository, offline repository

**Agent Instructions**:
The `AGENTS.md` files of an Agent Repository; the root file defines how the assistant behaves, nested ones add guidance for their folder.
_Avoid_: Rules (unqualified), prompt

**System Prompt**:
The standing text the model receives with every Turn: a fixed preamble from the App, followed by the root Agent Instructions.
_Avoid_: Prompt (unqualified), preamble

**Skill**:
A curated instruction document the assistant can load on demand from a fixed list.
_Avoid_: Plugin, prompt template

## Repository lifecycle

**Sync**:
Bringing the Checkout of an Agent Repository up to date with its remote, in the background and without waiting for running Turns.
_Avoid_: Update, refresh, pull

**Commit Permission**:
The Admin's switch that allows the assistant to change files in the Checkout, each changed Turn being saved as a commit. From an Agent Repository's point of view it is one of the Fixed Rules.
_Avoid_: Write access, edit mode

**Push Permission**:
The Admin's switch that allows saved commits to be pushed to the remote.
_Avoid_: Upload, publish mode

**Publish**:
The one-time push of a Local Agent Repository's whole history to an empty remote when the Admin provides its URL, whatever Push Permission says; afterwards it is an ordinary Agent Repository.
_Avoid_: Export, migrate, initial push

**Diverged**:
The state of an Agent Repository whose local commits and remote branch can no longer be combined automatically; it is flagged to the Admin and nothing is discarded. A Diverged Agent Repository is Stale.

**Stale**:
The state of an Agent Repository whose last Sync or Push failed, so its Checkout and the remote may differ; Family Members are told to contact the Admin.
_Avoid_: Out of date, broken

## Sandbox

**Tool**:
A named capability from the App's fixed catalog that the assistant can call, such as reading a file or asking a Question.
_Avoid_: Function, plugin, command

**Fixed Rules**:
The limits the App enforces on the assistant whatever an Agent Repository declares, for example that the git internals are hidden, that every `AGENTS.md` and `.family_assist.yaml` are read-only, and that files can only be changed while Commit Permission is on; no Repository Rule can lift or override them.
_Avoid_: Built-in protections, hard-coded limits

**Repository Rules**:
The Hidden Paths, Read-only Paths and Tool Allowlist an Agent Repository declares in its `.family_assist.yaml`; they apply within the Fixed Rules.
_Avoid_: Settings, config, permissions

**Sandbox**:
Everything that limits what the assistant can see and change: the Fixed Rules and the Repository Rules together, the Fixed Rules taking precedence.
_Avoid_: Permissions, guardrails

**Hidden Path**:
A path the assistant cannot see, declared by the Fixed Rules or the Repository Rules; to the assistant the path does not exist.
_Avoid_: Ignored path, excluded path, secret

**Read-only Path**:
A path the assistant can read but never change, declared by the Fixed Rules or the Repository Rules.
_Avoid_: Locked path, protected path

**Tool Allowlist**:
The positive list of Tools the Repository Rules allow the assistant to use; anything not on it is refused.
_Avoid_: Permissions, blocklist
