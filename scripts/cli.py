"""Single fam command with optional MCP transport."""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import asdict
from datetime import date
from typing import Any

from scripts import fam_tend, fam_today
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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="fam")
    commands = parser.add_subparsers(dest="command", required=True)
    today = commands.add_parser("today", help="show ranked contact queue (read-only)")
    today.add_argument("--on-date", type=iso_date, default=None)
    today.add_argument("--all", action="store_true", help="include below-threshold rows")
    today.add_argument("--circle", choices=person.CIRCLES)
    today.add_argument("--limit", type=nonnegative)
    today.add_argument("--json", action="store_true")
    today.add_argument("--include-snoozed", action="store_true")
    today.add_argument("--location", help="case-insensitive location substring")
    today.add_argument("--tag", help="case-insensitive relationship tag membership")
    today.add_argument("--interaction", help="case-insensitive interaction preference membership")
    check = commands.add_parser("validate", help="validate configuration and person notes")
    check.add_argument("--json", action="store_true")
    tend = commands.add_parser("tend", help="explicit bulk creation from unresolved @ links")
    tend.add_argument("--scan", action="store_true", required=True)
    tend.add_argument("--dry-run", action="store_true")
    persons = commands.add_parser("person", help="read and update person notes")
    actions = persons.add_subparsers(dest="action", required=True)
    listing = actions.add_parser("list", help="list person paths and contact dates as JSON")
    listing.add_argument("--circle", choices=person.CIRCLES)
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
    update.add_argument("--clear", choices=people.OPTIONAL_FIELDS, action="append", default=[])
    mcp = commands.add_parser("mcp", help="serve optional MCP interface")
    mcp.add_argument("--transport", choices=("stdio", "http"), default="stdio")
    mcp.add_argument("--host", default="127.0.0.1")
    mcp.add_argument("--port", type=int, default=8000)
    mcp.add_argument("--token-file", default=os.environ.get("FAM_MCP_TOKEN_FILE"))
    args = parser.parse_args(argv)
    try:
        if args.command == "today":
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
        elif args.command == "validate":
            report = validate.preflight(vault.get_vault_root())
            if args.json:
                print_json(asdict(report))
            else:
                print("OK" if report.ok else "FAIL:\n  " + "\n  ".join(report.errors))
            return 0 if report.ok else 1
        elif args.command == "tend" or (args.command == "person" and args.action == "ensure"):
            result = fam_tend.tend(
                scan=args.command == "tend",
                person_name=args.name if args.command == "person" else None,
                dry_run=args.dry_run,
            )
            print_json(asdict(result))
            return 1 if result.failed else 0
        elif args.command == "person":
            if args.action == "list":
                print_json(people.list_people(args.circle))
            elif args.action == "show":
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
