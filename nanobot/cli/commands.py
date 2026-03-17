"""CLI commands for nanobot."""

import asyncio
import json
import os
import select
import signal
import sys
from pathlib import Path

import typer
from prompt_toolkit import PromptSession
from prompt_toolkit.formatted_text import HTML
from prompt_toolkit.history import FileHistory
from prompt_toolkit.patch_stdout import patch_stdout
from rich.console import Console
from rich.markdown import Markdown
from rich.table import Table
from rich.text import Text

from nanobot import __logo__, __version__
from nanobot.config.schema import Config
from nanobot.utils.helpers import sync_workspace_templates

app = typer.Typer(
    name="nanobot",
    help=f"{__logo__} HCIGuard - HCI Troubleshooting Assistant",
    no_args_is_help=True,
)

console = Console()
EXIT_COMMANDS = {"exit", "quit", "/exit", "/quit", ":q"}

# ---------------------------------------------------------------------------
# CLI input: prompt_toolkit for editing, paste, history, and display
# ---------------------------------------------------------------------------

_PROMPT_SESSION: PromptSession | None = None
_SAVED_TERM_ATTRS = None  # original termios settings, restored on exit


def _flush_pending_tty_input() -> None:
    """Drop unread keypresses typed while the model was generating output."""
    try:
        fd = sys.stdin.fileno()
        if not os.isatty(fd):
            return
    except Exception:
        return

    try:
        import termios
        termios.tcflush(fd, termios.TCIFLUSH)
        return
    except Exception:
        pass

    try:
        while True:
            ready, _, _ = select.select([fd], [], [], 0)
            if not ready:
                break
            if not os.read(fd, 4096):
                break
    except Exception:
        return


def _restore_terminal() -> None:
    """Restore terminal to its original state (echo, line buffering, etc.)."""
    if _SAVED_TERM_ATTRS is None:
        return
    try:
        import termios
        termios.tcsetattr(sys.stdin.fileno(), termios.TCSADRAIN, _SAVED_TERM_ATTRS)
    except Exception:
        pass


def _init_prompt_session() -> None:
    """Create the prompt_toolkit session with persistent file history."""
    global _PROMPT_SESSION, _SAVED_TERM_ATTRS

    # Save terminal state so we can restore it on exit
    try:
        import termios
        _SAVED_TERM_ATTRS = termios.tcgetattr(sys.stdin.fileno())
    except Exception:
        pass

    history_file = Path.home() / ".nanobot" / "history" / "cli_history"
    history_file.parent.mkdir(parents=True, exist_ok=True)

    _PROMPT_SESSION = PromptSession(
        history=FileHistory(str(history_file)),
        enable_open_in_editor=False,
        multiline=False,   # Enter submits (single line mode)
    )


def _print_agent_response(response: str, render_markdown: bool) -> None:
    """Render assistant response with consistent terminal styling."""
    content = response or ""
    body = Markdown(content) if render_markdown else Text(content)
    console.print()
    console.print(f"[cyan]{__logo__} HCIGuard[/cyan]")
    console.print(body)
    console.print()


def _is_exit_command(command: str) -> bool:
    """Return True when input should end interactive chat."""
    return command.lower() in EXIT_COMMANDS


async def _read_interactive_input_async() -> str:
    """Read user input using prompt_toolkit (handles paste, history, display).

    prompt_toolkit natively handles:
    - Multiline paste (bracketed paste mode)
    - History navigation (up/down arrows)
    - Clean display (no ghost characters or artifacts)
    """
    if _PROMPT_SESSION is None:
        raise RuntimeError("Call _init_prompt_session() first")
    try:
        with patch_stdout():
            return await _PROMPT_SESSION.prompt_async(
                HTML("<b fg='ansiblue'>You:</b> "),
            )
    except EOFError as exc:
        raise KeyboardInterrupt from exc


async def _read_secret_input_async(target_label: str) -> str:
    """Read a secret value from CLI without echo, used for SSH passwords."""
    if _PROMPT_SESSION is None:
        raise RuntimeError("Call _init_prompt_session() first")
    try:
        with patch_stdout():
            return await _PROMPT_SESSION.prompt_async(
                HTML(f"<b fg='ansiyellow'>SSH password for {target_label}:</b> "),
                is_password=True,
            )
    except EOFError as exc:
        raise KeyboardInterrupt from exc



def version_callback(value: bool):
    if value:
        console.print(f"{__logo__} HCIGuard v{__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: bool = typer.Option(
        None, "--version", "-v", callback=version_callback, is_eager=True
    ),
):
    """HCIGuard - HCI Troubleshooting Assistant."""
    pass


# ============================================================================
# Onboard / Setup
# ============================================================================


@app.command()
def onboard():
    """Initialize nanobot configuration and workspace."""
    from nanobot.config.loader import get_config_path, load_config, save_config
    from nanobot.config.schema import Config
    from nanobot.utils.helpers import get_workspace_path

    config_path = get_config_path()

    if config_path.exists():
        console.print(f"[yellow]Config already exists at {config_path}[/yellow]")
        console.print("  [bold]y[/bold] = overwrite with defaults (existing values will be lost)")
        console.print("  [bold]N[/bold] = refresh config, keeping existing values and adding new fields")
        if typer.confirm("Overwrite?"):
            config = Config()
            save_config(config)
            console.print(f"[green]✓[/green] Config reset to defaults at {config_path}")
        else:
            config = load_config()
            save_config(config)
            console.print(f"[green]✓[/green] Config refreshed at {config_path} (existing values preserved)")
    else:
        save_config(Config())
        console.print(f"[green]✓[/green] Created config at {config_path}")

    # Create workspace
    workspace = get_workspace_path()

    if not workspace.exists():
        workspace.mkdir(parents=True, exist_ok=True)
        console.print(f"[green]✓[/green] Created workspace at {workspace}")

    sync_workspace_templates(workspace)

    console.print(f"\n{__logo__} HCIGuard is ready!")
    console.print("\nNext steps:")
    console.print("  1. Add your API key to [cyan]~/.nanobot/config.json[/cyan]")
    console.print("     Get one at: https://openrouter.ai/keys")
    console.print("  2. Chat: [cyan]nanobot agent -m \"Hello!\"[/cyan]")
    console.print("\n[dim]Want Telegram/Mattermost? See: https://github.com/HKUDS/nanobot#-chat-apps[/dim]")





def _make_provider(config: Config):
    """Create the appropriate LLM provider from config."""
    from nanobot.providers.custom_provider import CustomProvider
    from nanobot.providers.litellm_provider import LiteLLMProvider
    from nanobot.providers.openai_codex_provider import OpenAICodexProvider

    model = config.agents.defaults.model
    provider_name = config.get_provider_name(model)
    p = config.get_provider(model)

    # OpenAI Codex (OAuth)
    if provider_name == "openai_codex" or model.startswith("openai-codex/"):
        return OpenAICodexProvider(default_model=model)

    # Custom: direct OpenAI-compatible endpoint, bypasses LiteLLM
    if provider_name == "custom":
        return CustomProvider(
            api_key=p.api_key if p else "no-key",
            api_base=config.get_api_base(model) or "http://localhost:8000/v1",
            default_model=model,
        )

    from nanobot.providers.registry import find_by_name
    spec = find_by_name(provider_name)
    if not model.startswith("bedrock/") and not (p and p.api_key) and not (spec and spec.is_oauth):
        console.print("[red]Error: No API key configured.[/red]")
        console.print("Set one in ~/.nanobot/config.json under providers section")
        raise typer.Exit(1)

    return LiteLLMProvider(
        api_key=p.api_key if p else None,
        api_base=config.get_api_base(model),
        default_model=model,
        extra_headers=p.extra_headers if p else None,
        provider_name=provider_name,
    )


# ============================================================================
# Gateway / Server
# ============================================================================


@app.command()
def gateway(
    port: int = typer.Option(18790, "--port", "-p", help="Gateway port"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Verbose output"),
):
    """Start the nanobot gateway."""
    from nanobot.agent.loop import AgentLoop
    from nanobot.bus.queue import MessageBus
    from nanobot.channels.manager import ChannelManager
    from nanobot.config.loader import get_data_dir, load_config
    from nanobot.cron.service import CronService
    from nanobot.cron.types import CronJob
    from nanobot.heartbeat.service import HeartbeatService
    from nanobot.session.manager import SessionManager

    if verbose:
        import logging
        logging.basicConfig(level=logging.DEBUG)

    console.print(f"{__logo__} Starting HCIGuard gateway on port {port}...")

    config = load_config()
    sync_workspace_templates(config.workspace_path)
    bus = MessageBus()
    provider = _make_provider(config)
    session_manager = SessionManager(config.workspace_path)

    # Create cron service first (callback set after agent creation)
    cron_store_path = get_data_dir() / "cron" / "jobs.json"
    cron = CronService(cron_store_path)

    # Create agent with cron service
    agent = AgentLoop(
        bus=bus,
        provider=provider,
        workspace=config.workspace_path,
        model=config.agents.defaults.model,
        temperature=config.agents.defaults.temperature,
        max_tokens=config.agents.defaults.max_tokens,
        max_iterations=config.agents.defaults.max_tool_iterations,
        memory_window=config.agents.defaults.memory_window,
        reasoning_effort=config.agents.defaults.reasoning_effort,
        brave_api_key=config.tools.web.search.api_key or None,
        web_proxy=config.tools.web.proxy or None,
        exec_config=config.tools.exec,
        diagnostics_config=config.tools.diagnostics,
        troubleshooting_config=config.tools.troubleshooting,
        cases_config=config.cases,
        targeting=config.targeting,
        cron_service=cron,
        restrict_to_workspace=config.tools.restrict_to_workspace,
        session_manager=session_manager,
        mcp_servers=config.tools.mcp_servers,
        channels_config=config.channels,
    )

    # Set cron callback (needs agent)
    async def on_cron_job(job: CronJob) -> str | None:
        """Execute a cron job through the agent."""
        from nanobot.agent.tools.cron import CronTool
        from nanobot.agent.tools.message import MessageTool
        from nanobot.inspection.service import InspectionService

        if job.payload.kind == "system_event":
            if job.payload.message.startswith("inspection:run"):
                service = InspectionService(
                    workspace=config.workspace_path,
                    inspection=config.inspection,
                    provider=provider,
                    model=config.agents.defaults.model,
                    cases=config.cases,
                    exec_config=config.tools.exec,
                    targeting=config.targeting,
                )
                result = await service.run(trigger="cron")
                if result.get("status") == "disabled":
                    return "Inspection is disabled in config."
                target_status = result.get("target_status") or {}
                status_text = (
                    f"ok={target_status.get('ok', 0)} "
                    f"failed={target_status.get('failed', 0)} "
                    f"skipped={target_status.get('skipped', 0)}"
                )
                text = (
                    f"Inspection done: targets={result.get('targets', 0)} "
                    f"findings={result.get('findings', 0)} "
                    f"errors={result.get('target_errors', 0)} "
                    f"status=({status_text})\n"
                    f"Report: {result.get('report_path', '')}"
                )
                if result.get("case_id"):
                    text += f"\nCase: {result['case_id']}"
                return text
            return f"Unsupported system event: {job.payload.message}"

        reminder_note = (
            "[Scheduled Task] Timer finished.\n\n"
            f"Task '{job.name}' has been triggered.\n"
            f"Scheduled instruction: {job.payload.message}"
        )

        # Prevent the agent from scheduling new cron jobs during execution
        cron_tool = agent.tools.get("cron")
        cron_token = None
        if isinstance(cron_tool, CronTool):
            cron_token = cron_tool.set_cron_context(True)
        try:
            response = await agent.process_direct(
                reminder_note,
                session_key=f"cron:{job.id}",
                channel=job.payload.channel or "cli",
                chat_id=job.payload.to or "direct",
            )
        finally:
            if isinstance(cron_tool, CronTool) and cron_token is not None:
                cron_tool.reset_cron_context(cron_token)

        message_tool = agent.tools.get("message")
        if isinstance(message_tool, MessageTool) and message_tool._sent_in_turn:
            return response

        if job.payload.deliver and job.payload.to and response:
            from nanobot.bus.events import OutboundMessage
            await bus.publish_outbound(OutboundMessage(
                channel=job.payload.channel or "cli",
                chat_id=job.payload.to,
                content=response
            ))
        return response
    cron.on_job = on_cron_job

    # Create channel manager
    channels = ChannelManager(config, bus)

    def _pick_heartbeat_target() -> tuple[str, str]:
        """Pick a routable channel/chat target for heartbeat-triggered messages."""
        enabled = set(channels.enabled_channels)
        # Prefer the most recently updated non-internal session on an enabled channel.
        for item in session_manager.list_sessions():
            key = item.get("key") or ""
            if ":" not in key:
                continue
            channel, chat_id = key.split(":", 1)
            if channel in {"cli", "system"}:
                continue
            if channel in enabled and chat_id:
                return channel, chat_id
        # Fallback keeps prior behavior but remains explicit.
        return "cli", "direct"

    # Create heartbeat service
    async def on_heartbeat_execute(tasks: str) -> str:
        """Phase 2: execute heartbeat tasks through the full agent loop."""
        channel, chat_id = _pick_heartbeat_target()

        async def _silent(*_args, **_kwargs):
            pass

        return await agent.process_direct(
            tasks,
            session_key="heartbeat",
            channel=channel,
            chat_id=chat_id,
            on_progress=_silent,
        )

    async def on_heartbeat_notify(response: str) -> None:
        """Deliver a heartbeat response to the user's channel."""
        from nanobot.bus.events import OutboundMessage
        channel, chat_id = _pick_heartbeat_target()
        if channel == "cli":
            return  # No external channel available to deliver to
        await bus.publish_outbound(OutboundMessage(channel=channel, chat_id=chat_id, content=response))

    hb_cfg = config.gateway.heartbeat
    heartbeat = HeartbeatService(
        workspace=config.workspace_path,
        provider=provider,
        model=agent.model,
        on_execute=on_heartbeat_execute,
        on_notify=on_heartbeat_notify,
        interval_s=hb_cfg.interval_s,
        enabled=hb_cfg.enabled,
    )

    if channels.enabled_channels:
        console.print(f"[green]✓[/green] Channels enabled: {', '.join(channels.enabled_channels)}")
    else:
        console.print("[yellow]Warning: No channels enabled[/yellow]")

    cron_status = cron.status()
    if cron_status["jobs"] > 0:
        console.print(f"[green]✓[/green] Cron: {cron_status['jobs']} scheduled jobs")

    console.print(f"[green]✓[/green] Heartbeat: every {hb_cfg.interval_s}s")

    async def run():
        try:
            await cron.start()
            await heartbeat.start()
            await asyncio.gather(
                agent.run(),
                channels.start_all(),
            )
        except KeyboardInterrupt:
            console.print("\nShutting down...")
        finally:
            await agent.close_mcp()
            heartbeat.stop()
            cron.stop()
            agent.stop()
            await channels.stop_all()

    asyncio.run(run())




# ============================================================================
# Agent Commands
# ============================================================================


@app.command()
def agent(
    message: str = typer.Option(None, "--message", "-m", help="Message to send to the agent"),
    session_id: str = typer.Option("cli:direct", "--session", "-s", help="Session ID"),
    markdown: bool = typer.Option(True, "--markdown/--no-markdown", help="Render assistant output as Markdown"),
    logs: bool = typer.Option(False, "--logs/--no-logs", help="Show HCIGuard runtime logs during chat"),
):
    """Interact with the agent directly."""
    from loguru import logger

    from nanobot.agent.loop import AgentLoop
    from nanobot.bus.queue import MessageBus
    from nanobot.config.loader import get_data_dir, load_config
    from nanobot.cron.service import CronService

    config = load_config()
    sync_workspace_templates(config.workspace_path)

    bus = MessageBus()
    provider = _make_provider(config)

    # Create cron service for tool usage (no callback needed for CLI unless running)
    cron_store_path = get_data_dir() / "cron" / "jobs.json"
    cron = CronService(cron_store_path)

    if logs:
        logger.enable("nanobot")
    else:
        logger.disable("nanobot")

    agent_loop = AgentLoop(
        bus=bus,
        provider=provider,
        workspace=config.workspace_path,
        model=config.agents.defaults.model,
        temperature=config.agents.defaults.temperature,
        max_tokens=config.agents.defaults.max_tokens,
        max_iterations=config.agents.defaults.max_tool_iterations,
        memory_window=config.agents.defaults.memory_window,
        reasoning_effort=config.agents.defaults.reasoning_effort,
        brave_api_key=config.tools.web.search.api_key or None,
        web_proxy=config.tools.web.proxy or None,
        exec_config=config.tools.exec,
        diagnostics_config=config.tools.diagnostics,
        troubleshooting_config=config.tools.troubleshooting,
        cases_config=config.cases,
        targeting=config.targeting,
        cron_service=cron,
        restrict_to_workspace=config.tools.restrict_to_workspace,
        mcp_servers=config.tools.mcp_servers,
        channels_config=config.channels,
    )
    if exec_tool := agent_loop.tools.get("exec"):
        if hasattr(exec_tool, "set_secret_prompt_callback"):
            exec_tool.set_secret_prompt_callback(_read_secret_input_async)

    # Show spinner when logs are off (no output to miss); skip when logs are on
    def _thinking_ctx():
        if logs:
            from contextlib import nullcontext
            return nullcontext()
        # Animated spinner is safe to use with prompt_toolkit input handling
        return console.status("[dim]HCIGuard is thinking...[/dim]", spinner="dots")

    async def _cli_progress(content: str, *, tool_hint: bool = False) -> None:
        ch = agent_loop.channels_config
        if ch and tool_hint and not ch.send_tool_hints:
            return
        if ch and not tool_hint and not ch.send_progress:
            return
        console.print(f"  [dim]↳ {content}[/dim]")

    if message:
        # Single message mode — direct call, no bus needed
        async def run_once():
            with _thinking_ctx():
                response = await agent_loop.process_direct(message, session_id, on_progress=_cli_progress)
            _print_agent_response(response, render_markdown=markdown)
            await agent_loop.close_mcp()

        asyncio.run(run_once())
    else:
        # Interactive mode — route through bus like other channels
        from nanobot.bus.events import InboundMessage
        _init_prompt_session()
        console.print(f"{__logo__} Interactive mode (type [bold]exit[/bold] or [bold]Ctrl+C[/bold] to quit)\n")

        if ":" in session_id:
            cli_channel, cli_chat_id = session_id.split(":", 1)
        else:
            cli_channel, cli_chat_id = "cli", session_id

        def _exit_on_sigint(signum, frame):
            _restore_terminal()
            console.print("\nGoodbye!")
            os._exit(0)

        signal.signal(signal.SIGINT, _exit_on_sigint)

        async def run_interactive():
            bus_task = asyncio.create_task(agent_loop.run())
            turn_done = asyncio.Event()
            turn_done.set()
            turn_response: list[str] = []

            async def _consume_outbound():
                while True:
                    try:
                        msg = await asyncio.wait_for(bus.consume_outbound(), timeout=1.0)
                        if msg.metadata.get("_progress"):
                            is_tool_hint = msg.metadata.get("_tool_hint", False)
                            ch = agent_loop.channels_config
                            if ch and is_tool_hint and not ch.send_tool_hints:
                                pass
                            elif ch and not is_tool_hint and not ch.send_progress:
                                pass
                            else:
                                console.print(f"  [dim]↳ {msg.content}[/dim]")
                        elif not turn_done.is_set():
                            if msg.content:
                                turn_response.append(msg.content)
                            turn_done.set()
                        elif msg.content:
                            console.print()
                            _print_agent_response(msg.content, render_markdown=markdown)
                    except asyncio.TimeoutError:
                        continue
                    except asyncio.CancelledError:
                        break

            outbound_task = asyncio.create_task(_consume_outbound())

            try:
                while True:
                    try:
                        _flush_pending_tty_input()
                        user_input = await _read_interactive_input_async()
                        command = user_input.strip()
                        if not command:
                            continue

                        if _is_exit_command(command):
                            _restore_terminal()
                            console.print("\nGoodbye!")
                            break

                        turn_done.clear()
                        turn_response.clear()

                        await bus.publish_inbound(InboundMessage(
                            channel=cli_channel,
                            sender_id="user",
                            chat_id=cli_chat_id,
                            content=user_input,
                        ))

                        with _thinking_ctx():
                            await turn_done.wait()

                        if turn_response:
                            _print_agent_response(turn_response[0], render_markdown=markdown)
                    except KeyboardInterrupt:
                        _restore_terminal()
                        console.print("\nGoodbye!")
                        break
                    except EOFError:
                        _restore_terminal()
                        console.print("\nGoodbye!")
                        break
            finally:
                agent_loop.stop()
                outbound_task.cancel()
                await asyncio.gather(bus_task, outbound_task, return_exceptions=True)
                await agent_loop.close_mcp()

        asyncio.run(run_interactive())


# ============================================================================
# Channel Commands
# ============================================================================


channels_app = typer.Typer(help="Manage channels")
app.add_typer(channels_app, name="channels")


@channels_app.command("status")
def channels_status():
    """Show channel status."""
    from nanobot.config.loader import load_config

    config = load_config()

    table = Table(title="Channel Status")
    table.add_column("Channel", style="cyan")
    table.add_column("Enabled", style="green")
    table.add_column("Configuration", style="yellow")

    # Telegram
    tg = config.channels.telegram
    tg_config = f"token: {tg.token[:10]}..." if tg.token else "[dim]not configured[/dim]"
    table.add_row(
        "Telegram",
        "✓" if tg.enabled else "✗",
        tg_config
    )

    # Mattermost
    mm = config.channels.mattermost
    mm_config = mm.base_url if mm.base_url else "[dim]not configured[/dim]"
    table.add_row(
        "Mattermost",
        "✓" if mm.enabled else "✗",
        mm_config
    )

    console.print(table)

# ============================================================================
# Status Commands
# ============================================================================


@app.command()
def status():
    """Show nanobot status."""
    from nanobot.config.loader import get_config_path, load_config

    config_path = get_config_path()
    config = load_config()
    workspace = config.workspace_path

    console.print(f"{__logo__} HCIGuard Status\n")

    console.print(f"Config: {config_path} {'[green]✓[/green]' if config_path.exists() else '[red]✗[/red]'}")
    console.print(f"Workspace: {workspace} {'[green]✓[/green]' if workspace.exists() else '[red]✗[/red]'}")

    if config_path.exists():
        from nanobot.providers.registry import PROVIDERS

        console.print(f"Model: {config.agents.defaults.model}")

        # Check API keys from registry
        for spec in PROVIDERS:
            p = getattr(config.providers, spec.name, None)
            if p is None:
                continue
            if spec.is_oauth:
                console.print(f"{spec.label}: [green]✓ (OAuth)[/green]")
            elif spec.is_local:
                # Local deployments show api_base instead of api_key
                if p.api_base:
                    console.print(f"{spec.label}: [green]✓ {p.api_base}[/green]")
                else:
                    console.print(f"{spec.label}: [dim]not set[/dim]")
            else:
                has_key = bool(p.api_key)
                console.print(f"{spec.label}: {'[green]✓[/green]' if has_key else '[dim]not set[/dim]'}")


# ============================================================================
# Approval Commands
# ============================================================================


approvals_app = typer.Typer(help="Manage manual command approvals for exec tool")
app.add_typer(approvals_app, name="approvals")


def _approval_file_from_config() -> Path:
    from nanobot.config.loader import load_config

    cfg = load_config()
    return Path(cfg.tools.exec.approval_file).expanduser()


def _load_approvals(path: Path) -> list[str]:
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        commands = data.get("commands", [])
        if isinstance(commands, list):
            return [str(c) for c in commands if str(c).strip()]
    except Exception:
        return []
    return []


def _save_approvals(path: Path, commands: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"version": 1, "commands": commands}
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _split_markdown_frontmatter(content: str) -> tuple[dict[str, str | list[str]], str]:
    """Parse simple YAML-like frontmatter and return (metadata, markdown_body)."""
    text = content or ""
    if not text.startswith("---\n"):
        return {}, text
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}, text

    end_idx = -1
    for idx in range(1, len(lines)):
        if lines[idx].strip() == "---":
            end_idx = idx
            break
    if end_idx == -1:
        return {}, text

    metadata: dict[str, str | list[str]] = {}
    current_list_key: str | None = None
    for raw in lines[1:end_idx]:
        line = raw.rstrip()
        if line.startswith("  - "):
            if current_list_key is not None:
                existing = metadata.setdefault(current_list_key, [])
                if isinstance(existing, list):
                    existing.append(line[4:].strip())
            continue
        if ":" in line:
            key, value = line.split(":", 1)
            key = key.strip()
            value = value.strip()
            if not key:
                current_list_key = None
                continue
            if value == "":
                metadata[key] = []
                current_list_key = key
            else:
                metadata[key] = value
                current_list_key = None
        else:
            current_list_key = None

    body = "\n".join(lines[end_idx + 1 :]).lstrip("\n")
    return metadata, body


def _parse_case_sections(body: str) -> list[tuple[str, str]]:
    """Parse '# Section' style markdown into (section, content) pairs."""
    lines = (body or "").splitlines()
    sections: list[tuple[str, str]] = []
    current_title = ""
    current_lines: list[str] = []

    def _flush() -> None:
        nonlocal current_title, current_lines
        if current_title:
            sections.append((current_title, "\n".join(current_lines).strip() or "(empty)"))
        current_title = ""
        current_lines = []

    for line in lines:
        if line.startswith("# "):
            _flush()
            current_title = line[2:].strip()
            continue
        if current_title:
            current_lines.append(line)

    _flush()
    return sections


def _format_case_created(value: str) -> str:
    s = (value or "").strip()
    if len(s) >= 16 and "T" in s:
        return s.replace("T", " ")[:16]
    return s[:16]


def _shorten_path_for_display(path_str: str) -> str:
    p = Path(path_str).expanduser()
    try:
        home = Path.home().resolve()
        resolved = p.resolve()
        return "~/" + str(resolved.relative_to(home))
    except Exception:
        return path_str


@approvals_app.command("list")
def approvals_list():
    """List approved commands."""
    path = _approval_file_from_config()
    commands = _load_approvals(path)
    if not commands:
        console.print("[yellow]No approved commands.[/yellow]")
        return
    console.print(f"[cyan]Approval file:[/cyan] {path}")
    for c in commands:
        console.print(f"- {c}")


@approvals_app.command("grant")
def approvals_grant(command: str = typer.Option(..., "--command", "-c", help="Exact command string to approve")):
    """Grant manual approval for one exact command."""
    path = _approval_file_from_config()
    commands = _load_approvals(path)
    if command not in commands:
        commands.append(command)
        _save_approvals(path, commands)
    console.print(f"[green]Approved:[/green] {command}")
    console.print(f"[dim]{path}[/dim]")


@approvals_app.command("revoke")
def approvals_revoke(command: str = typer.Option(..., "--command", "-c", help="Exact command string to revoke")):
    """Revoke manual approval for one exact command."""
    path = _approval_file_from_config()
    commands = _load_approvals(path)
    kept = [c for c in commands if c != command]
    _save_approvals(path, kept)
    console.print(f"[green]Revoked:[/green] {command}")
    console.print(f"[dim]{path}[/dim]")


# ============================================================================
# Case Commands
# ============================================================================


cases_app = typer.Typer(help="Manage troubleshooting cases")
app.add_typer(cases_app, name="cases")


@cases_app.command("list")
def cases_list(
    limit: int = typer.Option(20, "--limit", "-n", help="Max rows to show"),
    keyword: str = typer.Option("", "--keyword", "-k", help="Filter by keyword in title/summary"),
    tag: str = typer.Option("", "--tag", help="Filter by tag"),
    host: str = typer.Option("", "--host", help="Filter by host"),
    service: str = typer.Option("", "--service", help="Filter by service"),
):
    """List stored troubleshooting cases."""
    from nanobot.cases.store import CaseStore
    from nanobot.config.loader import load_config

    config = load_config()
    store = CaseStore(config.workspace_path, config.cases.path)
    if any((keyword, tag, host, service)):
        rows = store.search_cases(
            keyword=keyword,
            tag=tag,
            host=host,
            service=service,
            limit=limit,
        )
    else:
        rows = store.list_cases(limit=limit)

    if not rows:
        console.print("[yellow]No cases found.[/yellow]")
        raise typer.Exit(0)

    table = Table(title="Cases")
    table.add_column("ID", style="cyan")
    table.add_column("Title")
    table.add_column("Severity", style="red")
    table.add_column("Status", style="green")
    table.add_column("Created", style="yellow", no_wrap=True)
    table.add_column("Tags")
    for row in rows:
        table.add_row(
            str(row.get("id", "")),
            str(row.get("title", "")),
            str(row.get("severity", "")),
            str(row.get("status", "")),
            _format_case_created(str(row.get("created_at", ""))),
            ",".join([str(t) for t in row.get("tags", [])]),
        )
    console.print(table)


@cases_app.command("show")
def cases_show(case_id: str = typer.Argument(..., help="Case ID, e.g. INC-20260307-001")):
    """Show a case record by ID."""
    from nanobot.cases.store import CaseStore
    from nanobot.config.loader import load_config

    config = load_config()
    store = CaseStore(config.workspace_path, config.cases.path)
    item, content = store.get_case(case_id)
    if not item:
        console.print(f"[red]Case not found:[/red] {case_id}")
        raise typer.Exit(1)

    console.print(f"[cyan]{item.get('id', '')}[/cyan] {item.get('title', '')}")
    if content:
        metadata, body = _split_markdown_frontmatter(content)
        if metadata:
            table = Table(title="Metadata")
            table.add_column("Field", style="cyan", no_wrap=True)
            table.add_column("Value")
            ordered = [
                "id",
                "title",
                "source",
                "created_at",
                "trigger",
                "host",
                "service",
                "severity",
                "status",
                "root_cause",
                "tags",
                "import_source",
            ]
            seen: set[str] = set()
            for key in ordered:
                if key not in metadata:
                    continue
                val = metadata[key]
                shown = ", ".join(val) if isinstance(val, list) else str(val)
                table.add_row(key, shown)
                seen.add(key)
            for key, val in metadata.items():
                if key in seen:
                    continue
                shown = ", ".join(val) if isinstance(val, list) else str(val)
                table.add_row(key, shown)
            console.print(table)
        if body.strip():
            sections = _parse_case_sections(body)
            if sections:
                for idx, (title, text) in enumerate(sections):
                    if idx > 0:
                        console.print()
                    console.print(f"[bold cyan]{title}[/bold cyan]")
                    console.print(text)
            else:
                console.print(body)
    else:
        console.print("[yellow]Case file missing on disk, but index entry exists.[/yellow]")


@cases_app.command("import")
def cases_import(
    path: str = typer.Argument(..., help="File or folder path to import (.md/.txt/.json)"),
):
    """Import existing troubleshooting records."""
    from nanobot.cases.importer import CaseImporter
    from nanobot.cases.store import CaseStore
    from nanobot.config.loader import load_config

    config = load_config()
    store = CaseStore(config.workspace_path, config.cases.path)
    importer = CaseImporter(store)

    try:
        imported = importer.import_path(path)
    except FileNotFoundError as e:
        console.print(f"[red]{e}[/red]")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]Import failed:[/red] {e}")
        raise typer.Exit(1)

    if not imported:
        console.print("[yellow]No supported files found to import.[/yellow]")
        raise typer.Exit(0)

    console.print(f"[green]Imported {len(imported)} case(s).[/green]")
    for item in imported[:10]:
        console.print(f"  - {item.get('id', '')} {item.get('title', '')}")
    if len(imported) > 10:
        console.print(f"  ... and {len(imported) - 10} more")


# ============================================================================
# Inspection Commands
# ============================================================================


inspection_app = typer.Typer(help="Run inspection scans and generate reports")
app.add_typer(inspection_app, name="inspection")


@inspection_app.command("run")
def inspection_run(
    trigger: str = typer.Option("manual", "--trigger", help="Trigger source label"),
    use_llm: bool = typer.Option(True, "--llm/--no-llm", help="Use model analysis"),
):
    """Run one inspection and print result summary."""
    from nanobot.config.loader import load_config
    from nanobot.inspection.service import InspectionService

    config = load_config()
    provider = None
    if use_llm:
        try:
            provider = _make_provider(config)
        except Exception:
            provider = None
            console.print("[yellow]Provider not available, continue without model analysis.[/yellow]")

    service = InspectionService(
        workspace=config.workspace_path,
        inspection=config.inspection,
        provider=provider,
        model=config.agents.defaults.model if provider else None,
        cases=config.cases,
        exec_config=config.tools.exec,
        targeting=config.targeting,
    )

    async def _run():
        return await service.run(trigger=trigger)

    result = asyncio.run(_run())
    if result.get("status") == "disabled":
        console.print("[yellow]Inspection is disabled in config.[/yellow]")
        raise typer.Exit(0)

    target_status = result.get("target_status") or {}
    status_text = (
        f"ok={target_status.get('ok', 0)} "
        f"failed={target_status.get('failed', 0)} "
        f"skipped={target_status.get('skipped', 0)}"
    )
    console.print(
        f"[green]Inspection done[/green] "
        f"targets={result.get('targets', 0)} "
        f"findings={result.get('findings', 0)} "
        f"errors={result.get('target_errors', 0)} "
        f"status=({status_text})"
    )
    report_path = result.get("report_path", "")
    console.print("Report:")
    console.print(f"  {_shorten_path_for_display(report_path)}")
    if result.get("case_id"):
        console.print(f"Case: {result['case_id']}")


# ============================================================================
# Cron Commands
# ============================================================================


cron_app = typer.Typer(help="Manage scheduled jobs")
app.add_typer(cron_app, name="cron")


def _cron_service():
    from nanobot.config.loader import get_data_dir
    from nanobot.cron.service import CronService

    return CronService(get_data_dir() / "cron" / "jobs.json")


@cron_app.command("add")
def cron_add(
    name: str = typer.Option(..., "--name", help="Job name"),
    message: str = typer.Option(..., "--message", help="Job message"),
    every_seconds: int | None = typer.Option(None, "--every-seconds", help="Run every N seconds"),
    cron_expr: str | None = typer.Option(None, "--cron", help="Cron expression"),
    tz: str | None = typer.Option(None, "--tz", help="Timezone for --cron (e.g. Asia/Shanghai)"),
    at: str | None = typer.Option(None, "--at", help="Run once at ISO datetime"),
):
    """Add a cron job."""
    from datetime import datetime

    from nanobot.cron.types import CronSchedule

    if tz and not cron_expr:
        console.print("[red]Error: tz can only be used with --cron[/red]")
        raise typer.Exit(1)
    if sum(1 for x in [every_seconds, cron_expr, at] if x) != 1:
        console.print("[red]Error: choose exactly one of --every-seconds / --cron / --at[/red]")
        raise typer.Exit(1)

    if every_seconds:
        schedule = CronSchedule(kind="every", every_ms=every_seconds * 1000)
    elif cron_expr:
        schedule = CronSchedule(kind="cron", expr=cron_expr, tz=tz)
    else:
        dt = datetime.fromisoformat(str(at))
        schedule = CronSchedule(kind="at", at_ms=int(dt.timestamp() * 1000))

    try:
        job = _cron_service().add_job(
            name=name,
            schedule=schedule,
            message=message,
            delete_after_run=(schedule.kind == "at"),
        )
    except ValueError as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)

    console.print(f"[green]Added job[/green] {job.id} ({job.schedule.kind})")


@cron_app.command("list")
def cron_list():
    """List cron jobs."""
    jobs = _cron_service().list_jobs(include_disabled=True)
    if not jobs:
        console.print("[yellow]No jobs.[/yellow]")
        return
    table = Table(title="Cron Jobs")
    table.add_column("ID", style="cyan")
    table.add_column("Name")
    table.add_column("Schedule")
    table.add_column("Enabled")
    for j in jobs:
        schedule = j.schedule.kind
        if j.schedule.kind == "every":
            schedule = f"every {int((j.schedule.every_ms or 0) / 1000)}s"
        elif j.schedule.kind == "cron":
            schedule = f"cron {j.schedule.expr or ''} ({j.schedule.tz or 'local'})"
        elif j.schedule.kind == "at":
            schedule = f"at {j.schedule.at_ms}"
        table.add_row(j.id, j.name, schedule, "yes" if j.enabled else "no")
    console.print(table)


@cron_app.command("remove")
def cron_remove(job_id: str = typer.Argument(..., help="Job ID")):
    """Remove one cron job."""
    ok = _cron_service().remove_job(job_id)
    if not ok:
        console.print(f"[red]Job not found:[/red] {job_id}")
        raise typer.Exit(1)
    console.print(f"[green]Removed[/green] {job_id}")


# ============================================================================
# OAuth Login
# ============================================================================

provider_app = typer.Typer(help="Manage providers")
app.add_typer(provider_app, name="provider")


_LOGIN_HANDLERS: dict[str, callable] = {}


def _register_login(name: str):
    def decorator(fn):
        _LOGIN_HANDLERS[name] = fn
        return fn
    return decorator


@provider_app.command("login")
def provider_login(
    provider: str = typer.Argument(..., help="OAuth provider (e.g. 'openai-codex', 'github-copilot')"),
):
    """Authenticate with an OAuth provider."""
    from nanobot.providers.registry import PROVIDERS

    key = provider.replace("-", "_")
    spec = next((s for s in PROVIDERS if s.name == key and s.is_oauth), None)
    if not spec:
        names = ", ".join(s.name.replace("_", "-") for s in PROVIDERS if s.is_oauth)
        console.print(f"[red]Unknown OAuth provider: {provider}[/red]  Supported: {names}")
        raise typer.Exit(1)

    handler = _LOGIN_HANDLERS.get(spec.name)
    if not handler:
        console.print(f"[red]Login not implemented for {spec.label}[/red]")
        raise typer.Exit(1)

    console.print(f"{__logo__} OAuth Login - {spec.label}\n")
    handler()


@_register_login("openai_codex")
def _login_openai_codex() -> None:
    try:
        from oauth_cli_kit import get_token, login_oauth_interactive
        token = None
        try:
            token = get_token()
        except Exception:
            pass
        if not (token and token.access):
            console.print("[cyan]Starting interactive OAuth login...[/cyan]\n")
            token = login_oauth_interactive(
                print_fn=lambda s: console.print(s),
                prompt_fn=lambda s: typer.prompt(s),
            )
        if not (token and token.access):
            console.print("[red]✗ Authentication failed[/red]")
            raise typer.Exit(1)
        console.print(f"[green]✓ Authenticated with OpenAI Codex[/green]  [dim]{token.account_id}[/dim]")
    except ImportError:
        console.print("[red]oauth_cli_kit not installed. Run: pip install oauth-cli-kit[/red]")
        raise typer.Exit(1)


@_register_login("github_copilot")
def _login_github_copilot() -> None:
    import asyncio

    console.print("[cyan]Starting GitHub Copilot device flow...[/cyan]\n")

    async def _trigger():
        from litellm import acompletion
        await acompletion(model="github_copilot/gpt-4o", messages=[{"role": "user", "content": "hi"}], max_tokens=1)

    try:
        asyncio.run(_trigger())
        console.print("[green]✓ Authenticated with GitHub Copilot[/green]")
    except Exception as e:
        console.print(f"[red]Authentication error: {e}[/red]")
        raise typer.Exit(1)


if __name__ == "__main__":
    app()
