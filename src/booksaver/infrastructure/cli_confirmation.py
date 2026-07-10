from __future__ import annotations

from booksaver.domain.rebook import ConfirmationAnswer, ConfirmationPrompt, RebookAction

_ACTION_LABELS = {
    RebookAction.CANCEL_EXISTING: "CANCEL your existing reservation",
    RebookAction.BOOK_NEW: "BOOK the new, cheaper offer",
}


class TerminalConfirmationGate:
    """ConfirmationGate adapter over stdin. Only an explicit 'yes'/'y' approves;
    anything else — including Ctrl-C/Ctrl-D — declines (fail-safe)."""

    @property
    def channel_name(self) -> str:
        return "terminal"

    def ask(self, prompt: ConfirmationPrompt) -> ConfirmationAnswer:
        print()
        print("=" * 60)
        print(f"CONFIRMATION REQUIRED: {_ACTION_LABELS[prompt.action]}")
        print("=" * 60)
        print(f"  You paid   : {prompt.old_price.amount} {prompt.old_price.currency}")
        print(f"  New price  : {prompt.new_price.amount} {prompt.new_price.currency}")
        print(f"  Refunds    : {prompt.refundability_summary}")
        print()
        print("Nothing happens unless you type exactly 'yes'.")
        try:
            raw = input("Proceed? [yes/no]: ")
        except (KeyboardInterrupt, EOFError):
            print("\nCancelled — treated as a decline.")
            raw = "no"
        return ConfirmationAnswer.from_input(raw)
