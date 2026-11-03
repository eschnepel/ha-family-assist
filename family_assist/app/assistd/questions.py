from __future__ import annotations

import asyncio
import json
import uuid
from dataclasses import dataclass, field

ASK_USER = "ask_user"
KINDS = ("single", "multiple", "text")
MAX_QUESTION_CHARS = 500
MIN_OPTIONS = 2
MAX_OPTIONS = 20
MAX_OPTION_CHARS = 200
MAX_ANSWER_CHARS = 4000
SKIPPED = "The user skipped this question."

SCHEMA = (
    "Ask the user ONE question and wait for the answer. Use it when you need information only the user can give. "
    "Ask several questions by calling this tool several times, one after the other.",
    {
        "type": "object",
        "properties": {
            "question": {"type": "string", "description": "The question text"},
            "kind": {
                "type": "string", "enum": list(KINDS),
                "description": "'single' = pick one option, 'multiple' = pick any number of options, "
                               "'text' = free text answer. Default 'text'",
            },
            "options": {
                "type": "array", "items": {"type": "string"},
                "description": f"The choices; required for 'single' and 'multiple' ({MIN_OPTIONS}-{MAX_OPTIONS} entries)",
            },
            "required": {"type": "boolean", "description": "Default true; false lets the user skip the question"},
        },
        "required": ["question"],
    },
)


class QuestionError(ValueError):
    pass


@dataclass(frozen=True)
class Question:
    text: str
    kind: str
    options: tuple[str, ...]
    required: bool


def parse_question(arguments) -> Question:
    """Validate the arguments of an `ask_user` call as sent by the model."""
    if isinstance(arguments, str):
        try:
            arguments = json.loads(arguments or "{}")
        except ValueError:
            arguments = None
    if not isinstance(arguments, dict):
        raise QuestionError("arguments must be an object")
    text = arguments.get("question")
    if not isinstance(text, str) or not text.strip():
        raise QuestionError("question must be a non-empty string")
    text = text.strip()
    if len(text) > MAX_QUESTION_CHARS:
        raise QuestionError(f"question is longer than {MAX_QUESTION_CHARS} characters")
    kind = arguments.get("kind") or "text"
    if kind not in KINDS:
        raise QuestionError(f"kind must be one of: {', '.join(KINDS)}")
    required = arguments.get("required", True)
    if isinstance(required, str):
        required = required.strip().lower() not in ("false", "0", "no")
    options: tuple[str, ...] = ()
    if kind != "text":
        raw = arguments.get("options")
        if not isinstance(raw, list) or not all(isinstance(o, str) and o.strip() for o in raw):
            raise QuestionError("options must be a list of non-empty strings")
        options = tuple(dict.fromkeys(o.strip() for o in raw))
        if not MIN_OPTIONS <= len(options) <= MAX_OPTIONS:
            raise QuestionError(f"give {MIN_OPTIONS} to {MAX_OPTIONS} different options")
        if any(len(o) > MAX_OPTION_CHARS for o in options):
            raise QuestionError(f"an option is longer than {MAX_OPTION_CHARS} characters")
    return Question(text, kind, options, bool(required))


@dataclass
class PendingQuestion:
    """A question shown to the user; the agent turn waits on `future` for the answer as tool result text."""

    question: Question
    id: str = field(default_factory=lambda: uuid.uuid4().hex)
    future: asyncio.Future = field(default_factory=lambda: asyncio.get_running_loop().create_future(), repr=False)

    def public(self) -> dict:
        q = self.question
        return {"id": self.id, "question": q.text, "kind": q.kind, "options": list(q.options), "required": q.required}

    def answer(self, value, skipped: bool = False) -> None:
        """Check the user's answer against the question and hand it to the waiting turn."""
        if self.future.done():
            raise QuestionError("this question was already answered")
        q = self.question
        if isinstance(value, str) and not value.strip():
            value = None
        if skipped or value is None or value == []:
            if q.required:
                raise QuestionError("this question must be answered")
            self.future.set_result(SKIPPED)
            return
        if q.kind == "text":
            if not isinstance(value, str):
                raise QuestionError("the answer must be text")
            value = value.strip()
            if len(value) > MAX_ANSWER_CHARS:
                raise QuestionError(f"the answer is longer than {MAX_ANSWER_CHARS} characters")
            result = value
        elif q.kind == "single":
            if not isinstance(value, str) or value not in q.options:
                raise QuestionError("the answer must be one of the options")
            result = value
        else:
            if not isinstance(value, list) or not all(isinstance(v, str) and v in q.options for v in value):
                raise QuestionError("the answer must be a list of the options")
            result = "\n".join(o for o in q.options if o in value)
        self.future.set_result(result)
