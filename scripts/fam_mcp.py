"""Thin MCP adapter over fam's shared operations."""

from __future__ import annotations

from dataclasses import asdict
from datetime import date
from pathlib import Path
from typing import Annotated, Any, Literal

from fastmcp import FastMCP
from fastmcp.server.auth.providers.jwt import StaticTokenVerifier
from pydantic import Field
from starlette.requests import Request
from starlette.responses import PlainTextResponse

from scripts import fam_tend, fam_today
from scripts.lib import people, validate, vault

Circle = Literal["reference", "passive", "inner", "close", "orbit", "distant"]
OptionalField = Literal[
    "cadence_days_override",
    "snooze_until",
    "next_action_at",
    "periodic_contact_reminders",
    "contact_channels_ordered_preference",
    "location",
    "relationship_tags",
    "interaction_preferences",
]
Limit = Annotated[int, Field(ge=0)]
Cadence = Annotated[int, Field(gt=0)]


def create_server(*, token: str | None = None) -> FastMCP:
    auth = StaticTokenVerifier(tokens={token: {"client_id": "fam"}}) if token else None
    server = FastMCP(
        "fam",
        instructions=(
            "Personal CRM backed by Obsidian Markdown. Contact dates derive only from "
            "Logged contacts. Log contacts only from user reports or evidence of an actual "
            "interaction, never from mentions. Resolve identity and explicit contact date "
            "before logging. Use exact paths from list_people or today for person operations. "
            "Use update_person for fam fields; file tools for free-form relationship context. "
            "today is read-only; missing circles require an explicit update_person."
        ),
        auth=auth,
        mask_error_details=False,
    )
    read_only = {"readOnlyHint": True, "openWorldHint": False}
    mutating = {
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    }

    @server.tool(annotations=read_only)
    def today(
        on_date: date | None = None,
        include_below_threshold: bool = False,
        circle: Circle | None = None,
        include_snoozed: bool = False,
        limit: Limit | None = None,
        location: str | None = None,
        relationship_tag: str | None = None,
        interaction_preference: str | None = None,
    ) -> list[dict[str, Any]]:
        """Rank who to contact without writes. on_date defaults to server-local date.

        Inactive circles and muted reminders without action dates stay out even with
        include_below_threshold. include_snoozed retains real scores and marks snoozes.
        Location matches a casefolded substring; tag and mode match whole list entries.
        Metadata filters combine before limit and never bypass queue exclusions.
        If nobody meets their alert threshold, returns the highest-ranked eligible person.
        """
        return fam_today.rows_as_dicts(
            fam_today.compute_rows(
                today=on_date or date.today(),
                include_below_threshold=include_below_threshold,
                circle=circle,
                include_snoozed=include_snoozed,
                limit=limit,
                location=location,
                relationship_tag=relationship_tag,
                interaction_preference=interaction_preference,
            )
        )

    @server.tool(name="validate", annotations=read_only)
    def validate_vault() -> dict[str, Any]:
        """Validate configuration, all person frontmatter and contact bullets; no writes."""
        return asdict(validate.preflight(vault.get_vault_root()))

    @server.tool(annotations=mutating)
    def tend(scan: Literal[True], dry_run: bool = False) -> dict[str, Any]:
        """Explicit bulk creation from unresolved @ links; scan must be true.

        Preview with dry_run first. Does not infer contacts or edit existing notes.
        Inspect failed for partial creation failures.
        """
        return asdict(fam_tend.tend(scan=scan, dry_run=dry_run))

    @server.tool(annotations=mutating)
    def ensure_person(person_name: str, dry_run: bool = False) -> dict[str, Any]:
        """Create one named person through Templater if missing; never scan mentions.

        dry_run previews creation. Inspect failed even when other fields indicate success.
        """
        return asdict(fam_tend.tend(person_name=person_name, dry_run=dry_run))

    @server.tool(annotations=read_only)
    def list_people(circle: Circle | None = None) -> list[dict[str, Any]]:
        """List names, contact dates and exact paths, including inactive circles."""
        return people.list_people(circle)

    @server.tool(annotations=read_only)
    def read_person(path: str) -> dict[str, Any]:
        """Read original Markdown and contact date for an exact discovered person path."""
        return people.read_person(path)

    @server.tool(annotations=mutating)
    def log_contact(
        path: str, on_date: date, description: str, complete_action: bool = False
    ) -> dict[str, Any]:
        """Log one evidenced interaction with explicit date and single-line description.

        Exact date/description retries do not duplicate bullets. complete_action explicitly
        clears next_action_at; otherwise it stays unchanged. Returns added and person summary.
        """
        return people.log_contact(path, on_date, description, complete_action=complete_action)

    @server.tool(annotations={**mutating, "destructiveHint": True})
    def update_person(
        path: str,
        circle: Circle | None = None,
        cadence_days_override: Cadence | None = None,
        snooze_until: date | None = None,
        next_action_at: date | None = None,
        periodic_contact_reminders: bool | None = None,
        contact_channels_ordered_preference: list[str] | None = None,
        location: str | None = None,
        relationship_tags: list[str] | None = None,
        interaction_preferences: list[str] | None = None,
        clear: list[OptionalField] | None = None,
    ) -> dict[str, Any]:
        """Set fam fields, or remove optional fields named in clear. Other content survives.

        Omitted/null parameters leave fields unchanged. Set and clear cannot overlap.
        Circle changes preserve cadence override. Explicit circle can repair a missing one.
        """
        changes = {
            "circle": circle,
            "cadence_days_override": cadence_days_override,
            "snooze_until": snooze_until,
            "next_action_at": next_action_at,
            "periodic_contact_reminders": periodic_contact_reminders,
            "contact_channels_ordered_preference": contact_channels_ordered_preference,
            "location": location,
            "relationship_tags": relationship_tags,
            "interaction_preferences": interaction_preferences,
        }
        return people.update_person(
            path, {k: v for k, v in changes.items() if v is not None}, clear
        )

    @server.custom_route("/healthz", methods=["GET"])
    async def health(request: Request) -> PlainTextResponse:
        return PlainTextResponse("ok")

    return server


def serve(
    *, transport: Literal["stdio", "http"], host: str, port: int, token_file: str | None
) -> None:
    token = None
    if transport == "http":
        if not token_file:
            raise ValueError("HTTP transport requires --token-file or FAM_MCP_TOKEN_FILE")
        token = Path(token_file).read_text().strip()
        if not token:
            raise ValueError("MCP token file is empty")
    server = create_server(token=token)
    if transport == "http":
        server.run(transport="http", host=host, port=port)
    else:
        server.run(transport="stdio")
