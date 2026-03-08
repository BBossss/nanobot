import json
from datetime import datetime
from pathlib import Path

from typer.testing import CliRunner

from nanobot.cases.importer import CaseImporter
from nanobot.cases.store import CaseStore
from nanobot.cli.commands import app
from nanobot.config.schema import Config


runner = CliRunner()


def _make_store(tmp_path: Path) -> CaseStore:
    return CaseStore(workspace=tmp_path, cases_path=str(tmp_path / "notes" / "cases"))


def test_case_store_write_and_get(tmp_path: Path) -> None:
    store = _make_store(tmp_path)
    item = store.write_case(
        title="Node panic on startup",
        trigger="cli",
        source="generated",
        summary="node-1 panic during boot",
        evidence="panic stack trace in /var/log/messages",
        conclusion="kernel module mismatch",
        suggestion="align module version and reboot",
        host="node-1",
        service="kernel",
        tags=["hci", "panic"],
    )

    got, content = store.get_case(item["id"])
    assert got is not None
    assert got["title"] == "Node panic on startup"
    assert "Node panic on startup" in (content or "")
    assert "# Evidence" in (content or "")
    assert got["summary"] == "node-1 panic during boot"


def test_case_store_search_filters(tmp_path: Path) -> None:
    store = _make_store(tmp_path)
    store.write_case(
        title="Disk io spike",
        trigger="cli",
        source="generated",
        summary="disk io and iowait are high",
        evidence="iostat snapshot",
        conclusion="compaction task running",
        suggestion="reschedule task",
        host="node-a",
        service="storage",
        tags=["storage", "perf"],
        created_at=datetime(2026, 3, 7, 9, 0, 0),
    )
    store.write_case(
        title="Network packet drop",
        trigger="cli",
        source="generated",
        summary="packet drop on vm traffic",
        evidence="netstat counters",
        conclusion="nic queue overflow",
        suggestion="tune queue and verify",
        host="node-b",
        service="network",
        tags=["network"],
        created_at=datetime(2026, 3, 7, 10, 0, 0),
    )

    by_keyword = store.search_cases(keyword="packet")
    assert len(by_keyword) == 1
    assert by_keyword[0]["service"] == "network"

    by_host = store.search_cases(host="node-a")
    assert len(by_host) == 1
    assert by_host[0]["title"] == "Disk io spike"

    by_tag = store.search_cases(tag="storage")
    assert len(by_tag) == 1
    assert by_tag[0]["host"] == "node-a"

    by_service = store.search_cases(service="net")
    assert len(by_service) == 1
    assert by_service[0]["host"] == "node-b"


def test_case_store_supports_cases_path_outside_workspace(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    external_cases = tmp_path / "external-cases"
    store = CaseStore(workspace=workspace, cases_path=str(external_cases))

    item = store.write_case(
        title="external case",
        trigger="cli",
        source="generated",
        summary="summary",
        evidence="evidence",
        conclusion="conclusion",
        suggestion="suggestion",
    )

    assert Path(item["path"]).is_absolute()
    meta, content = store.get_case(item["id"])
    assert meta is not None
    assert content is not None
    assert "external case" in content


def test_case_store_saves_index_to_real_file(tmp_path: Path) -> None:
    store = _make_store(tmp_path)
    item = store.write_case(
        title="atomic index",
        trigger="cli",
        source="generated",
        summary="summary",
        evidence="evidence",
        conclusion="conclusion",
        suggestion="suggestion",
    )

    data = json.loads((tmp_path / "notes" / "cases" / "index.json").read_text(encoding="utf-8"))
    assert data["cases"][0]["id"] == item["id"]


def test_case_importer_imports_text_markdown_and_json(tmp_path: Path) -> None:
    source = tmp_path / "import_source"
    source.mkdir(parents=True, exist_ok=True)
    (source / "a.md").write_text("# A\nissue details", encoding="utf-8")
    (source / "b.txt").write_text("plain text case", encoding="utf-8")
    (source / "c.json").write_text(
        '[{"title":"json one","summary":"s1"},{"title":"json two","summary":"s2"}]',
        encoding="utf-8",
    )

    store = _make_store(tmp_path)
    importer = CaseImporter(store)
    imported = importer.import_path(str(source))

    assert len(imported) == 4
    assert any(i["title"] == "json one" for i in imported)
    assert any(i["title"] == "a" for i in imported)


def test_cases_cli_commands(tmp_path: Path, monkeypatch) -> None:
    cfg = Config()
    cfg.agents.defaults.workspace = str(tmp_path)
    cfg.cases.path = str(tmp_path / "notes" / "cases")

    monkeypatch.setattr("nanobot.config.loader.load_config", lambda: cfg)

    empty_list = runner.invoke(app, ["cases", "list"])
    assert empty_list.exit_code == 0
    assert "No cases found" in empty_list.stdout

    store = _make_store(tmp_path)
    item = store.write_case(
        title="CLI Case",
        trigger="cli",
        source="generated",
        summary="summary",
        evidence="evidence",
        conclusion="conclusion",
        suggestion="suggestion",
        tags=["cli"],
    )

    listed = runner.invoke(app, ["cases", "list"])
    assert listed.exit_code == 0
    assert "CLI Case" in listed.stdout
    assert item["id"] in listed.stdout

    shown = runner.invoke(app, ["cases", "show", item["id"]])
    assert shown.exit_code == 0
    assert "CLI Case" in shown.stdout
    assert "Metadata" in shown.stdout
    assert "root_cause" in shown.stdout
    assert "Problem" in shown.stdout
    assert "Evidence" in shown.stdout
    assert "Conclusion" in shown.stdout
    assert "Suggestion" in shown.stdout

    src = tmp_path / "legacy.txt"
    src.write_text("legacy case content", encoding="utf-8")
    imported = runner.invoke(app, ["cases", "import", str(src)])
    assert imported.exit_code == 0
    assert "Imported 1 case" in imported.stdout
