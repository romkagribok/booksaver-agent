from __future__ import annotations

from booksaver.infrastructure.telegram.dialogs import DialogDefinition, DialogManager, DialogStep


def _no_validation(_: str) -> str | None:
    return None


def _digits_only(text: str) -> str | None:
    return None if text.isdigit() else "Please send a number."


def _two_step_dialog(completions: list[tuple[int, int, dict[str, str]]]) -> DialogDefinition:
    def _on_complete(user_id: int, chat_id: int, answers: dict[str, str]) -> str:
        completions.append((user_id, chat_id, dict(answers)))
        return f"Done: {answers}"

    return DialogDefinition(
        name="two-step",
        steps=(
            DialogStep(key="name", prompt="What is your name?", validate=_no_validation),
            DialogStep(key="age", prompt="What is your age?", validate=_digits_only),
        ),
        on_complete=_on_complete,
    )


def test_start_returns_first_prompt_and_marks_active() -> None:
    manager = DialogManager()
    prompt = manager.start(1, _two_step_dialog([]))
    assert prompt == "What is your name?"
    assert manager.has_active(1) is True


def test_has_active_false_for_untouched_chat() -> None:
    manager = DialogManager()
    assert manager.has_active(999) is False


def test_valid_answer_advances_to_next_prompt() -> None:
    manager = DialogManager()
    manager.start(1, _two_step_dialog([]))
    reply = manager.handle_message(1, user_id=42, text="Alice")
    assert reply == "What is your age?"
    assert manager.has_active(1) is True


def test_invalid_answer_reprompts_with_expected_format() -> None:
    manager = DialogManager()
    manager.start(1, _two_step_dialog([]))
    manager.handle_message(1, user_id=42, text="Alice")
    reply = manager.handle_message(1, user_id=42, text="not-a-number")
    assert "Please send a number." in reply
    assert "What is your age?" in reply
    assert manager.has_active(1) is True  # still on the same step


def test_completing_all_steps_calls_on_complete_and_clears_active_dialog() -> None:
    completions: list[tuple[int, int, dict[str, str]]] = []
    manager = DialogManager()
    manager.start(1, _two_step_dialog(completions))
    manager.handle_message(1, user_id=42, text="Alice")
    reply = manager.handle_message(1, user_id=42, text="30")

    assert "Done:" in reply
    assert completions == [(42, 1, {"name": "Alice", "age": "30"})]
    assert manager.has_active(1) is False


def test_cancel_removes_active_dialog_and_reports_whether_one_existed() -> None:
    manager = DialogManager()
    manager.start(1, _two_step_dialog([]))

    assert manager.cancel(1) is True
    assert manager.has_active(1) is False
    assert manager.cancel(1) is False  # nothing left to cancel


def test_cancel_from_any_step_works() -> None:
    manager = DialogManager()
    manager.start(1, _two_step_dialog([]))
    manager.handle_message(1, user_id=42, text="Alice")  # now on step 2

    assert manager.cancel(1) is True
    assert manager.has_active(1) is False


def test_dialogs_are_independent_per_chat() -> None:
    manager = DialogManager()
    manager.start(1, _two_step_dialog([]))
    manager.start(2, _two_step_dialog([]))

    manager.handle_message(1, user_id=42, text="Alice")

    assert manager.active_dialog_name(1) == "two-step"
    assert manager.active_dialog_name(2) == "two-step"
    # chat 2 is still on step 1 — sending a numeric-looking "name" is accepted as-is
    reply = manager.handle_message(2, user_id=43, text="Bob")
    assert reply == "What is your age?"


def test_starting_a_new_dialog_replaces_an_active_one() -> None:
    manager = DialogManager()
    manager.start(1, _two_step_dialog([]))
    manager.handle_message(1, user_id=42, text="Alice")  # now on step 2 of dialog A

    prompt = manager.start(1, _two_step_dialog([]))  # restart from scratch
    assert prompt == "What is your name?"


def test_empty_steps_dialog_definition_rejected() -> None:
    import pytest

    with pytest.raises(ValueError, match="at least one step"):
        DialogDefinition(name="empty", steps=(), on_complete=lambda u, c, a: "done")
