import { useEffect, useState } from "react";
import { Box, Button, MenuItem, TextField, Typography } from "@mui/material";
import { api } from "../api";
import { ErrorAlert, PageTitle, Panel } from "../ui";

type TableRow = { name: string; kind?: string | null };

export function SnowflakePage() {
  const [databases, setDatabases] = useState<string[]>([]);
  const [schemas, setSchemas] = useState<string[]>([]);
  const [tables, setTables] = useState<TableRow[]>([]);
  const [database, setDatabase] = useState("");
  const [schemaName, setSchemaName] = useState("");
  const [relation, setRelation] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [count, setCount] = useState<string | null>(null);
  const [truncated, setTruncated] = useState(false);

  useEffect(() => {
    api<{ databases: string[]; truncated: boolean }>("/api/snowflake/databases")
      .then((result) => {
        setDatabases(result.databases);
        setTruncated(result.truncated);
      })
      .catch((reason: Error) => setError(reason.message));
  }, []);

  useEffect(() => {
    let live = true;
    setSchemas([]);
    setSchemaName("");
    setTables([]);
    setRelation("");
    if (!database) return;
    api<{ schemas: string[]; truncated: boolean }>(`/api/snowflake/schemas?database=${encodeURIComponent(database)}`)
      .then((result) => {
        if (!live) return;
        setSchemas(result.schemas);
        setTruncated((current) => current || result.truncated);
      })
      .catch((reason: Error) => {
        if (live) setError(reason.message);
      });
    return () => {
      live = false;
    };
  }, [database]);

  useEffect(() => {
    let live = true;
    setTables([]);
    setRelation("");
    if (!database || !schemaName) return;
    const query = new URLSearchParams({ database, schema_name: schemaName });
    api<{ tables: TableRow[]; truncated: boolean }>(`/api/snowflake/tables?${query.toString()}`)
      .then((result) => {
        if (!live) return;
        setTables(result.tables);
        setTruncated((current) => current || result.truncated);
      })
      .catch((reason: Error) => {
        if (live) setError(reason.message);
      });
    return () => {
      live = false;
    };
  }, [database, schemaName]);

  async function runCount() {
    setCount(null);
    setError(null);
    try {
      const result = await api<{ row_count: number; target: string }>("/api/snowflake/count", {
        method: "POST",
        body: JSON.stringify({ database, schema_name: schemaName, relation }),
      });
      setCount(`${result.target}: ${result.row_count} rows`);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Count failed.");
    }
  }

  return (
    <Box>
      <PageTitle title="Snowflake" />
      <ErrorAlert message={error} />
      {truncated ? (
        <Typography color="text.secondary" sx={{ mb: 1 }}>
          Lists are capped at 100 rows.
        </Typography>
      ) : null}
      <Panel>
        <Box sx={{ display: "flex", flexWrap: "wrap", gap: 1 }}>
          <TextField select label="Database" value={database} onChange={(event) => setDatabase(event.target.value)} sx={{ minWidth: 220 }}>
            {databases.map((name) => (
              <MenuItem key={name} value={name}>
                {name}
              </MenuItem>
            ))}
          </TextField>
          <TextField select label="Schema" value={schemaName} onChange={(event) => setSchemaName(event.target.value)} sx={{ minWidth: 220 }}>
            {schemas.map((name) => (
              <MenuItem key={name} value={name}>
                {name}
              </MenuItem>
            ))}
          </TextField>
          <TextField select label="Table" value={relation} onChange={(event) => setRelation(event.target.value)} sx={{ minWidth: 220 }}>
            {tables.map((table) => (
              <MenuItem key={table.name} value={table.name}>
                {table.name}
              </MenuItem>
            ))}
          </TextField>
          <Button variant="contained" disabled={!relation} onClick={runCount} sx={{ alignSelf: "center" }}>
            Count rows
          </Button>
        </Box>
        {count ? <Typography sx={{ mt: 2 }}>{count}</Typography> : null}
      </Panel>
    </Box>
  );
}
