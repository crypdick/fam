"""Single fam command with optional MCP transport."""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import asdict
from datetime import date
from typing import Any

from scripts import fam_events, fam_tend, fam_today
from scripts.lib import config, people, person, validate, vault


def iso_date(value: str) -> date:
    try:
        parsed = date.fromisoformat(value)
        if parsed.isoformat() == value:
            return parsed
    except ValueError:
        pass
    raise argparse.ArgumentTypeError("expected YYYY-MM-DD date")


def nonnegative(value: str) -> int:
    try:
        result = int(value)
        if result >= 0:
            return result
    except ValueError:
        pass
    raise argparse.ArgumentTypeError("expected nonnegative integer")


def positive(value: str) -> int:
    result = nonnegative(value)
    if result == 0:
        raise argparse.ArgumentTypeError("expected positive integer")
    return result


def print_json(value: Any) -> None:
    print(json.dumps(value, indent=2, allow_nan=False))


def format_people(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return "No people match this list (or --limit is 0)."
    table = [["NAME", "CIRCLE", "LAST_CONTACTED", "LOCATION", "TAGS", "INTERACTION", "PATH"]]
    show_score = "score" in rows[0]
    if show_score:
        table[0].insert(0, "SCORE")
    for row in rows:
        table.append(
            [
                row["name"],
                row["circle"],
                row["last_contacted"] or "-",
                row["location"] or "-",
                ", ".join(row["relationship_tags"]) or "-",
                ", ".join(row["interaction_preferences"]) or "-",
                row["path"],
            ]
        )
        if show_score:
            value = row["score"]
            table[-1].insert(0, f"{value:.2f}" if isinstance(value, float) else str(value))
    widths = [max(len(cell) for cell in column) for column in zip(*table, strict=True)]
    return "\n".join(
        "  ".join(cell.ljust(width) for cell, width in zip(row, widths, strict=True)).rstrip()
        for row in table
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="fam")
    commands = parser.add_subparsers(dest="command", required=True)
    list_options = argparse.ArgumentParser(add_help=False)
    list_options.add_argument(
        "--on-date", type=iso_date, default=None, help="scoring date (--today or --sort score)"
    )
    list_options.add_argument(
        "--all", action="store_true", help="include below-threshold queue rows (requires --today)"
    )
    list_options.add_argument("--circle", choices=person.CIRCLES)
    list_options.add_argument("--limit", type=nonnegative)
    list_options.add_argument("--json", action="store_true")
    list_options.add_argument(
        "--include-snoozed",
        action="store_true",
        help="include snoozed queue rows (requires --today)",
    )
    list_options.add_argument("--location", help="case-insensitive location substring")
    list_options.add_argument("--tag", help="case-insensitive relationship tag membership")
    list_options.add_argument(
        "--interaction", help="case-insensitive interaction preference membership"
    )
    listing = commands.add_parser("list", parents=[list_options], help="list people (read-only)")
    listing.add_argument("--today", action="store_true", help="show ranked contact queue")
    listing.add_argument(
        "--sort",
        choices=("name", "score"),
        default=None,
        help="sort by name (default) or descending score",
    )
    today = commands.add_parser("today", parents=[list_options], help="alias for list --today")
    today.set_defaults(today=True)
    events = commands.add_parser("events", help="important event reminders (read-only)")
    events.add_argument("--on-date", type=iso_date)
    events.add_argument(
        "--days", type=nonnegative, default=0, help="look ahead for reminder windows"
    )
    events.add_argument("--include-snoozed", action="store_true")
    events.add_argument("--limit", type=nonnegative)
    events.add_argument("--json", action="store_true")
    check = commands.add_parser("validate", help="validate configuration and person notes")
    check.add_argument("--json", action="store_true")
    tend = commands.add_parser("tend", help="explicit bulk creation from unresolved @ links")
    tend.add_argument("--dry-run", action="store_true")
    persons = commands.add_parser("person", help="read and update person notes")
    actions = persons.add_subparsers(dest="action", required=True)
    show = actions.add_parser("show", help="read one person as JSON")
    show.add_argument("path")
    ensure = actions.add_parser("ensure", help="create one named person if missing")
    ensure.add_argument("name")
    ensure.add_argument("--dry-run", action="store_true")
    log = actions.add_parser("log-contact", help="log a reported or evidenced interaction")
    log.add_argument("path")
    log.add_argument("--date", type=iso_date, required=True)
    log.add_argument("--description", required=True)
    log.add_argument("--complete-action", action="store_true")
    update = actions.add_parser("update", help="set or clear fam fields")
    update.add_argument("path")
    update.add_argument("--circle", choices=person.CIRCLES)
    update.add_argument("--cadence-days-override", type=positive)
    update.add_argument("--snooze-until", type=iso_date)
    update.add_argument("--next-action-at", type=iso_date)
    update.add_argument("--periodic-contact-reminders", action=argparse.BooleanOptionalAction)
    update.add_argument("--contact-channels-ordered-preference", nargs="+")
    update.add_argument("--location")
    update.add_argument("--relationship-tags", nargs="+")
    update.add_argument("--interaction-preferences", nargs="+")
    update.add_argument("--important-events", type=json.loads, help="replace event list with JSON")
    update.add_argument("--clear", choices=people.OPTIONAL_FIELDS, action="append", default=[])
    mcp = commands.add_parser("mcp", help="serve optional MCP interface")
    mcp.add_argument("--transport", choices=("stdio", "http"), default="stdio")
    mcp.add_argument("--host", default="127.0.0.1")
    mcp.add_argument("--port", type=int, default=8000)
    mcp.add_argument("--token-file", default=os.environ.get("FAM_MCP_TOKEN_FILE"))
    args = parser.parse_args(argv)
    if args.command == "list":
        if args.today and args.sort == "name":
            parser.error("--today always sorts by score")
        if not args.today:
            if args.all or args.include_snoozed:
                parser.error("--all and --include-snoozed require --today")
            if args.on_date is not None and args.sort != "score":
                parser.error("--on-date requires --today or --sort score")
    try:
        if args.command in {"list", "today"} and args.today:
            fam_today.run(
                today=args.on_date or date.today(),
                json_out=args.json,
                include_below_threshold=args.all,
                circle=args.circle,
                include_snoozed=args.include_snoozed,
                limit=args.limit,
                location=args.location,
                relationship_tag=args.tag,
                interaction_preference=args.interaction,
            )
        elif args.command == "list":
            rows = people.list_people(
                args.circle,
                location=args.location,
                relationship_tag=args.tag,
                interaction_preference=args.interaction,
                limit=args.limit,
                sort_by=args.sort or "name",
                on_date=args.on_date,
            )
            if args.json:
                print_json(rows)
            else:
                print(format_people(rows))
        elif args.command == "events":
            rows = fam_events.upcoming(
                today=args.on_date or date.today(),
                days=args.days,
                include_snoozed=args.include_snoozed,
                limit=args.limit,
            )
            if args.json:
                print_json(rows)
            else:
                print(fam_events.format_events(rows))
        elif args.command == "validate":
            report = validate.preflight(vault.get_vault_root())
            if args.json:
                print_json(asdict(report))
            else:
                print("OK" if report.ok else "FAIL:\n  " + "\n  ".join(report.errors))
            return 0 if report.ok else 1
        elif args.command == "tend" or (args.command == "person" and args.action == "ensure"):
            result = fam_tend.tend(
                person_name=args.name if args.command == "person" else None,
                dry_run=args.dry_run,
            )
            print_json(asdict(result))
            return 1 if result.failed else 0
        elif args.command == "person":
            if args.action == "show":
                print_json(people.read_person(args.path))
            elif args.action == "log-contact":
                print_json(
                    people.log_contact(
                        args.path, args.date, args.description, complete_action=args.complete_action
                    )
                )
            elif args.action == "update":
                changes = {
                    field: value
                    for field in people.EDITABLE_FIELDS
                    if (value := getattr(args, field)) is not None
                }
                print_json(people.update_person(args.path, changes, args.clear))
        elif args.command == "mcp":
            # Ordinary CLI use does not import optional MCP dependencies.
            try:
                from scripts.fam_mcp import serve
            except ModuleNotFoundError as error:
                if error.name != "fastmcp":
                    raise
                raise ValueError("MCP dependencies missing; run uv sync --extra mcp") from error

            serve(
                transport=args.transport, host=args.host, port=args.port, token_file=args.token_file
            )
    except (
        config.ConfigError,
        person.PersonSchemaError,
        validate.ValidationError,
        vault.ObsidianCliError,
        OSError,
        ValueError,
    ) as error:
        print(str(error), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
