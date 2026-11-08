"""Prepare synchronized plugin versions for the GitHub Actions release job."""

import argparse
import json
import os
import re
import subprocess
import tomllib
from pathlib import Path


def _git(*args: str) -> str:
    environment = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}
    result = subprocess.run(  # noqa: S603 -- fixed Git command and validated commit SHAs.
        ["git", *args],  # noqa: S607 -- Git is a required development tool resolved through PATH.
        check=True,
        capture_output=True,
        text=True,
        env=environment,
    )
    return result.stdout.strip()


def _release_state(source: str) -> str:
    if _git("rev-parse", "HEAD") == source:
        return "new"
    parent = _git("rev-parse", "HEAD^")
    message = _git("log", "-1", "--format=%B")
    if (
        parent == source
        and message.startswith("Release ")
        and f"Source-Commit: {source}" in message.splitlines()
    ):
        return "retry"
    return "stale"


def _parts(value: object) -> tuple[int, int, int]:
    if (
        not isinstance(value, str)
        or (match := re.fullmatch(r"(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)", value)) is None
    ):
        raise ValueError(f"version must be major.minor.patch: {value!r}")
    return int(match[1]), int(match[2]), int(match[3])


def _project_version(content: str) -> str:
    version = tomllib.loads(content)["project"]["version"]
    parts = _parts(version)
    return ".".join(map(str, parts))


def _read_json(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError(f"{path} must contain a JSON object")
    return value


def _prepare_version(previous: str) -> str:
    # NOTE: docs/development.md documents pyproject.toml as the release source of truth.
    project_path = Path("pyproject.toml")
    project = project_path.read_text(encoding="utf-8")
    current = _project_version(project)
    baseline = _project_version(_git("show", f"{previous}:pyproject.toml"))
    current_parts, baseline_parts = _parts(current), _parts(baseline)
    if current_parts < baseline_parts:
        raise ValueError(f"version decreased from {baseline} to {current}")
    version = (
        current
        if current_parts > baseline_parts
        else f"{current_parts[0]}.{current_parts[1]}.{current_parts[2] + 1}"
    )
    project, count = re.subn(
        r'^version = "[^"]+"$', f'version = "{version}"', project, count=1, flags=re.M
    )
    if count != 1:
        raise ValueError('pyproject.toml must declare version = "major.minor.patch"')

    paths = [
        Path(".claude-plugin/plugin.json"),
        Path(".codex-plugin/plugin.json"),
        Path(".claude-plugin/marketplace.json"),
    ]
    manifests = [_read_json(path) for path in paths]
    if any(manifest.get("name") != "fam" for manifest in manifests[:2]):
        raise ValueError("plugin manifests must be named fam")
    plugins = manifests[2].get("plugins")
    if not isinstance(plugins, list):
        raise TypeError("marketplace must contain a plugins array")
    registrations = [
        item for item in plugins if isinstance(item, dict) and item.get("name") == "fam"
    ]
    if len(registrations) != 1:
        raise ValueError("marketplace must register fam exactly once")
    plugin = registrations[0]
    plugin["version"] = version
    for manifest in manifests[:2]:
        manifest["version"] = version

    project_path.write_text(project, encoding="utf-8")
    for path, manifest in zip(paths, manifests, strict=True):
        path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return version


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True)
    parser.add_argument("--previous", required=True, help="Branch HEAD before this push")
    args = parser.parse_args()
    for name in ("source", "previous"):
        if re.fullmatch(r"[0-9a-f]{40}", getattr(args, name)) is None:
            parser.error(f"{name} must be a full Git commit SHA")
    try:
        output_path = Path(os.environ["GITHUB_OUTPUT"])
        state = _release_state(args.source)
        version = (
            _prepare_version(args.previous)
            if state == "new"
            else _project_version(Path("pyproject.toml").read_text(encoding="utf-8"))
        )
        with output_path.open("a", encoding="utf-8") as output:
            output.write(f"state={state}\nversion={version}\n")
    except (KeyError, OSError, subprocess.CalledProcessError, TypeError, ValueError) as error:
        parser.error(str(error))


if __name__ == "__main__":
    main()
