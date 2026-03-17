"""Agent loop: the core processing engine."""

from __future__ import annotations

import asyncio
import json
import re
import weakref
from contextlib import AsyncExitStack
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, Awaitable, Callable

from loguru import logger

from nanobot.agent.context import ContextBuilder
from nanobot.agent.memory import MemoryStore
from nanobot.agent.multi_target import execute_multi_target_tool, supports_multi_target_tool
from nanobot.agent.subagent import SubagentManager
from nanobot.agent.tools.cron import CronTool
from nanobot.agent.tools.cases import GetCaseTool, SearchCasesTool
from nanobot.agent.tools.diagnostics import (
    DiagnoseLogReadTool,
    DiagnoseLogSearchTool,
    DiagnoseSystemStatusTool,
)
from nanobot.agent.tools.filesystem import EditFileTool, ListDirTool, ReadFileTool, WriteFileTool
from nanobot.agent.tools.message import MessageTool
from nanobot.agent.tools.planning import PlanningTool
from nanobot.agent.tools.registry import ToolRegistry
from nanobot.agent.tools.shell import ExecTool
from nanobot.agent.tools.troubleshooting import (
    DiskSnapshotTool,
    FindLogsTool,
    FindRecentFilesTool,
    JournalTailTool,
    NetworkSnapshotTool,
    ProcessSnapshotTool,
    ReadLogTailTool,
    SearchLogTool,
    ServiceStatusTool,
)
from nanobot.agent.tools.spawn import SpawnTool
from nanobot.agent.tools.web import WebFetchTool, WebSearchTool
from nanobot.bus.events import InboundMessage, OutboundMessage
from nanobot.bus.queue import MessageBus
from nanobot.cases.store import CaseStore
from nanobot.policies.cases import CaseRecordPolicy
from nanobot.policies.skills import SkillRoutingPolicy
from nanobot.providers.base import LLMProvider
from nanobot.session.manager import Session, SessionManager

if TYPE_CHECKING:
    from nanobot.config.schema import (
        CasesConfig,
        ChannelsConfig,
        DiagnosticsToolConfig,
        ExecToolConfig,
        TargetingConfig,
        TroubleshootingToolConfig,
    )
    from nanobot.cron.service import CronService


@dataclass
class InvestigationState:
    """Per-request lightweight investigation state."""

    rounds: int = 0
    consecutive_stale_rounds: int = 0
    checked_objects: set[str] = field(default_factory=set)


class AgentLoop:
    """
    The agent loop is the core processing engine.

    It:
    1. Receives messages from the bus
    2. Builds context with history, memory, skills
    3. Calls the LLM
    4. Executes tool calls
    5. Sends responses back
    """

    _TOOL_RESULT_MAX_CHARS = 500

    def __init__(
        self,
        bus: MessageBus,
        provider: LLMProvider,
        workspace: Path,
        model: str | None = None,
        max_iterations: int = 40,
        temperature: float = 0.1,
        max_tokens: int = 4096,
        memory_window: int = 100,
        reasoning_effort: str | None = None,
        brave_api_key: str | None = None,
        web_proxy: str | None = None,
        exec_config: ExecToolConfig | None = None,
        diagnostics_config: DiagnosticsToolConfig | None = None,
        troubleshooting_config: TroubleshootingToolConfig | None = None,
        cases_config: CasesConfig | None = None,
        targeting: TargetingConfig | None = None,
        cron_service: CronService | None = None,
        restrict_to_workspace: bool = False,
        session_manager: SessionManager | None = None,
        mcp_servers: dict | None = None,
        channels_config: ChannelsConfig | None = None,
    ):
        from nanobot.config.schema import ExecToolConfig
        self.bus = bus
        self.channels_config = channels_config
        self.provider = provider
        self.workspace = workspace
        self.model = model or provider.get_default_model()
        self.max_iterations = max_iterations
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.memory_window = memory_window
        self.reasoning_effort = reasoning_effort
        self.brave_api_key = brave_api_key
        self.web_proxy = web_proxy
        self.exec_config = exec_config or ExecToolConfig()
        self.max_investigation_rounds = max(1, self.exec_config.max_investigation_rounds)
        self.diagnostics_config = diagnostics_config
        self.troubleshooting_config = troubleshooting_config
        self.cases_config = cases_config
        self.targeting = targeting
        self.cron_service = cron_service
        self.restrict_to_workspace = restrict_to_workspace

        self.context = ContextBuilder(workspace)
        self.sessions = session_manager or SessionManager(workspace)
        self.tools = ToolRegistry()
        self.subagents = SubagentManager(
            provider=provider,
            workspace=workspace,
            bus=bus,
            model=self.model,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
            reasoning_effort=reasoning_effort,
            brave_api_key=brave_api_key,
            web_proxy=web_proxy,
            exec_config=self.exec_config,
            restrict_to_workspace=restrict_to_workspace,
        )

        self._running = False
        self._mcp_servers = mcp_servers or {}
        self._mcp_stack: AsyncExitStack | None = None
        self._mcp_connected = False
        self._mcp_connecting = False
        self._consolidating: set[str] = set()  # Session keys with consolidation in progress
        self._consolidation_tasks: set[asyncio.Task] = set()  # Strong refs to in-flight tasks
        self._consolidation_locks: weakref.WeakValueDictionary[str, asyncio.Lock] = weakref.WeakValueDictionary()
        self._active_tasks: dict[str, list[asyncio.Task]] = {}  # session_key -> tasks
        self._session_locks: dict[str, asyncio.Lock] = {}
        self._case_store = CaseStore(
            workspace=self.workspace,
            cases_path=cases_config.path if cases_config else None,
        )
        self._register_default_tools()

    def _register_default_tools(self) -> None:
        """Register the default set of tools."""
        allowed_dir = self.workspace if self.restrict_to_workspace else None
        for cls in (ReadFileTool, WriteFileTool, EditFileTool, ListDirTool):
            self.tools.register(cls(workspace=self.workspace, allowed_dir=allowed_dir))
        self.tools.register(ExecTool(
            working_dir=str(self.workspace),
            timeout=self.exec_config.timeout,
            restrict_to_workspace=self.restrict_to_workspace,
            path_append=self.exec_config.path_append,
            readonly_mode=self.exec_config.readonly_mode,
            allowed_commands=self.exec_config.allowed_commands,
            approval_file=self.exec_config.approval_file,
            default_target=self.exec_config.default_target,
            ssh_enabled=self.exec_config.ssh.enabled,
        ))
        diag_cfg = self.diagnostics_config
        if diag_cfg is None or diag_cfg.enabled:
            timeout = diag_cfg.timeout if diag_cfg else 20
            max_read_lines = diag_cfg.max_read_lines if diag_cfg else 2000
            max_search_hits = diag_cfg.max_search_hits if diag_cfg else 100
            allowed_paths = diag_cfg.allowed_paths if diag_cfg else ["/var/log", "/opt/logs"]
            self.tools.register(DiagnoseLogReadTool(
                workspace=self.workspace,
                timeout=timeout,
                max_read_lines=max_read_lines,
                max_search_hits=max_search_hits,
                allowed_paths=allowed_paths,
            ))
            self.tools.register(DiagnoseLogSearchTool(
                workspace=self.workspace,
                timeout=timeout,
                max_read_lines=max_read_lines,
                max_search_hits=max_search_hits,
                allowed_paths=allowed_paths,
            ))
            self.tools.register(DiagnoseSystemStatusTool(
                workspace=self.workspace,
                timeout=timeout,
                max_read_lines=max_read_lines,
                max_search_hits=max_search_hits,
                allowed_paths=allowed_paths,
            ))
        troubleshoot_cfg = self.troubleshooting_config
        if troubleshoot_cfg is None or troubleshoot_cfg.enabled:
            self.tools.register(FindLogsTool(
                allowed_log_roots=troubleshoot_cfg.allowed_log_roots if troubleshoot_cfg else None,
                max_results=20,
            ))
            self.tools.register(ReadLogTailTool(
                default_lines=troubleshoot_cfg.default_tail_lines if troubleshoot_cfg else 200,
                max_lines=troubleshoot_cfg.max_tail_lines if troubleshoot_cfg else 2000,
            ))
            self.tools.register(SearchLogTool(
                max_hits=troubleshoot_cfg.max_search_hits if troubleshoot_cfg else 100,
            ))
            self.tools.register(ServiceStatusTool())
            self.tools.register(ProcessSnapshotTool())
            self.tools.register(JournalTailTool(
                default_lines=troubleshoot_cfg.default_tail_lines if troubleshoot_cfg else 200,
                max_lines=troubleshoot_cfg.max_tail_lines if troubleshoot_cfg else 2000,
            ))
            self.tools.register(DiskSnapshotTool())
            self.tools.register(NetworkSnapshotTool())
            self.tools.register(FindRecentFilesTool(
                allowed_log_roots=troubleshoot_cfg.allowed_log_roots if troubleshoot_cfg else None,
                max_results=troubleshoot_cfg.max_recent_files if troubleshoot_cfg else 50,
            ))
        self.tools.register(WebSearchTool(api_key=self.brave_api_key, proxy=self.web_proxy))
        self.tools.register(WebFetchTool(proxy=self.web_proxy))
        self.tools.register(SearchCasesTool(workspace=self.workspace, cases_path=self.cases_config.path if self.cases_config else None))
        self.tools.register(GetCaseTool(workspace=self.workspace, cases_path=self.cases_config.path if self.cases_config else None))
        self.tools.register(PlanningTool())
        self.tools.register(MessageTool(send_callback=self.bus.publish_outbound))
        self.tools.register(SpawnTool(manager=self.subagents))
        if self.cron_service:
            self.tools.register(CronTool(self.cron_service))

    async def _connect_mcp(self) -> None:
        """Connect to configured MCP servers (one-time, lazy)."""
        if self._mcp_connected or self._mcp_connecting or not self._mcp_servers:
            return
        self._mcp_connecting = True
        from nanobot.agent.tools.mcp import connect_mcp_servers
        try:
            self._mcp_stack = AsyncExitStack()
            await self._mcp_stack.__aenter__()
            await connect_mcp_servers(self._mcp_servers, self.tools, self._mcp_stack)
            self._mcp_connected = True
        except Exception as e:
            logger.error("Failed to connect MCP servers (will retry next message): {}", e)
            if self._mcp_stack:
                try:
                    await self._mcp_stack.aclose()
                except Exception:
                    pass
                self._mcp_stack = None
        finally:
            self._mcp_connecting = False

    def _set_tool_context(self, channel: str, chat_id: str, message_id: str | None = None) -> None:
        """Update context for all tools that need routing info."""
        for name in ("message", "spawn", "cron", "exec"):
            if tool := self.tools.get(name):
                if hasattr(tool, "set_context"):
                    tool.set_context(channel, chat_id, *([message_id] if name == "message" else []))

    @staticmethod
    def _strip_think(text: str | None) -> str | None:
        """Remove <think>…</think> blocks that some models embed in content."""
        if not text:
            return None
        return re.sub(r"<think>[\s\S]*?</think>", "", text).strip() or None

    @staticmethod
    def _tool_hint(tool_calls: list) -> str:
        """Format tool calls as concise hint, e.g. 'web_search("query")'."""
        def _fmt(tc):
            args = (tc.arguments[0] if isinstance(tc.arguments, list) else tc.arguments) or {}
            val = next(iter(args.values()), None) if isinstance(args, dict) else None
            if not isinstance(val, str):
                return tc.name
            return f'{tc.name}("{val[:40]}…")' if len(val) > 40 else f'{tc.name}("{val}")'
        return ", ".join(_fmt(tc) for tc in tool_calls)

    @staticmethod
    def _redact_sensitive_value(value):
        """Recursively redact secret-bearing fields before logging or persistence."""
        if isinstance(value, dict):
            redacted = {}
            for key, item in value.items():
                if key == "ssh_password":
                    redacted[key] = "***"
                else:
                    redacted[key] = AgentLoop._redact_sensitive_value(item)
            return redacted
        if isinstance(value, list):
            return [AgentLoop._redact_sensitive_value(item) for item in value]
        return value

    @staticmethod
    def _redact_tool_calls(tool_calls: list[dict] | None) -> list[dict] | None:
        """Redact secrets inside OpenAI-format tool call payloads."""
        if not tool_calls:
            return tool_calls

        redacted = []
        for call in tool_calls:
            entry = dict(call)
            fn = dict(entry.get("function") or {})
            args = fn.get("arguments")
            if isinstance(args, str):
                try:
                    parsed = json.loads(args)
                except Exception:
                    parsed = None
                if isinstance(parsed, dict):
                    fn["arguments"] = json.dumps(
                        AgentLoop._redact_sensitive_value(parsed),
                        ensure_ascii=False,
                    )
            elif isinstance(args, dict):
                fn["arguments"] = AgentLoop._redact_sensitive_value(args)
            entry["function"] = fn
            redacted.append(entry)
        return redacted

    @staticmethod
    def _tool_call_signature(name: str, arguments: dict[str, Any]) -> str:
        """Build a stable signature for repeated investigation actions."""
        return json.dumps({"name": name, "arguments": arguments}, ensure_ascii=False, sort_keys=True)

    @staticmethod
    def _result_signature(name: str, arguments: dict[str, Any], result: str) -> str:
        """Normalize tool output for evidence de-duplication."""
        target = arguments.get("target", "")
        payload = {
            "name": name,
            "target": target,
            "result": result.strip(),
        }
        return json.dumps(payload, ensure_ascii=False, sort_keys=True)

    @staticmethod
    def _object_signature(name: str, arguments: dict[str, Any]) -> str | None:
        """Build a signature for repeated investigation objects."""
        target = arguments.get("target", "")
        obj = None
        if name in {"read_log_tail", "search_log", "diagnose_log_read", "diagnose_log_search"}:
            if path := arguments.get("path"):
                obj = f"path:{path}"
        elif name in {"service_status", "journal_tail"}:
            if service := arguments.get("service"):
                obj = f"service:{service}"
        elif name in {"process_snapshot", "disk_snapshot", "network_snapshot", "diagnose_system_status"}:
            scope = arguments.get("scope", "")
            obj = f"snapshot:{name}:{scope}"
        elif name == "find_logs":
            if keyword := arguments.get("keyword"):
                obj = f"keyword:{keyword}"
        elif name == "find_recent_files":
            if base_path := arguments.get("base_path"):
                obj = f"path:{base_path}"
        if not obj:
            return None
        payload = {"name": name, "target": target, "object": obj}
        return json.dumps(payload, ensure_ascii=False, sort_keys=True)

    @staticmethod
    def _format_cached_tool_result(result: str) -> str:
        """Annotate reused tool output so the model can converge instead of re-sampling."""
        base = result.strip() or "(no output)"
        return (
            f"{base}\n\n"
            "[Investigation cache] Reused an identical tool call result from this same request; "
            "no new evidence was produced."
        )

    def _build_investigation_limit_message(self) -> str:
        """Build the stop message when the investigation round limit is reached."""
        return (
            f"I reached the maximum investigation rounds ({self.max_investigation_rounds}) "
            "for this request. Summarize the evidence collected so far, state what remains uncertain, "
            "and propose the next highest-value readonly check."
        )

    @staticmethod
    def _build_stale_investigation_message() -> str:
        """Build the stop message when repeated rounds stop yielding new evidence."""
        return (
            "I stopped the investigation because two consecutive rounds produced no new evidence. "
            "Summarize the current findings, distinguish facts from inference, and suggest either "
            "a narrower target/time window or the next best readonly direction."
        )

    async def _run_agent_loop(
        self,
        initial_messages: list[dict],
        on_progress: Callable[..., Awaitable[None]] | None = None,
        session: Session | None = None,
    ) -> tuple[str | None, list[str], list[dict]]:
        """Run the agent iteration loop. Returns (final_content, tools_used, messages)."""
        messages = initial_messages
        iteration = 0
        final_content = None
        tools_used: list[str] = []
        investigation = InvestigationState()
        tool_result_cache: dict[str, str] = {}
        object_result_cache: dict[str, str] = {}
        seen_result_signatures: set[str] = set()

        while iteration < self.max_iterations:
            iteration += 1

            response = await self.provider.chat(
                messages=messages,
                tools=self.tools.get_definitions(),
                model=self.model,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
                reasoning_effort=self.reasoning_effort,
            )

            if response.has_tool_calls:
                investigation.rounds += 1
                if on_progress:
                    clean = self._strip_think(response.content)
                    if clean:
                        await on_progress(clean)
                    await on_progress(self._tool_hint(response.tool_calls), tool_hint=True)

                tool_call_dicts = [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.name,
                            "arguments": json.dumps(
                                self._redact_sensitive_value(tc.arguments),
                                ensure_ascii=False,
                            )
                        }
                    }
                    for tc in response.tool_calls
                ]
                messages = self.context.add_assistant_message(
                    messages, response.content, tool_call_dicts,
                    reasoning_content=response.reasoning_content,
                    thinking_blocks=response.thinking_blocks,
                )

                round_has_new_evidence = False
                for tool_call in response.tool_calls:
                    tools_used.append(tool_call.name)
                    args_str = json.dumps(
                        self._redact_sensitive_value(tool_call.arguments),
                        ensure_ascii=False,
                    )
                    logger.info("Tool call: {}({})", tool_call.name, args_str[:200])
                    signature = self._tool_call_signature(tool_call.name, tool_call.arguments)
                    object_signature = self._object_signature(tool_call.name, tool_call.arguments)
                    if object_signature and object_signature in object_result_cache:
                        result = self._format_cached_tool_result(object_result_cache[object_signature])
                    elif signature in tool_result_cache:
                        result = self._format_cached_tool_result(tool_result_cache[signature])
                    else:
                        result = await self._execute_tool_call(tool_call.name, tool_call.arguments, session=session)
                        tool_result_cache[signature] = result
                        if object_signature:
                            object_result_cache[object_signature] = result
                            investigation.checked_objects.add(object_signature)
                        result_sig = self._result_signature(tool_call.name, tool_call.arguments, result)
                        if result_sig not in seen_result_signatures:
                            seen_result_signatures.add(result_sig)
                            round_has_new_evidence = True
                    messages = self.context.add_tool_result(
                        messages, tool_call.id, tool_call.name, result
                    )

                if round_has_new_evidence:
                    investigation.consecutive_stale_rounds = 0
                else:
                    investigation.consecutive_stale_rounds += 1

                if investigation.consecutive_stale_rounds >= 2:
                    final_content = self._build_stale_investigation_message()
                    break

                if investigation.rounds >= self.max_investigation_rounds:
                    final_content = self._build_investigation_limit_message()
                    break
            else:
                clean = self._strip_think(response.content)
                # Don't persist error responses to session history — they can
                # poison the context and cause permanent 400 loops (#1303).
                if response.finish_reason == "error":
                    logger.error("LLM returned error: {}", (clean or "")[:200])
                    final_content = clean or "Sorry, I encountered an error calling the AI model."
                    break
                messages = self.context.add_assistant_message(
                    messages, clean, reasoning_content=response.reasoning_content,
                    thinking_blocks=response.thinking_blocks,
                )
                final_content = clean
                break

        if final_content is None and iteration >= self.max_iterations:
            logger.warning("Max iterations ({}) reached", self.max_iterations)
            final_content = (
                f"I reached the maximum number of tool call iterations ({self.max_iterations}) "
                "without completing the task. You can try breaking the task into smaller steps."
            )

        return final_content, tools_used, messages

    async def run(self) -> None:
        """Run the agent loop, dispatching messages as tasks to stay responsive to /stop."""
        self._running = True
        await self._connect_mcp()
        logger.info("Agent loop started")

        while self._running:
            try:
                msg = await asyncio.wait_for(self.bus.consume_inbound(), timeout=1.0)
            except asyncio.TimeoutError:
                continue

            if msg.content.strip().lower() == "/stop":
                await self._handle_stop(msg)
            else:
                task = asyncio.create_task(self._dispatch(msg))
                self._active_tasks.setdefault(msg.session_key, []).append(task)
                task.add_done_callback(lambda t, k=msg.session_key: self._active_tasks.get(k, []) and self._active_tasks[k].remove(t) if t in self._active_tasks.get(k, []) else None)

    async def _handle_stop(self, msg: InboundMessage) -> None:
        """Cancel all active tasks and subagents for the session."""
        tasks = self._active_tasks.pop(msg.session_key, [])
        cancelled = sum(1 for t in tasks if not t.done() and t.cancel())
        for t in tasks:
            try:
                await t
            except (asyncio.CancelledError, Exception):
                pass
        sub_cancelled = await self.subagents.cancel_by_session(msg.session_key)
        total = cancelled + sub_cancelled
        content = f"⏹ Stopped {total} task(s)." if total else "No active task to stop."
        await self.bus.publish_outbound(OutboundMessage(
            channel=msg.channel, chat_id=msg.chat_id, content=content,
        ))

    async def _dispatch(self, msg: InboundMessage) -> None:
        """Process a message under the session lock."""
        lock = self._session_locks.setdefault(msg.session_key, asyncio.Lock())
        async with lock:
            try:
                response = await self._process_message(msg)
                if response is not None:
                    await self.bus.publish_outbound(response)
                elif msg.channel == "cli":
                    await self.bus.publish_outbound(OutboundMessage(
                        channel=msg.channel, chat_id=msg.chat_id,
                        content="", metadata=msg.metadata or {},
                    ))
            except asyncio.CancelledError:
                logger.info("Task cancelled for session {}", msg.session_key)
                raise
            except Exception:
                logger.exception("Error processing message for session {}", msg.session_key)
                await self.bus.publish_outbound(OutboundMessage(
                    channel=msg.channel, chat_id=msg.chat_id,
                    content="Sorry, I encountered an error.",
                ))

    async def close_mcp(self) -> None:
        """Close MCP connections."""
        if self._mcp_stack:
            try:
                await self._mcp_stack.aclose()
            except (RuntimeError, BaseExceptionGroup):
                pass  # MCP SDK cancel scope cleanup is noisy but harmless
            self._mcp_stack = None

    def stop(self) -> None:
        """Stop the agent loop."""
        self._running = False
        logger.info("Agent loop stopping")

    async def _process_message(
        self,
        msg: InboundMessage,
        session_key: str | None = None,
        on_progress: Callable[[str], Awaitable[None]] | None = None,
    ) -> OutboundMessage | None:
        """Process a single inbound message and return the response."""
        # System messages: parse origin from chat_id ("channel:chat_id")
        if msg.channel == "system":
            channel, chat_id = (msg.chat_id.split(":", 1) if ":" in msg.chat_id
                                else ("cli", msg.chat_id))
            logger.info("Processing system message from {}", msg.sender_id)
            key = f"{channel}:{chat_id}"
            session = self.sessions.get_or_create(key)
            self._set_tool_context(channel, chat_id, msg.metadata.get("message_id"))
            history = session.get_history(max_messages=self.memory_window)
            messages = self.context.build_messages(
                history=history,
                current_message=msg.content,
                channel=channel,
                chat_id=chat_id,
                skill_names=SkillRoutingPolicy.select_skills(
                    content=msg.content,
                    channel=msg.channel,
                    metadata=msg.metadata,
                ),
            )
            final_content, _, all_msgs = await self._run_agent_loop(messages, session=session)
            self._save_turn(session, all_msgs, 1 + len(history))
            self.sessions.save(session)
            return OutboundMessage(channel=channel, chat_id=chat_id,
                                  content=final_content or "Background task completed.")

        preview = msg.content[:80] + "..." if len(msg.content) > 80 else msg.content
        logger.info("Processing message from {}:{}: {}", msg.channel, msg.sender_id, preview)

        key = session_key or msg.session_key
        session = self.sessions.get_or_create(key)

        # Slash commands
        cmd = msg.content.strip().lower()
        if cmd == "/new":
            lock = self._consolidation_locks.setdefault(session.key, asyncio.Lock())
            self._consolidating.add(session.key)
            try:
                async with lock:
                    snapshot = session.messages[session.last_consolidated:]
                    if snapshot:
                        temp = Session(key=session.key)
                        temp.messages = list(snapshot)
                        if not await self._consolidate_memory(temp, archive_all=True):
                            return OutboundMessage(
                                channel=msg.channel, chat_id=msg.chat_id,
                                content="Memory archival failed, session not cleared. Please try again.",
                            )
            except Exception:
                logger.exception("/new archival failed for {}", session.key)
                return OutboundMessage(
                    channel=msg.channel, chat_id=msg.chat_id,
                    content="Memory archival failed, session not cleared. Please try again.",
                )
            finally:
                self._consolidating.discard(session.key)

            session.clear()
            self.sessions.save(session)
            self.sessions.invalidate(session.key)
            return OutboundMessage(channel=msg.channel, chat_id=msg.chat_id,
                                  content="New session started.")
        if cmd == "/help":
            return OutboundMessage(channel=msg.channel, chat_id=msg.chat_id,
                                  content="🐈 nanobot commands:\n/new — Start a new conversation\n/stop — Stop the current task\n/help — Show available commands")

        gate_reply = self._handle_target_expansion_gate(session, msg.content)
        if gate_reply is not None:
            self.sessions.save(session)
            return OutboundMessage(channel=msg.channel, chat_id=msg.chat_id, content=gate_reply)

        unconsolidated = len(session.messages) - session.last_consolidated
        if (unconsolidated >= self.memory_window and session.key not in self._consolidating):
            self._consolidating.add(session.key)
            lock = self._consolidation_locks.setdefault(session.key, asyncio.Lock())

            async def _consolidate_and_unlock():
                try:
                    async with lock:
                        await self._consolidate_memory(session)
                finally:
                    self._consolidating.discard(session.key)
                    _task = asyncio.current_task()
                    if _task is not None:
                        self._consolidation_tasks.discard(_task)

            _task = asyncio.create_task(_consolidate_and_unlock())
            self._consolidation_tasks.add(_task)

        self._set_tool_context(msg.channel, msg.chat_id, msg.metadata.get("message_id"))
        if message_tool := self.tools.get("message"):
            if isinstance(message_tool, MessageTool):
                message_tool.start_turn()

        history = session.get_history(max_messages=self.memory_window)

        async def _bus_progress(content: str, *, tool_hint: bool = False) -> None:
            meta = dict(msg.metadata or {})
            meta["_progress"] = True
            meta["_tool_hint"] = tool_hint
            await self.bus.publish_outbound(OutboundMessage(
                channel=msg.channel, chat_id=msg.chat_id, content=content, metadata=meta,
            ))

        progress_cb = on_progress or _bus_progress
        initial_messages = self.context.build_messages(
            history=history,
            current_message=msg.content,
            media=msg.media if msg.media else None,
            channel=msg.channel,
            chat_id=msg.chat_id,
            skill_names=SkillRoutingPolicy.select_skills(
                content=msg.content,
                channel=msg.channel,
                metadata=msg.metadata,
            ),
        )

        if progress_cb:
            scope_hint = self._build_confirmed_scope_progress(session)
            if scope_hint:
                await progress_cb(scope_hint)

        final_content, _, all_msgs = await self._run_agent_loop(
            initial_messages, on_progress=progress_cb, session=session,
        )

        if final_content is None:
            final_content = "I've completed processing but have no response to give."

        self._save_turn(session, all_msgs, 1 + len(history))
        self.sessions.save(session)

        self._maybe_record_case(msg, final_content)

        if (mt := self.tools.get("message")) and isinstance(mt, MessageTool) and mt._sent_in_turn:
            return None

        preview = final_content[:120] + "..." if len(final_content) > 120 else final_content
        logger.info("Response to {}:{}: {}", msg.channel, msg.sender_id, preview)
        return OutboundMessage(
            channel=msg.channel, chat_id=msg.chat_id, content=final_content,
            metadata=msg.metadata or {},
        )

    def _maybe_record_case(self, msg: InboundMessage, final_content: str) -> None:
        cfg = self.cases_config
        if cfg and not cfg.enabled:
            return
        if cfg and not cfg.auto_record:
            return
        if cfg and not self._should_record_case(msg.content, cfg.record_mode):
            return
        cmd = msg.content.strip().lower()
        if cmd.startswith("/"):
            return
        draft = CaseRecordPolicy.build_generated_case(
            channel=msg.channel,
            content=msg.content,
            final_content=final_content,
        )
        item = self._case_store.write_case(
            title=draft.title,
            trigger=draft.trigger,
            source=draft.source,
            summary=draft.summary,
            evidence=draft.evidence,
            conclusion=draft.conclusion,
            suggestion=draft.suggestion,
            status=draft.status,
            tags=draft.tags,
        )
        entry = CaseRecordPolicy.build_history_entry(
            created_at=item["created_at"],
            case_id=item["id"],
            channel=msg.channel,
            title=item["title"],
            conclusion=draft.conclusion,
        )
        MemoryStore(self.workspace).append_history(entry)

    @staticmethod
    def _should_record_case(content: str, mode: str) -> bool:
        return CaseRecordPolicy.should_record(content, mode)

    def _save_turn(self, session: Session, messages: list[dict], skip: int) -> None:
        """Save new-turn messages into session, truncating large tool results."""
        from datetime import datetime
        for m in messages[skip:]:
            entry = dict(m)
            if "tool_calls" in entry:
                entry["tool_calls"] = self._redact_tool_calls(entry.get("tool_calls"))
            role, content = entry.get("role"), entry.get("content")
            if role == "assistant" and not content and not entry.get("tool_calls"):
                continue  # skip empty assistant messages — they poison session context
            if role == "tool" and isinstance(content, str) and len(content) > self._TOOL_RESULT_MAX_CHARS:
                entry["content"] = content[:self._TOOL_RESULT_MAX_CHARS] + "\n... (truncated)"
            elif role == "user":
                if isinstance(content, str) and content.startswith(ContextBuilder._RUNTIME_CONTEXT_TAG):
                    # Strip the runtime-context prefix, keep only the user text.
                    parts = content.split("\n\n", 1)
                    if len(parts) > 1 and parts[1].strip():
                        entry["content"] = parts[1]
                    else:
                        continue
                if isinstance(content, list):
                    filtered = []
                    for c in content:
                        if c.get("type") == "text" and isinstance(c.get("text"), str) and c["text"].startswith(ContextBuilder._RUNTIME_CONTEXT_TAG):
                            continue  # Strip runtime context from multimodal messages
                        if (c.get("type") == "image_url"
                                and c.get("image_url", {}).get("url", "").startswith("data:image/")):
                            filtered.append({"type": "text", "text": "[image]"})
                        else:
                            filtered.append(c)
                    if not filtered:
                        continue
                    entry["content"] = filtered
            entry.setdefault("timestamp", datetime.now().isoformat())
            session.messages.append(entry)
        session.updated_at = datetime.now()

    async def _consolidate_memory(self, session, archive_all: bool = False) -> bool:
        """Delegate to MemoryStore.consolidate(). Returns True on success."""
        return await MemoryStore(self.workspace).consolidate(
            session, self.provider, self.model,
            archive_all=archive_all, memory_window=self.memory_window,
        )

    async def process_direct(
        self,
        content: str,
        session_key: str = "cli:direct",
        channel: str = "cli",
        chat_id: str = "direct",
        on_progress: Callable[[str], Awaitable[None]] | None = None,
    ) -> str:
        """Process a message directly (for CLI or cron usage)."""
        await self._connect_mcp()
        msg = InboundMessage(channel=channel, sender_id="user", chat_id=chat_id, content=content)
        response = await self._process_message(msg, session_key=session_key, on_progress=on_progress)
        return response.content if response else ""

    async def _execute_tool_call(
        self,
        name: str,
        arguments: dict[str, Any],
        *,
        session: Session | None = None,
    ) -> str:
        """Execute a tool call, expanding to multiple targets when confirmed."""
        if (
            session
            and session.metadata.get("expansion_confirmed") is True
            and supports_multi_target_tool(name)
            and not arguments.get("target")
        ):
            resolved_targets = session.metadata.get("resolved_targets") or []
            if resolved_targets:
                return await execute_multi_target_tool(
                    tool_name=name,
                    arguments=arguments,
                    resolved_targets=resolved_targets,
                    execute_tool=self.tools.execute,
                )
        return await self.tools.execute(name, arguments)

    @staticmethod
    def _normalized_reply_token(content: str) -> str:
        return re.sub(r"\s+", "", content.strip().lower())

    def _handle_target_expansion_gate(self, session: Session, content: str) -> str | None:
        """Handle confirmation-gated cluster expansion before normal agent execution."""
        pending = session.metadata.get("pending_target_resolution")
        token = self._normalized_reply_token(content)
        if pending:
            if token in {"确认", "继续", "可以查", "yes", "y"}:
                session.metadata["resolved_target_ids"] = list(pending.get("resolved_target_ids", []))
                session.metadata["resolved_targets"] = list(pending.get("resolved_targets", []))
                session.metadata["resolution_reason"] = str(pending.get("reason", ""))
                session.metadata["expansion_confirmed"] = True
                session.metadata["pending_target_resolution"] = None
                return None
            if token in {"不用", "先单节点", "no", "n"}:
                session.metadata["pending_target_resolution"] = None
                session.metadata["expansion_confirmed"] = False
                session.metadata.pop("resolved_target_ids", None)
                session.metadata.pop("resolved_targets", None)
                session.metadata.pop("resolution_reason", None)
                return "保持单节点排障模式。如需多节点排查，我会先列出候选节点再请你确认。"

        resolution = self._resolve_target_intent(content)
        if not resolution:
            return None

        session.metadata["pending_target_resolution"] = resolution
        session.metadata["expansion_confirmed"] = False
        targets = ", ".join(resolution["resolved_target_ids"])
        suffix = "。候选范围已截断。" if resolution.get("truncated") else "。"
        return (
            f"{resolution['reason']}，候选节点为 {targets}{suffix}"
            " 如果要切换到多节点排查，请回复“确认”。当前仍保持单节点模式。"
        )

    def _resolve_target_intent(self, content: str) -> dict[str, Any] | None:
        """Resolve a candidate multi-target scope from the current message."""
        if not self.targeting or not self.targeting.targets:
            return None

        from nanobot.targets.intent_resolver import resolve_target_intent

        resolution = resolve_target_intent(content, self.targeting)
        if not resolution.should_expand:
            return None

        return {
            "reason": resolution.reason,
            "group_names": list(resolution.group_names),
            "label_any": list(resolution.label_any),
            "resolved_target_ids": [target.id for target in resolution.resolved_targets],
            "resolved_targets": [
                {"id": target.id, "target": target.target, "labels": list(target.labels)}
                for target in resolution.resolved_targets
            ],
            "truncated": resolution.truncated,
        }

    @staticmethod
    def _build_confirmed_scope_progress(session: Session) -> str | None:
        """Build a progress note for a confirmed multi-target troubleshooting scope."""
        if session.metadata.get("expansion_confirmed") is not True:
            return None
        target_ids = session.metadata.get("resolved_target_ids") or []
        if not target_ids:
            return None
        reason = str(session.metadata.get("resolution_reason", "")).strip()
        prefix = "已确认多节点排查范围"
        if reason:
            return f"{prefix}：{', '.join(target_ids)}。依据：{reason}"
        return f"{prefix}：{', '.join(target_ids)}。"
