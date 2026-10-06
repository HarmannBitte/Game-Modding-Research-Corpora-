# Contributing

Suggestions and corrections are welcome. This repository is a curated index, so contributions should keep the links useful, concise, and verifiable.

## Adding or updating a resource

1. Prefer the project's canonical upstream repository or official documentation URL.
2. Add one short, factual summary in `README.md` and the matching entry in `resources.json`.
3. Keep the JSON fields consistent with the existing catalog: `id`, `name`, `url`, `category`, `summary`, and `tags`.
4. Do not guess at project support, maintenance status, license, or compatibility. Link to upstream material for details and note uncertainty where needed; clearly label archived or otherwise inactive projects as historical, not current recommendations.
5. Treat game-version, loader, and AI-provider details as volatile. Add a review date when a status claim materially affects whether a resource is useful.
6. Do not add game binaries, dumps, firmware, keys, proprietary assets, credentials, or instructions for bypassing access controls.

## Checks

Run the dependency-free validator before opening a pull request:

```sh
python scripts/validate_catalog.py
git diff --check
```

The validator checks the catalog structure, unique IDs and URLs, required fields, README URL parity, text whitespace, catalog snapshot count, and the finite game/engine crosswalk dispositions. If intentionally changing the finite checklist or catalog schema version, update the validator's explicit guards and audit documentation in the same change.

Build and verify the standard project archive with:

```sh
python scripts/build_archive.py
```

By default, the ZIP is written next to the project directory; use `--output PATH` to choose another location. The builder fixes archive ordering and timestamps, then checks ZIP integrity and byte-for-byte parity with the included project files.

Keep the README and JSON catalog in sync. Summaries should be original descriptions, not copied blocks from project documentation.
