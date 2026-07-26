from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_image_contains_transient_remote_browser_dependencies() -> None:
    dockerfile = (ROOT / "Dockerfile").read_text()
    for package in ("novnc", "websockify", "x11vnc", "xvfb"):
        assert package in dockerfile
    for module in ("rfb.js", "keyboard.js", "keysym.js", "keysymdef.js"):
        assert f"test -f /usr/share/novnc/core/{module}" in dockerfile or (
            f"test -f /usr/share/novnc/core/input/{module}" in dockerfile
        )


def test_compose_publishes_only_caddy_for_opt_in_remote_auth_profile() -> None:
    compose = (ROOT / "docker-compose.yml").read_text()
    booksaver_block, caddy_block = compose.split("\n  caddy:", maxsplit=1)

    assert 'profiles: ["remote-auth"]' in caddy_block
    assert '"80:80"' in caddy_block
    assert '"443:443"' in caddy_block
    assert '"8080"' in booksaver_block
    assert '"6080"' in booksaver_block
    assert "    ports:" not in booksaver_block
    assert "shm_size: 1g" in booksaver_block
    assert "./config.toml:/data/config.toml:ro" in booksaver_block


def test_caddy_routes_websocket_without_access_log_configuration() -> None:
    caddyfile = (ROOT / "Caddyfile").read_text()

    assert "{$BOOKSAVER_AUTH_DOMAIN}" in caddyfile
    assert "reverse_proxy booksaver:6080" in caddyfile
    assert "reverse_proxy booksaver:8080" in caddyfile
    assert "log {" not in caddyfile
