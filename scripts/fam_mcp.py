"""MCP access to fam's existing commands and person notes."""

from __future__ import annotations

import argparse
import os
from dataclasses import asdict
from datetime import date
from pathlib import Path
from typing import Annotated, Any, Literal

from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
from fastmcp.server.auth.providers.jwt import StaticTokenVerifier
from pydantic import Field
from starlette.requests import Request
from starlette.responses import PlainTextResponse

from scripts import fam_tend, fam_today
from scripts.lib import interactions, person, validate, vault

Circle = Literal["reference", "passive", "inner", "close", "orbit", "distant"]
Limit = Annotated[int, Field(ge=0)]


def create_server(*, token: str | None = None) -> FastMCP:
    auth = StaticTokenVerifier(tokens={token: {"client_id": "fam"}}) if token else None
    server = FastMCP(
        "fam",
        instructions=(
            "Personal CRM backed by Obsidian Markdown. Contact dates derive only from "
            "Logged contacts. Log contacts only from user reports or evidence of an actual "
            "interaction, never from mentions. Edit individual notes with Obsidian file tools. "
            "today repairs missing circles; tend creates notes through Templater."
        ),
        auth=auth,
        mask_error_details=False,
    )

    @server.tool(
        annotations={
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        }
    )
    def today(
        on_date: date | None = None,
        include_below_threshold: bool = False,
        circle: Circle | None = None,
        include_snoozed: bool = False,
        limit: Limit | None = None,
    ) -> list[dict[str, Any]]:
        """Rank who to contact. Missing circles are repaired to reference before scoring.

        on_date defaults to today's server-local date. include_below_threshold includes
        people before their alert threshold; inactive circles and muted reminders still
        stay out. include_snoozed retains real scores and marks snoozed people.
        """
        return fam_today.rows_as_dicts(
            fam_today.compute_rows(
                today=on_date or date.today(),
                include_below_threshold=include_below_threshold,
                circle=circle,
                include_snoozed=include_snoozed,
                limit=limit,
            )
        )

    @server.tool(name="validate", annotations={"readOnlyHint": True, "openWorldHint": False})
    def validate_vault() -> dict[str, Any]:
        """Validate circles, all person frontmatter, and logged contact bullets; no writes."""
        return asdict(validate.preflight(vault.get_vault_root()))

    @server.tool(
        annotations={
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        }
    )
    def tend(person_name: str | None = None, dry_run: bool = False) -> dict[str, Any]:
        """Ensure one person's note exists, or create unresolved @ links through Templater.

        dry_run previews names without writes. Does not infer contacts or update existing
        notes. Failed creations are returned in failed, including any partial successes.
        """
        return asdict(fam_tend.tend(person_name=person_name, dry_run=dry_run))

    @server.tool(annotations={"readOnlyHint": True, "openWorldHint": False})
    def list_people(circle: Circle | None = None) -> list[dict[str, Any]]:
        """List person names and exact vault-relative paths, including inactive circles."""
        root = vault.get_vault_root()
        result = []
        for path in person.discover(root):
            loaded = person.load(path)
            if circle is None or loaded.circle == circle:
                last = interactions.last_contacted(loaded)
                result.append(
                    {
                        "name": loaded.name,
                        "circle": loaded.circle,
                        "path": str(path.relative_to(root)),
                        "last_contacted": last.isoformat() if last else None,
                    }
                )
        return result

    @server.tool(annotations={"readOnlyHint": True, "openWorldHint": False})
    def read_person(path: str) -> dict[str, Any]:
        """Read one @ person note by exact vault-relative path from list_people or today."""
        root = vault.get_vault_root()
        relative = Path(path)
        target = root / relative
        if relative.is_absolute() or ".." in relative.parts or target not in person.discover(root):
            raise ToolError("path must identify a discovered person note inside the vault")
        loaded = person.load(target)
        last = interactions.last_contacted(loaded)
        return {
            "path": str(relative),
            "name": loaded.name,
            "circle": loaded.circle,
            "last_contacted": last.isoformat() if last else None,
            "content": vault.read_text(target),
        }

    @server.custom_route("/healthz", methods=["GET"])
    async def health(request: Request) -> PlainTextResponse:
        return PlainTextResponse("ok")

    return server


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="fam-mcp")
    parser.add_argument("--transport", choices=("stdio", "http"), default="stdio")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--token-file", default=os.environ.get("FAM_MCP_TOKEN_FILE"))
    args = parser.parse_args(argv)
    token = None
    if args.transport == "http":
        if not args.token_file:
            parser.error("HTTP transport requires --token-file or FAM_MCP_TOKEN_FILE")
        token = Path(args.token_file).read_text().strip()
        if not token:
            parser.error("MCP token file is empty")
    server = create_server(token=token)
    if args.transport == "http":
        server.run(transport="http", host=args.host, port=args.port)
    else:
        server.run(transport="stdio")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
