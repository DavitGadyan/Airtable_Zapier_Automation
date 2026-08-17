#!/usr/bin/env python3
"""Create the Airtable base from app/airtable/schema.py.

Idempotent: re-running after a schema change adds only what is missing, which
is the intended way to apply one.

    python scripts/provision_airtable.py            # apply
    python scripts/provision_airtable.py --dry-run  # show the plan
    python scripts/provision_airtable.py --emit-doc # write the manual guide

If the token cannot write schema (Airtable gates this by plan and by token
scope), the script does not fail the install -- it writes a manual setup
document instead, so somebody can build the base by hand from the same source
of truth.
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

# Allow `python scripts/provision_airtable.py` from the backend directory.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.airtable.provision import (  # noqa: E402
    AirtableProvisioner,
    SchemaPermissionError,
)
from app.airtable.schema import TABLES  # noqa: E402
from app.config import get_settings  # noqa: E402

DOC_PATH = Path(__file__).resolve().parents[2] / "docs" / "airtable-schema.md"


def render_manual_doc() -> str:
    lines = [
        "# Airtable base schema",
        "",
        "Generated from `backend/app/airtable/schema.py` -- the source of truth.",
        "Regenerate with `python scripts/provision_airtable.py --emit-doc`.",
        "",
        "Build these by hand only if the API token cannot write schema. Create",
        "all tables and their plain fields first, then add the link fields at",
        "the end -- Airtable will not accept a link to a table that does not",
        "exist yet.",
        "",
    ]
    for table in TABLES:
        lines += [f"## {table.name}", "", table.description, ""]
        lines += ["| Field | Type | Notes |", "|---|---|---|"]
        for field in table.fields:
            note = field.description or ""
            if field.type == "singleSelect" and field.options:
                choices = ", ".join(c["name"] for c in field.options["choices"])
                note = (note + " " if note else "") + f"Options: {choices}"
            lines.append(f"| {field.name} | `{field.type}` | {note} |")
        for link in table.links:
            note = link.description or f"Links to **{link.to_table}**."
            lines.append(f"| {link.name} | `link` | {note} |")
        lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--emit-doc",
        action="store_true",
        help="write docs/airtable-schema.md and exit",
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)-7s %(message)s")

    if args.emit_doc:
        DOC_PATH.parent.mkdir(parents=True, exist_ok=True)
        DOC_PATH.write_text(render_manual_doc())
        print(f"wrote {DOC_PATH}")
        return 0

    if args.dry_run:
        for table in TABLES:
            print(f"{table.name}: {len(table.fields)} fields, {len(table.links)} links")
        print(f"\n{len(TABLES)} tables total. No changes made.")
        return 0

    settings = get_settings()
    if not settings.airtable_api_key or not settings.airtable_base_id:
        print(
            "AIRTABLE_API_KEY and AIRTABLE_BASE_ID must be set "
            "(copy .env.example to backend/.env).",
            file=sys.stderr,
        )
        return 2

    try:
        with AirtableProvisioner(
            settings.airtable_api_key, settings.airtable_base_id
        ) as provisioner:
            report = provisioner.provision()
    except SchemaPermissionError as exc:
        DOC_PATH.parent.mkdir(parents=True, exist_ok=True)
        DOC_PATH.write_text(render_manual_doc())
        print(f"\n{exc}\n", file=sys.stderr)
        print(f"Wrote a manual setup guide to {DOC_PATH} instead.", file=sys.stderr)
        return 3

    print(report.summary())
    for name in report.created_tables:
        print(f"  + table  {name}")
    for name in report.created_fields:
        print(f"  + field  {name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
