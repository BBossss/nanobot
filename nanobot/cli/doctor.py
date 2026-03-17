"""CLI readiness checks for first-run experience."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from pathlib import Path

from nanobot.config.schema import Config
from nanobot.providers.custom_provider import CustomProvider


@dataclass(frozen=True)
class DoctorCheck:
    name: str
    status: str
    detail: str


def run_doctor(*, config_path: Path, workspace_path: Path, config: Config) -> list[DoctorCheck]:
    """Collect bounded readiness checks for the local CLI experience."""
    checks = [
        DoctorCheck(
            name="配置",
            status="ok" if config_path.exists() else "blocked",
            detail=str(config_path) if config_path.exists() else f"missing: {config_path}",
        ),
        DoctorCheck(
            name="工作区",
            status="ok" if workspace_path.exists() else "blocked",
            detail=str(workspace_path) if workspace_path.exists() else f"missing: {workspace_path}",
        ),
    ]

    field_status, field_detail = _check_minimal_provider_fields(config)
    checks.append(DoctorCheck(name="Provider 字段", status=field_status, detail=field_detail))

    if field_status != "ok":
        checks.append(
            DoctorCheck(
                name="模型连通性",
                status="blocked",
                detail="provider fields incomplete",
            )
        )
        return checks

    status, detail = probe_model_connectivity(config)
    checks.append(DoctorCheck(name="模型连通性", status=status, detail=detail))
    return checks


def probe_model_connectivity(config: Config) -> tuple[str, str]:
    """Probe whether the configured default model path can answer a minimal request."""
    try:
        return asyncio.run(_probe_model_connectivity_async(config))
    except Exception as exc:
        return "blocked", str(exc)


async def _probe_model_connectivity_async(config: Config) -> tuple[str, str]:
    provider_name = config.agents.defaults.provider
    model = config.agents.defaults.model
    provider = config.get_provider(model)

    if provider_name == "custom" and provider is not None:
        client = CustomProvider(
            api_key=provider.api_key or "no-key",
            api_base=provider.api_base or "http://localhost:8000/v1",
            default_model=model,
        )
        result = await client.chat(
            messages=[{"role": "user", "content": "Reply with OK"}],
            model=model,
            max_tokens=8,
            temperature=0,
        )
        if result.finish_reason == "error" or (result.content or "").startswith("Error:"):
            return "blocked", result.content or "provider returned an error"
        return "ok", "connected"

    return "partial", f"provider {provider_name} connectivity probe not implemented"


def _check_minimal_provider_fields(config: Config) -> tuple[str, str]:
    provider_name = config.agents.defaults.provider
    model = config.agents.defaults.model.strip()
    provider = config.get_provider(model)

    if not model:
        return "blocked", "missing model"
    if not provider_name:
        return "blocked", "missing provider"
    if provider_name == "custom":
        if not provider or not provider.api_base:
            return "blocked", "missing base_url"
        if not provider.api_key:
            return "blocked", "missing api_key"
        return "ok", f"{provider_name}:{model}"
    if not provider or not provider.api_key:
        return "blocked", f"missing api_key for {provider_name}"
    return "ok", f"{provider_name}:{model}"
