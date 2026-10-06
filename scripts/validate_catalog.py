#!/usr/bin/env python3
"""Dependency-free consistency checks for the curated modding research index."""

from __future__ import annotations

import json
import re
import sys
from collections import Counter
from datetime import date
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
CATALOG_PATH = ROOT / "resources.json"
README_PATH = ROOT / "README.md"
COVERAGE_PATH = ROOT / "ECOSYSTEM_COVERAGE.md"

ROOT_KEYS = {"schema_version", "last_reviewed", "resources"}
RESOURCE_KEYS = {"id", "name", "url", "category", "summary", "tags"}
ID_PATTERN = re.compile(r"[a-z0-9][a-z0-9._-]*\Z")

# The finite checklist was explicitly closed at these dispositions. If the
# checklist itself changes, update this guard together with the audit document.
EXPECTED_CROSSWALK_ROWS = 18
EXPECTED_CROSSWALK_COUNTS = {
    "Covered": 6,
    "Partial": 12,
    "Open": 0,
    "Out of scope": 0,
}
STATUS_PATTERN = re.compile(r"\*\*(Covered|Partial|Open|Out of scope)(?:\s|\*)")

TEXT_FILES_TO_CHECK = (
    ".gitignore",
    "CONTRIBUTING.md",
    "ECOSYSTEM_COVERAGE.md",
    "README.md",
    "resources.json",
    ".github/workflows/validate.yml",
    "scripts/build_archive.py",
    "scripts/validate_catalog.py",
)


def validate() -> list[str]:
    errors: list[str] = []

    try:
        data = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return [f"cannot read valid JSON from {CATALOG_PATH.relative_to(ROOT)}: {exc}"]

    if not isinstance(data, dict):
        return ["catalog root must be a JSON object"]
    if set(data) != ROOT_KEYS:
        errors.append(
            f"catalog root keys must be {sorted(ROOT_KEYS)}; found {sorted(data)}"
        )
    if type(data.get("schema_version")) is not int or data.get("schema_version") != 1:
        errors.append("schema_version must be integer 1 (update the validator for a schema change)")
    reviewed = data.get("last_reviewed")
    if not isinstance(reviewed, str):
        errors.append("last_reviewed must be an ISO date string")
    else:
        try:
            date.fromisoformat(reviewed)
        except ValueError:
            errors.append(f"last_reviewed is not a valid ISO date: {reviewed!r}")

    resources = data.get("resources")
    if not isinstance(resources, list):
        errors.append("resources must be a JSON array")
        resources = []

    seen_ids: set[str] = set()
    seen_urls: set[str] = set()
    valid_urls: list[str] = []

    for index, resource in enumerate(resources):
        label = f"resources[{index}]"
        if not isinstance(resource, dict):
            errors.append(f"{label} must be an object")
            continue
        if set(resource) != RESOURCE_KEYS:
            errors.append(
                f"{label} keys must be {sorted(RESOURCE_KEYS)}; found {sorted(resource)}"
            )

        resource_id = resource.get("id")
        if not isinstance(resource_id, str) or not ID_PATTERN.fullmatch(resource_id):
            errors.append(f"{label}.id must be a lowercase slug; found {resource_id!r}")
        elif resource_id in seen_ids:
            errors.append(f"duplicate resource id: {resource_id}")
        else:
            seen_ids.add(resource_id)

        for field in ("name", "category", "summary"):
            value = resource.get(field)
            if not isinstance(value, str) or not value.strip():
                errors.append(f"{label}.{field} must be a non-empty string")

        url = resource.get("url")
        if not isinstance(url, str):
            errors.append(f"{label}.url must be a string")
        else:
            try:
                parsed = urlsplit(url)
            except ValueError as exc:
                errors.append(f"{label}.url is malformed: {url!r} ({exc})")
            else:
                if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
                    errors.append(f"{label}.url must be an HTTPS URL without embedded credentials: {url!r}")
            if url in seen_urls:
                errors.append(f"duplicate resource URL: {url}")
            else:
                seen_urls.add(url)
            valid_urls.append(url)

        tags = resource.get("tags")
        if not isinstance(tags, list) or not tags:
            errors.append(f"{label}.tags must be a non-empty array")
        elif any(not isinstance(tag, str) or not tag.strip() for tag in tags):
            errors.append(f"{label}.tags must contain only non-empty strings")
        elif len(tags) != len(set(tags)):
            errors.append(f"{label}.tags must not contain duplicates")

    try:
        readme = README_PATH.read_text(encoding="utf-8")
    except OSError as exc:
        errors.append(f"cannot read README.md: {exc}")
        readme = ""
    missing_urls = [url for url in valid_urls if url not in readme]
    for url in missing_urls:
        errors.append(f"README.md does not link to catalog URL: {url}")

    try:
        coverage = COVERAGE_PATH.read_text(encoding="utf-8")
    except OSError as exc:
        errors.append(f"cannot read ECOSYSTEM_COVERAGE.md: {exc}")
        coverage = ""

    snapshot_match = re.search(r"\*\*Catalog snapshot:\*\*\s+(\d+) resources", coverage)
    if snapshot_match and int(snapshot_match.group(1)) != len(resources):
        errors.append(
            f"coverage snapshot says {snapshot_match.group(1)} resources, "
            f"but resources.json contains {len(resources)}"
        )
    elif not snapshot_match:
        errors.append("could not find the Catalog snapshot count in ECOSYSTEM_COVERAGE.md")

    start_marker = "### Game and engine ecosystems"
    end_marker = "### Platform families and distribution ecosystems"
    if start_marker not in coverage or end_marker not in coverage:
        errors.append("could not locate the practical game/engine crosswalk section")
    else:
        section = coverage.split(start_marker, 1)[1].split(end_marker, 1)[0]
        counts: Counter[str] = Counter()
        for line in section.splitlines():
            if not line.startswith("|"):
                continue
            cells = line.split("|")
            if len(cells) < 3:
                continue
            status_cell = cells[2].strip()
            match = STATUS_PATTERN.match(status_cell)
            if match:
                counts[match.group(1)] += 1
        row_count = sum(counts.values())
        if row_count != EXPECTED_CROSSWALK_ROWS:
            errors.append(
                f"expected {EXPECTED_CROSSWALK_ROWS} game/engine crosswalk rows; found {row_count}"
            )
        actual = {key: counts.get(key, 0) for key in EXPECTED_CROSSWALK_COUNTS}
        if actual != EXPECTED_CROSSWALK_COUNTS:
            errors.append(
                f"game/engine crosswalk dispositions are {actual}; "
                f"expected {EXPECTED_CROSSWALK_COUNTS}"
            )

    for relative_path in TEXT_FILES_TO_CHECK:
        path = ROOT / relative_path
        if not path.is_file():
            errors.append(f"expected project file is missing: {relative_path}")
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            errors.append(f"cannot read {relative_path} as UTF-8 text: {exc}")
            continue
        if not text.endswith("\n"):
            errors.append(f"{relative_path} must end with a newline")
        for line_number, line in enumerate(text.splitlines(), start=1):
            if line.rstrip(" \t") != line:
                errors.append(f"{relative_path}:{line_number}: trailing whitespace")

    return errors


def main() -> int:
    errors = validate()
    if errors:
        print("Catalog validation failed:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1

    data = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    resources = data["resources"]
    categories = {resource["category"] for resource in resources}
    print(
        f"Catalog validation passed: {len(resources)} records, "
        f"{len(categories)} categories, unique IDs/URLs, README parity, "
        f"and {EXPECTED_CROSSWALK_ROWS} closed crosswalk rows "
        "(6 Covered / 12 Partial / 0 Open)."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
