from __future__ import annotations

import asyncio
from pathlib import Path

import pytest
from fastmcp import Client
from fastmcp.exceptions import ToolError

from scripts.fam_mcp import create_server


def test_mcp_queue_validation_and_person_reads(vault_root: Path, monkeypatch):
    monkeypatch.setenv("OBSIDIAN_VAULT_PATH", str(vault_root))

    async def check():
        async with Client(create_server()) as client:
            tools = {tool.name: tool for tool in await client.list_tools()}
            assert set(tools) == {"today", "validate", "tend", "list_people", "read_person"}
            assert tools["today"].annotations is not None
            assert tools["tend"].annotations is not None
            assert tools["read_person"].annotations is not None
            assert tools["today"].annotations.read_only_hint is False
            assert tools["tend"].annotations.read_only_hint is False
            assert tools["read_person"].annotations.read_only_hint is True
            report = await client.call_tool("validate", {})
            assert report.data == {"ok": True, "errors": []}
            queue = await client.call_tool("today", {"on_date": "2026-05-15", "limit": 1})
            assert queue.data == [
                {
                    "name": "Dan",
                    "circle": "orbit",
                    "last_contacted": None,
                    "days": None,
                    "days_overdue": None,
                    "score": "inf",
                    "path": "People/@Dan.md",
                    "snoozed": False,
                }
            ]
            people = await client.call_tool("list_people", {"circle": "passive"})
            assert people.data == [
                {
                    "name": "Carol",
                    "circle": "passive",
                    "path": "People/@Carol.md",
                    "last_contacted": None,
                }
            ]
            note = await client.call_tool("read_person", {"path": "People/@Alice.md"})
            assert note.data["content"] == (vault_root / "People/@Alice.md").read_text()
            assert note.data["last_contacted"] == "2026-04-22"
            for path in ("../outside.md", "/etc/passwd", "fam-circles.md"):
                with pytest.raises(ToolError, match="person note"):
                    await client.call_tool("read_person", {"path": path})
            for arguments in ({"limit": -1}, {"circle": "unknown"}, {"on_date": "tomorrow"}):
                with pytest.raises(ToolError):
                    await client.call_tool("today", arguments)

    asyncio.run(check())


def test_mcp_tend_previews_without_writing(vault_root: Path, monkeypatch):
    monkeypatch.setenv("OBSIDIAN_VAULT_PATH", str(vault_root))
    before = {p: p.read_bytes() for p in vault_root.rglob("*.md")}

    async def check():
        async with Client(create_server()) as client:
            result = await client.call_tool("tend", {"person_name": "New Person", "dry_run": True})
            assert result.data == {
                "created": [],
                "retried": [],
                "failed": [],
                "planned": ["@New Person"],
            }

    asyncio.run(check())
    assert {p: p.read_bytes() for p in vault_root.rglob("*.md")} == before


def test_mcp_validation_reports_invalid_vault_and_stops_queue(vault_root: Path, monkeypatch):
    monkeypatch.setenv("OBSIDIAN_VAULT_PATH", str(vault_root))
    invalid = vault_root / "People/@Invalid.md"
    invalid.write_text("---\ncircle: nonexistent\n---\n")

    async def check():
        async with Client(create_server()) as client:
            report = await client.call_tool("validate", {})
            assert report.data["ok"] is False
            assert "unknown circle" in report.data["errors"][0]
            with pytest.raises(ToolError, match="preflight failed"):
                await client.call_tool("today", {})

    asyncio.run(check())


def test_mcp_person_reads_reject_symlink_escape(vault_root: Path, tmp_path: Path, monkeypatch):
    monkeypatch.setenv("OBSIDIAN_VAULT_PATH", str(vault_root))
    outside = tmp_path / "@Outside.md"
    outside.write_text("---\ncircle: passive\n---\nprivate")
    (vault_root / "People/@Outside.md").symlink_to(outside)

    async def check():
        async with Client(create_server()) as client:
            with pytest.raises(ToolError, match="person note"):
                await client.call_tool("read_person", {"path": "People/@Outside.md"})
            people = await client.call_tool("list_people", {})
            assert not any(row["name"] == "Outside" for row in people.data)
            await client.call_tool("today", {})

    asyncio.run(check())


def test_http_requires_auth_and_serves_real_mcp(vault_root: Path, tmp_path: Path, monkeypatch):
    import socket
    import subprocess
    import sys
    import time
    import urllib.error
    import urllib.request

    monkeypatch.setenv("OBSIDIAN_VAULT_PATH", str(vault_root))
    missing_token = subprocess.run(
        [sys.executable, "-m", "scripts.fam_mcp", "--transport", "http"],
        capture_output=True,
        text=True,
        env={
            "PATH": str(Path(sys.executable).parent),
            "OBSIDIAN_VAULT_PATH": str(vault_root),
        },
    )
    assert missing_token.returncode != 0
    assert "HTTP transport requires" in missing_token.stderr
    token = tmp_path / "token"
    token.write_text("fixture-token")
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]
    url = f"http://127.0.0.1:{port}"
    with (tmp_path / "server.log").open("w+") as log:
        process = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "scripts.fam_mcp",
                "--transport",
                "http",
                "--port",
                str(port),
                "--token-file",
                str(token),
            ],
            stdout=log,
            stderr=log,
        )
        try:
            deadline = time.monotonic() + 15
            while True:
                try:
                    urllib.request.urlopen(f"{url}/healthz", timeout=1).close()
                    break
                except urllib.error.URLError:
                    if process.poll() is not None or time.monotonic() >= deadline:
                        log.seek(0)
                        pytest.fail(log.read())
                    time.sleep(0.05)
            for authorization in (None, "Bearer wrong-token"):
                headers = {"Content-Type": "application/json"}
                if authorization:
                    headers["Authorization"] = authorization
                request = urllib.request.Request(f"{url}/mcp", data=b"{}", headers=headers)
                with pytest.raises(urllib.error.HTTPError) as error:
                    urllib.request.urlopen(request, timeout=2)
                assert error.value.code == 401

            async def check():
                async with Client(f"{url}/mcp", auth="fixture-token") as client:
                    result = await client.call_tool("validate", {})
                    assert result.data == {"ok": True, "errors": []}

            asyncio.run(check())
        finally:
            process.terminate()
            process.wait(timeout=10)
