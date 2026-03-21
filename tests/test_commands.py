import shutil
from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from nanobot.agent.tools.shell import ExecTool
from nanobot.cli.commands import app
from nanobot.config.schema import Config
from nanobot.providers.litellm_provider import LiteLLMProvider
from nanobot.providers.openai_codex_provider import _strip_model_prefix
from nanobot.providers.registry import find_by_model

runner = CliRunner()


@pytest.fixture
def mock_paths():
    """Mock config/workspace paths for test isolation."""
    with patch("nanobot.config.loader.get_config_path") as mock_cp, \
         patch("nanobot.config.loader.save_config") as mock_sc, \
         patch("nanobot.config.loader.load_config") as mock_lc, \
         patch("nanobot.utils.helpers.get_workspace_path") as mock_ws:

        base_dir = Path("./test_onboard_data")
        if base_dir.exists():
            shutil.rmtree(base_dir)
        base_dir.mkdir()

        config_file = base_dir / "config.json"
        workspace_dir = base_dir / "workspace"

        mock_cp.return_value = config_file
        mock_ws.return_value = workspace_dir
        mock_sc.side_effect = lambda config: config_file.write_text(config.model_dump_json(by_alias=True))
        mock_lc.side_effect = lambda config_path=None: (
            Config.model_validate_json(config_file.read_text())
            if config_file.exists()
            else Config()
        )

        yield config_file, workspace_dir

        if base_dir.exists():
            shutil.rmtree(base_dir)


def test_onboard_fresh_install(mock_paths):
    """No existing config — should create a minimal runnable setup."""
    config_file, workspace_dir = mock_paths

    result = runner.invoke(
        app,
        ["onboard"],
        input="http://gw.example/v1\nsecret-key\ngpt-4.1-mini\n",
    )

    assert result.exit_code == 0
    assert "Created config" in result.stdout
    assert "Created workspace" in result.stdout
    assert "HCIGuard Doctor" in result.stdout
    assert "nanobot doctor" in result.stdout
    assert config_file.exists()
    assert (workspace_dir / "AGENTS.md").exists()
    assert (workspace_dir / "memory" / "MEMORY.md").exists()


def test_onboard_mentions_crs(mock_paths):
    config_file, _workspace_dir = mock_paths

    result = runner.invoke(
        app,
        ["onboard"],
        input="http://gw.example/v1\nsecret-key\ngpt-4.1-mini\n",
    )

    assert result.exit_code == 0
    assert "OpenAI-compatible gateway" in result.stdout
    assert "CRS" in result.stdout
    assert config_file.exists()


def test_onboard_existing_config_refresh(mock_paths):
    """Existing config should be updated in place through the wizard."""
    config_file, workspace_dir = mock_paths
    config_file.write_text(Config().model_dump_json(by_alias=True))

    result = runner.invoke(
        app,
        ["onboard"],
        input="http://gw.example/v1\nsecret-key\ngpt-4.1-mini\n",
    )

    assert result.exit_code == 0
    assert "Config already exists" not in result.stdout
    assert workspace_dir.exists()
    assert (workspace_dir / "AGENTS.md").exists()


def test_onboard_existing_config_overwrite(mock_paths):
    """Existing config should be overwritten with the new minimal values."""
    config_file, workspace_dir = mock_paths
    config = Config()
    config.agents.defaults.provider = "custom"
    config.providers.custom.api_key = "old-key"
    config.providers.custom.api_base = "http://old.example/v1"
    config_file.write_text(config.model_dump_json(by_alias=True))

    result = runner.invoke(
        app,
        ["onboard"],
        input="http://gw.example/v1\nsecret-key\ngpt-4.1-mini\n",
    )

    assert result.exit_code == 0
    data = Config.model_validate_json(config_file.read_text())
    assert data.providers.custom.api_key == "secret-key"
    assert workspace_dir.exists()


def test_onboard_existing_workspace_safe_create(mock_paths):
    """Existing workspace should be reused while missing templates are still added."""
    config_file, workspace_dir = mock_paths
    workspace_dir.mkdir(parents=True)
    config_file.write_text(Config().model_dump_json(by_alias=True))

    result = runner.invoke(
        app,
        ["onboard"],
        input="http://gw.example/v1\nsecret-key\ngpt-4.1-mini\n",
    )

    assert result.exit_code == 0
    assert "Created workspace" in result.stdout
    assert "Created AGENTS.md" in result.stdout
    assert (workspace_dir / "AGENTS.md").exists()


def test_root_command_runs_onboarding_when_minimal_config_missing(mock_paths):
    config_file, workspace_dir = mock_paths

    result = runner.invoke(
        app,
        [],
        input="http://gw.example/v1\nsecret-key\ngpt-4.1-mini\n",
    )

    assert result.exit_code == 0
    assert "First-time setup" in result.stdout
    assert "Created workspace" in result.stdout
    assert "doctor" in result.stdout
    assert config_file.exists()
    assert workspace_dir.exists()


def test_root_command_shows_help_when_minimal_config_exists(mock_paths):
    config_file, _workspace_dir = mock_paths
    config_file.write_text(
        """
{
  "agents": {
    "defaults": {
      "provider": "custom",
      "model": "gpt-4.1-mini"
    }
  },
  "providers": {
    "custom": {
      "apiKey": "secret-key",
      "apiBase": "http://gw.example/v1"
    }
  }
}
""".strip()
    )

    result = runner.invoke(app, [])

    assert result.exit_code == 0
    assert "Commands" in result.stdout
    assert "First-time setup" not in result.stdout


def test_onboard_writes_minimal_openai_compatible_config(mock_paths):
    config_file, workspace_dir = mock_paths

    result = runner.invoke(
        app,
        ["onboard"],
        input="http://gw.example/v1\nsecret-key\ngpt-4.1-mini\n",
    )

    assert result.exit_code == 0
    data = Config.model_validate_json(config_file.read_text())
    assert data.agents.defaults.provider == "custom"
    assert data.agents.defaults.model == "gpt-4.1-mini"
    assert data.providers.custom.api_base == "http://gw.example/v1"
    assert data.providers.custom.api_key == "secret-key"
    assert workspace_dir.exists()


def test_onboard_cancel_does_not_write_partial_config(mock_paths):
    config_file, _workspace_dir = mock_paths

    with patch("typer.prompt", side_effect=KeyboardInterrupt):
        result = runner.invoke(app, ["onboard"])

    assert result.exit_code == 1
    assert "cancelled" in result.stdout.lower()
    assert not config_file.exists()


def test_onboard_existing_config_refreshes_without_overwrite_prompt_for_minimal_flow(mock_paths):
    config_file, _workspace_dir = mock_paths
    config_file.write_text("{}")

    with patch("typer.prompt", side_effect=["http://gw.example/v1", "secret-key", "gpt-4.1-mini"]):
        result = runner.invoke(app, ["onboard"])

    assert result.exit_code == 0
    assert "Config already exists" not in result.stdout
    data = Config.model_validate_json(config_file.read_text())
    assert data.providers.custom.api_key == "secret-key"


def test_quickstart_prints_shortest_path() -> None:
    result = runner.invoke(app, ["quickstart"])

    assert result.exit_code == 0
    assert "uv tool install nanobot-ai" in result.stdout
    assert "nanobot" in result.stdout
    assert "nanobot doctor" in result.stdout
    assert "nanobot agent" in result.stdout


def test_doctor_reports_blocked_when_provider_config_missing(mock_paths):
    _config_file, _workspace_dir = mock_paths

    result = runner.invoke(app, ["doctor"])

    assert result.exit_code == 0
    assert "配置" in result.stdout
    assert "模型连通性" in result.stdout
    assert "blocked" in result.stdout


def test_doctor_reports_ok_when_minimal_custom_provider_is_ready(mock_paths):
    config_file, workspace_dir = mock_paths
    config = Config()
    config.agents.defaults.provider = "custom"
    config.agents.defaults.model = "gpt-4.1-mini"
    config.providers.custom.api_base = "http://gw.example/v1"
    config.providers.custom.api_key = "secret-key"
    config_file.write_text(config.model_dump_json(by_alias=True))
    workspace_dir.mkdir(parents=True, exist_ok=True)

    with patch("nanobot.cli.doctor.probe_model_connectivity", return_value=("ok", "connected")):
        result = runner.invoke(app, ["doctor"])

    assert result.exit_code == 0
    assert "ok" in result.stdout
    assert "connected" in result.stdout


def test_config_matches_github_copilot_codex_with_hyphen_prefix():
    config = Config()
    config.agents.defaults.model = "github-copilot/gpt-5.3-codex"

    assert config.get_provider_name() == "github_copilot"


def test_config_matches_openai_codex_with_hyphen_prefix():
    config = Config()
    config.agents.defaults.model = "openai-codex/gpt-5.1-codex"

    assert config.get_provider_name() == "openai_codex"


def test_find_by_model_prefers_explicit_prefix_over_generic_codex_keyword():
    spec = find_by_model("github-copilot/gpt-5.3-codex")

    assert spec is not None
    assert spec.name == "github_copilot"


def test_litellm_provider_canonicalizes_github_copilot_hyphen_prefix():
    provider = LiteLLMProvider(default_model="github-copilot/gpt-5.3-codex")

    resolved = provider._resolve_model("github-copilot/gpt-5.3-codex")

    assert resolved == "github_copilot/gpt-5.3-codex"


def test_openai_codex_strip_prefix_supports_hyphen_and_underscore():
    assert _strip_model_prefix("openai-codex/gpt-5.1-codex") == "gpt-5.1-codex"
    assert _strip_model_prefix("openai_codex/gpt-5.1-codex") == "gpt-5.1-codex"


def test_exec_config_round_trip_preserves_target_aware_settings():
    config = Config.model_validate({
        "tools": {
            "exec": {
                "defaultTarget": "root@example-host:2222",
                "maxInvestigationRounds": 12,
                "ssh": {
                    "enabled": False,
                    "port": 2200,
                },
            }
        }
    })

    dumped = config.model_dump(by_alias=True)

    assert dumped["tools"]["exec"]["defaultTarget"] == "root@example-host:2222"
    assert dumped["tools"]["exec"]["maxInvestigationRounds"] == 12
    assert dumped["tools"]["exec"]["ssh"]["enabled"] is False
    assert dumped["tools"]["exec"]["ssh"]["port"] == 2200


def test_exec_tool_schema_accepts_target_and_ssh_password():
    tool = ExecTool()

    errors = tool.validate_params({
        "command": "uptime",
        "target": "root@example-host",
        "ssh_password": "secret-123",
    })

    assert errors == []
