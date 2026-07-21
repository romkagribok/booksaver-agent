from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CommandDefinition:
    """One implemented Telegram command and its native-menu description."""

    name: str
    description: str
    owner_only: bool = False

    def as_api_dict(self) -> dict[str, str]:
        return {"command": self.name, "description": self.description}


COMMANDS = (
    CommandDefinition("start", "Welcome and show available commands"),
    CommandDefinition("help", "Show available commands"),
    CommandDefinition("status", "Show daemon and booking status"),
    CommandDefinition("connect", "Connect your Booking.com account"),
    CommandDefinition("register", "Add a refundable Booking.com hotel"),
    CommandDefinition("editbooking", "Edit one of your monitored bookings"),
    CommandDefinition("deletebooking", "Delete one of your monitored bookings"),
    CommandDefinition("bookings", "List monitored bookings"),
    CommandDefinition("savings", "List detected savings opportunities"),
    CommandDefinition("checks", "Choose a booking and view recent checks"),
    CommandDefinition("checknow", "Run a live price check now"),
    CommandDefinition("rebook", "Choose savings and start guided rebooking"),
    CommandDefinition("setkey", "Set a personal Anthropic API key"),
    CommandDefinition("deletekey", "Remove the personal Anthropic API key"),
    CommandDefinition("admin", "Manage users, invites, and access mode", owner_only=True),
    CommandDefinition("cancelflow", "Cancel the current dialog"),
)


def api_commands(*, include_owner_only: bool) -> list[dict[str, str]]:
    return [
        command.as_api_dict()
        for command in COMMANDS
        if include_owner_only or not command.owner_only
    ]


def help_text(*, include_owner_only: bool = True) -> str:
    lines = ["BookSaver commands:"]
    for command in COMMANDS:
        if command.owner_only and not include_owner_only:
            continue
        lines.append(f"/{command.name} - {command.description}")
    return "\n".join(lines)
