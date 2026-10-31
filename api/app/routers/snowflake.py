"""List databases, schemas, and tables, and count one relation."""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.snowflake_client import count_relation, list_databases, list_schemas, list_tables

router = APIRouter(prefix="/snowflake", tags=["snowflake"])


class CountIn(BaseModel):
    database: str
    schema_name: str = Field(alias="schema_name")
    relation: str

    model_config = {"populate_by_name": True}


@router.get("/databases")
def databases() -> dict:
    return list_databases()


@router.get("/schemas")
def schemas(database: str) -> dict:
    return list_schemas(database)


@router.get("/tables")
def tables(database: str, schema_name: str) -> dict:
    return list_tables(database, schema_name)


@router.post("/count")
def count(body: CountIn) -> dict:
    return count_relation(body.database, body.schema_name, body.relation)
