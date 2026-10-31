"""SQL guard tests. They do not connect to Snowflake."""

import pytest

from app.errors import UserError
from app.identifiers import quote_ident, quote_literal, quote_relation
from app.sql_guard import SqlRejected, guard_sql
from app.sql_templates import (
    accepted_values_sql,
    duplicate_keys_sql,
    exists_sql,
    expression_sql,
    failing_rows_sql,
    freshness_sql,
    min_max_mean_sql,
    null_rate_sql,
    referential_sql,
    row_count_sql,
    schema_sql,
)


def test_reject_non_select():
    rejected = [
        "INSERT INTO t VALUES (1)",
        "UPDATE t SET a = 1",
        "DELETE FROM t",
        "MERGE INTO t USING s ON t.id = s.id WHEN MATCHED THEN UPDATE SET a = 1",
        "DROP TABLE t",
        "CREATE TABLE t (a int)",
        "COPY INTO t FROM @stage",
        "TRUNCATE TABLE t",
        "ALTER TABLE t DROP COLUMN a",
        "GRANT SELECT ON t TO ROLE r",
        "SELECT 1; DROP TABLE t",
        "SELECT 1; SELECT 2",
    ]
    for sql in rejected:
        with pytest.raises(SqlRejected):
            guard_sql(sql)


def test_block_unbounded_select_star():
    with pytest.raises(SqlRejected, match="SELECT \\*"):
        guard_sql("SELECT * FROM t")
    with pytest.raises(SqlRejected, match="100"):
        guard_sql("SELECT * FROM t LIMIT 101")
    with pytest.raises(SqlRejected):
        guard_sql("SELECT t.* FROM t")


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT 1",
        "SELECT COUNT(*) AS row_count FROM t",
        "SELECT * FROM t LIMIT 100",
        "SELECT * FROM t LIMIT 1",
        "SELECT t.* FROM t LIMIT 10",
        "SHOW DATABASES",
        "SHOW SCHEMAS IN DATABASE FOO",
        "DESCRIBE TABLE foo",
        "DESC TABLE foo",
        "SELECT column_name, data_type FROM db.information_schema.columns WHERE table_name = 'T' LIMIT 100",
        "WITH c AS (SELECT a FROM t) SELECT a FROM c LIMIT 10",
        "SELECT * FROM (SELECT * FROM t) s LIMIT 100",
        "SELECT COUNT(*) AS failing_rows FROM (SELECT * FROM t) AS _failing_rows",
    ],
)
def test_allow_single_reads(sql: str):
    assert guard_sql(sql)


def test_templates_pass_the_guard():
    relation = quote_relation("ANALYTICS", "DBT", "ORDERS")
    parent = quote_relation("ANALYTICS", "DBT", "CUSTOMERS")
    column = quote_ident("ORDER_ID")
    statements = [
        *row_count_sql(relation),
        *freshness_sql(relation, quote_ident("UPDATED_AT")),
        *null_rate_sql(relation, column),
        *duplicate_keys_sql(relation, [column, quote_ident("SKU")]),
        *accepted_values_sql(relation, quote_ident("STATUS"), [quote_literal("open"), quote_literal("closed")]),
        *referential_sql(relation, parent, column, quote_ident("ID")),
        *min_max_mean_sql(relation, quote_ident("AMOUNT")),
        *schema_sql(quote_ident("ANALYTICS"), quote_literal("DBT"), quote_literal("ORDERS")),
        exists_sql(quote_ident("ANALYTICS"), quote_literal("DBT"), quote_literal("ORDERS")),
        *expression_sql(relation, quote_ident("AMOUNT"), [quote_ident("QTY"), quote_ident("PRICE")]),
    ]
    count_sql, sample_sql = failing_rows_sql("select * from orders where amount is null")
    statements.extend([count_sql, sample_sql])
    for sql in statements:
        guard_sql(sql)


def test_dbt_run_build_and_test_are_refused():
    from pathlib import Path

    from app.dbt_ops import run_dbt

    for command in ("run", "build", "test"):
        with pytest.raises(UserError, match="dbt parse and dbt compile"):
            run_dbt(command, Path("."), Path("."))
