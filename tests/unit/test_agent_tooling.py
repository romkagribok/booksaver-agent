import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_agent_adapters_use_installed_specsmd_paths() -> None:
    adapter_roots = (ROOT / ".agents", ROOT / ".claude", ROOT / ".cursor", ROOT / ".specsmd")
    text = "\n".join(
        path.read_text()
        for adapter_root in adapter_roots
        for path in adapter_root.rglob("*.md")
    )

    assert "src/flows/aidlc" not in text
    assert ".specsmd/skills/" not in text
    assert ".specsmd/agents/" not in text
    assert ".specsmd/aidlc/agents/" in text
    assert ".specsmd/aidlc/skills/" in text

    concrete_paths = {
        path for path in re.findall(r"`(\.specsmd/aidlc/[^`]+)`", text) if "{" not in path
    }
    assert concrete_paths
    assert all((ROOT / path).exists() for path in concrete_paths)
