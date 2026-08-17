"""Create the base from app/airtable/schema.py via the Airtable Meta API.

Idempotent by construction: existing tables are left alone and only missing
fields are added, so re-running after a schema change is safe and is the
intended way to apply one.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field as dc_field

import httpx

from app.airtable.schema import TABLES, Table

logger = logging.getLogger(__name__)

META_BASE_URL = "https://api.airtable.com/v0/meta/bases"


class SchemaPermissionError(RuntimeError):
    """The token cannot write schema.

    Not fatal: Airtable's Team plan and above expose schema writes, but plenty
    of bases sit on a plan or a token that does not. The caller falls back to
    emitting docs/airtable-schema.md for manual setup rather than failing the
    whole install.
    """


@dataclass
class ProvisionReport:
    created_tables: list[str] = dc_field(default_factory=list)
    skipped_tables: list[str] = dc_field(default_factory=list)
    created_fields: list[str] = dc_field(default_factory=list)

    def summary(self) -> str:
        return (
            f"{len(self.created_tables)} table(s) created, "
            f"{len(self.skipped_tables)} already present, "
            f"{len(self.created_fields)} field(s) added"
        )


class AirtableProvisioner:
    def __init__(self, api_key: str, base_id: str, *, timeout: float = 30.0) -> None:
        self._base_id = base_id
        self._client = httpx.Client(
            base_url=f"{META_BASE_URL}/{base_id}",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            timeout=timeout,
        )

    def __enter__(self) -> "AirtableProvisioner":
        return self

    def __exit__(self, *exc_info: object) -> None:
        self._client.close()

    # --- low level ------------------------------------------------------

    def _raise_for_status(self, response: httpx.Response, what: str) -> None:
        if response.status_code in (401, 403):
            raise SchemaPermissionError(
                f"{what} refused ({response.status_code}). The token needs the "
                "schema.bases:write scope and the base must be on a plan that "
                "allows programmatic schema changes."
            )
        if response.status_code >= 400:
            raise RuntimeError(f"{what} failed [{response.status_code}]: {response.text}")

    def fetch_schema(self) -> dict[str, dict]:
        """name -> {id, fields: {name -> id}} for what already exists."""
        response = self._client.get("/tables")
        self._raise_for_status(response, "reading base schema")
        return {
            table["name"]: {
                "id": table["id"],
                "fields": {f["name"]: f["id"] for f in table.get("fields", [])},
            }
            for table in response.json().get("tables", [])
        }

    def create_table(self, table: Table) -> str:
        payload = {
            "name": table.name,
            "description": table.description,
            "fields": [f.to_payload() for f in table.fields],
        }
        response = self._client.post("/tables", json=payload)
        self._raise_for_status(response, f"creating table {table.name!r}")
        return response.json()["id"]

    def create_field(self, table_id: str, payload: dict) -> None:
        response = self._client.post(f"/tables/{table_id}/fields", json=payload)
        self._raise_for_status(
            response, f"creating field {payload.get('name')!r}"
        )

    # --- orchestration --------------------------------------------------

    def provision(self) -> ProvisionReport:
        report = ProvisionReport()
        existing = self.fetch_schema()

        # Pass 1 -- tables and their scalar fields.
        for table in TABLES:
            if table.name in existing:
                report.skipped_tables.append(table.name)
                table_id = existing[table.name]["id"]
                present = existing[table.name]["fields"]
                for fld in table.fields:
                    if fld.name not in present:
                        self.create_field(table_id, fld.to_payload())
                        report.created_fields.append(f"{table.name}.{fld.name}")
                        logger.info("added field %s.%s", table.name, fld.name)
                continue

            table_id = self.create_table(table)
            report.created_tables.append(table.name)
            existing[table.name] = {
                "id": table_id,
                "fields": {f.name: "" for f in table.fields},
            }
            logger.info("created table %s", table.name)

        # Pass 2 -- links, now that every target table exists. This is also
        # what lets Bids and Purchase Orders reference each other.
        for table in TABLES:
            if not table.links:
                continue
            table_id = existing[table.name]["id"]
            present = existing[table.name]["fields"]
            for link in table.links:
                if link.name in present:
                    continue
                target = existing.get(link.to_table)
                if target is None:
                    logger.warning(
                        "link %s.%s targets unknown table %s; skipping",
                        table.name,
                        link.name,
                        link.to_table,
                    )
                    continue
                payload = {
                    "name": link.name,
                    "type": "multipleRecordLinks",
                    "options": {
                        "linkedTableId": target["id"],
                        "prefersSingleRecordLink": link.prefers_single,
                    },
                }
                if link.description:
                    payload["description"] = link.description
                self.create_field(table_id, payload)
                report.created_fields.append(f"{table.name}.{link.name}")
                logger.info("linked %s.%s -> %s", table.name, link.name, link.to_table)

        return report
