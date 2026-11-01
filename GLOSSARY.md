# Family Assist

A Home Assistant app that lets family members chat with a locally hosted generative AI whose behaviour, knowledge and working files come from one git repository.

## Language

**Agent Environment**:
The git repository, checked out locally, whose `AGENTS.md` and supporting files define how the assistant behaves and what it can read or change. The Admin may configure several; each Conversation belongs to exactly one.
_Avoid_: Agent directory, workspace, repo (when meaning the checkout), project

**Family Member**:
A Home Assistant user who chats with the assistant.
_Avoid_: User (unqualified), student, child, account

**Admin**:
A Home Assistant administrator who configures the Agent Environment and may read every Conversation.
_Avoid_: Parent, owner, superuser

**Acting As**:
An Admin using the assistant in the name of another Family Member, so that the Conversation belongs to that Family Member.
_Avoid_: Impersonation, switching user

**Alias**:
The name by which the assistant knows a Family Member.
_Avoid_: Nickname, display name, username

**Conversation**:
A chat thread owned by exactly one Family Member.
_Avoid_: Session, chat history

**Turn**:
One message from a Family Member together with the assistant's complete reply, including everything the assistant read or changed to produce it.
_Avoid_: Request, exchange

## Environment lifecycle

**Sync**:
Bringing the checkout of the Agent Environment up to date with its remote.
_Avoid_: Update, refresh, pull

**Commit Permission**:
The Admin's switch that allows the assistant to change files in the Agent Environment, each changed Turn being saved as a commit.
_Avoid_: Write access, edit mode

**Push Permission**:
The Admin's switch that allows saved commits to be published to the remote.
_Avoid_: Upload, publish mode

## Sandbox

**Hidden Path**:
A path the assistant cannot see; to it the path does not exist.
_Avoid_: Ignored path, excluded path, secret

**Read-only Path**:
A path the assistant can read but never change.
_Avoid_: Locked path, protected path

**Tool Allowlist**:
The positive list of named capabilities the assistant is allowed to use; anything not on it is refused.
_Avoid_: Permissions, blocklist
