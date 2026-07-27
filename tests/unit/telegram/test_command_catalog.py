from booksaver.infrastructure.telegram.command_catalog import COMMANDS, api_commands, help_text


def test_catalog_names_are_unique_and_telegram_safe() -> None:
    names = [command.name for command in COMMANDS]
    assert len(names) == len(set(names))
    assert all(name.replace("_", "").isalnum() and name == name.lower() for name in names)
    assert all(1 <= len(command.description) <= 256 for command in COMMANDS)


def test_owner_command_scope_adds_admin_only_to_owner() -> None:
    ordinary = {entry["command"] for entry in api_commands(include_owner_only=False)}
    owner = {entry["command"] for entry in api_commands(include_owner_only=True)}

    assert "admin" not in ordinary
    assert owner == ordinary | {"admin"}


def test_help_uses_same_catalog_and_can_hide_admin() -> None:
    ordinary_help = help_text(include_owner_only=False)
    owner_help = help_text(include_owner_only=True)

    for command in api_commands(include_owner_only=False):
        assert f"/{command['command']}" in ordinary_help
    assert "/admin" not in ordinary_help
    assert "/admin" in owner_help


def test_retired_booking_mutation_commands_are_absent() -> None:
    ordinary = {entry["command"] for entry in api_commands(include_owner_only=False)}
    help_output = help_text(include_owner_only=False)

    retired = {"register", "editbooking", "deletebooking", "rebook"}
    assert retired.isdisjoint(ordinary)
    assert all(f"/{command}" not in help_output for command in retired)
