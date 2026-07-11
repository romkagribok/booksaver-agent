from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

# ── Conversation state machine framework (US-024) ─────────────────────────────
#
# This bolt only ships the framework — no real dialogs. Later bolts (registration,
# /setkey key intake, rebook confirmation) define a `DialogDefinition` and start it
# from their own command handlers registered on the same `CommandRouter`.
#
# State is kept in memory only, scoped per chat. On a daemon restart the state is
# gone; a chat mid-dialog simply falls through to "no active dialog" (its next
# message is treated as an ordinary command/unknown input) — a safe reset, not a
# crash or a replayed step, matching the story's "or is safely reset with a
# notice" acceptance criterion. The notice is the caller's responsibility (e.g. a
# `/start` handler can mention that in-progress setups don't survive a restart).
#
# Extended in bolt 010 (US-025) for the `/register` dialog, which needs two
# things a single-answer-in-isolation step can't express:
#
#   - Cross-field validation (e.g. check-out must be after check-in): `validate`
#     now also receives the answers collected so far.
#   - A dynamic summary prompt on the final confirmation step: `prompt` may be
#     a callable of the answers-so-far instead of a fixed string.
#
# Both are purely additive — a plain string `prompt` and a single-argument
# `validate` still work for any dialog that doesn't need them (none did before
# this bolt).


class DialogAborted(Exception):
    """Raise from a step's `validate` to end the whole dialog immediately with
    `message` (e.g. a hard product-constraint rejection, or a "no" answer on a
    confirmation step) — distinct from an ordinary re-prompt-on-this-step
    validation failure.
    """

    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)


PromptSource = str | Callable[[dict[str, str]], str]
Validator = Callable[[str, dict[str, str]], str | None]


def _render_prompt(prompt: PromptSource, answers: dict[str, str]) -> str:
    return prompt(answers) if callable(prompt) else prompt


@dataclass(frozen=True)
class DialogStep:
    """One question in a multi-step dialog.

    `validate` returns `None` when `text` is acceptable (stored verbatim under
    `key`), or an error message to show the user before re-prompting the same
    step. It also receives the answers collected by earlier steps in this
    dialog, for cross-field checks. It may raise `DialogAborted` to end the
    dialog outright instead of re-prompting.

    `prompt` is either a fixed string or a callable of the answers collected
    so far (e.g. to render a final confirmation summary).
    """

    key: str
    prompt: PromptSource
    validate: Validator


@dataclass(frozen=True)
class DialogDefinition:
    name: str
    steps: tuple[DialogStep, ...]
    on_complete: Callable[[int, int, dict[str, str]], str]

    def __post_init__(self) -> None:
        if not self.steps:
            raise ValueError(f"DialogDefinition {self.name!r} must have at least one step")


@dataclass
class _ActiveDialog:
    definition: DialogDefinition
    step_index: int = 0
    answers: dict[str, str] = field(default_factory=dict)


class DialogManager:
    """Tracks at most one active dialog per chat."""

    def __init__(self) -> None:
        self._active: dict[int, _ActiveDialog] = {}

    def start(self, chat_id: int, definition: DialogDefinition) -> str:
        """Begin `definition` in `chat_id`, replacing any dialog already active there.

        Returns the first step's prompt.
        """
        self._active[chat_id] = _ActiveDialog(definition=definition)
        return _render_prompt(definition.steps[0].prompt, {})

    def has_active(self, chat_id: int) -> bool:
        return chat_id in self._active

    def active_dialog_name(self, chat_id: int) -> str | None:
        active = self._active.get(chat_id)
        return active.definition.name if active else None

    def cancel(self, chat_id: int) -> bool:
        """Abort the active dialog in `chat_id`, if any. Returns whether one existed."""
        return self._active.pop(chat_id, None) is not None

    def handle_message(self, chat_id: int, user_id: int, text: str) -> str:
        """Feed `text` to the current step of the active dialog in `chat_id`.

        Precondition: `has_active(chat_id)` is True. Returns the reply to send —
        either a re-prompt (invalid input), the next step's prompt, the
        dialog's completion message, or an abort message (`DialogAborted`).
        """
        active = self._active[chat_id]
        step = active.definition.steps[active.step_index]
        try:
            error = step.validate(text, active.answers)
        except DialogAborted as abort:
            del self._active[chat_id]
            return abort.message
        if error is not None:
            return f"{error}\n\n{_render_prompt(step.prompt, active.answers)}"

        active.answers[step.key] = text
        active.step_index += 1

        if active.step_index >= len(active.definition.steps):
            answers = active.answers
            del self._active[chat_id]
            return active.definition.on_complete(user_id, chat_id, answers)

        return _render_prompt(active.definition.steps[active.step_index].prompt, active.answers)
