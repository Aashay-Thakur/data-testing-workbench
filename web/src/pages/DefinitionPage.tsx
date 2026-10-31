import { useEffect, useState } from "react";
import { Box, Button, Checkbox, FormControlLabel, MenuItem, TextField, Typography } from "@mui/material";
import { useNavigate } from "react-router-dom";
import { api } from "../api";
import type { Check, KindInfo, Run } from "../types";
import { ErrorAlert, PageTitle, Panel } from "../ui";

type Draft = {
  name: string;
  label: string;
  blocking: boolean;
  database: string;
  schema_name: string;
  relation: string;
  unique_id: string;
  column: string;
  columns: string;
  values: string;
  max_null_rate: string;
  max_age_seconds: string;
  min_rows: string;
  max_rows: string;
  min_value: string;
  max_value: string;
  min_mean: string;
  max_mean: string;
  parent_database: string;
  parent_schema: string;
  parent_relation: string;
  parent_column: string;
  left: string;
  factors: string;
  expected: string;
  sql: string;
};

const EMPTY: Draft = {
  name: "",
  label: "",
  blocking: false,
  database: "",
  schema_name: "",
  relation: "",
  unique_id: "",
  column: "",
  columns: "",
  values: "",
  max_null_rate: "",
  max_age_seconds: "",
  min_rows: "",
  max_rows: "",
  min_value: "",
  max_value: "",
  min_mean: "",
  max_mean: "",
  parent_database: "",
  parent_schema: "",
  parent_relation: "",
  parent_column: "",
  left: "",
  factors: "",
  expected: "",
  sql: "",
};

const NUMERIC = new Set([
  "min_rows",
  "max_rows",
  "max_null_rate",
  "max_age_seconds",
  "min_value",
  "max_value",
  "min_mean",
  "max_mean",
]);

const LABELS: Record<string, string> = {
  column: "Column",
  columns: "Columns, comma separated",
  values: "Accepted values, comma separated",
  max_null_rate: "Max null rate (0 to 1)",
  max_age_seconds: "Max age in seconds",
  min_rows: "Min rows",
  max_rows: "Max rows",
  min_value: "Min value",
  max_value: "Max value",
  min_mean: "Min mean",
  max_mean: "Max mean",
  parent_database: "Parent database",
  parent_schema: "Parent schema",
  parent_relation: "Parent relation",
  parent_column: "Parent column",
  left: "Left column (amount)",
  factors: "Factors multiplied, comma separated (qty, price)",
  sql: "SELECT that returns violating rows",
  unique_id: "Test unique id",
};

export function DefinitionPage({ origin, title }: { origin: "check" | "rule"; title: string }) {
  const [kinds, setKinds] = useState<KindInfo[]>([]);
  const [saved, setSaved] = useState<Check[]>([]);
  const [draft, setDraft] = useState<Draft>(EMPTY);
  const [kind, setKind] = useState("");
  const [error, setError] = useState<string | null>(null);
  const navigate = useNavigate();
  const base = origin === "rule" ? "/api/rules" : "/api/checks";

  async function refresh() {
    const [nextKinds, nextSaved] = await Promise.all([
      api<KindInfo[]>(origin === "rule" ? "/api/rules/templates" : "/api/checks/kinds"),
      api<Check[]>(base),
    ]);
    setKinds(nextKinds);
    setSaved(nextSaved);
    setKind((current) => current || nextKinds[0]?.kind || "");
  }

  useEffect(() => {
    refresh().catch((reason: Error) => setError(reason.message));
  }, [origin]);

  const selected = kinds.find((item) => item.kind === kind);

  function update<K extends keyof Draft>(field: K, value: Draft[K]) {
    setDraft((current) => ({ ...current, [field]: value }));
  }

  async function submit(andRun: boolean) {
    setError(null);
    try {
      const created = await api<Check>(base, {
        method: "POST",
        body: JSON.stringify(payload(kind, draft, selected)),
      });
      if (andRun) {
        const run = await api<Run>(`${base}/${created.id}/run`, { method: "POST" });
        navigate(`/runs/${run.id}`);
        return;
      }
      setDraft(EMPTY);
      await refresh();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Save failed.");
    }
  }

  async function runSaved(id: number) {
    setError(null);
    try {
      const run = await api<Run>(`${base}/${id}/run`, { method: "POST" });
      navigate(`/runs/${run.id}`);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Run failed.");
    }
  }

  return (
    <Box>
      <PageTitle title={title} />
      <ErrorAlert message={error} />
      <Box sx={{ display: "flex", flexWrap: "wrap", gap: 2 }}>
        <Box sx={{ flex: "1 1 420px" }}>
          <Panel title={origin === "rule" ? "Template" : "Check"}>
            <TextField select label="Kind" value={kind} onChange={(event) => setKind(event.target.value)} fullWidth>
              {kinds.map((item) => (
                <MenuItem key={item.kind} value={item.kind}>
                  {item.title}
                </MenuItem>
              ))}
            </TextField>
            {selected ? (
              <Typography sx={{ my: 1 }}>{selected.plain}</Typography>
            ) : null}
            <TextField label="Name" value={draft.name} onChange={(event) => update("name", event.target.value)} fullWidth />
            <TextField label="Plain-language label" value={draft.label} onChange={(event) => update("label", event.target.value)} fullWidth />
            <Typography color="text.secondary" sx={{ mt: 1 }}>
              Target a loaded model by unique id, or a database, schema, and relation.
            </Typography>
            <TextField label="Model unique id" value={draft.unique_id} onChange={(event) => update("unique_id", event.target.value)} fullWidth />
            <Box sx={{ display: "flex", gap: 1 }}>
              <TextField label="Database" value={draft.database} onChange={(event) => update("database", event.target.value)} />
              <TextField label="Schema" value={draft.schema_name} onChange={(event) => update("schema_name", event.target.value)} />
              <TextField label="Relation" value={draft.relation} onChange={(event) => update("relation", event.target.value)} />
            </Box>
            {selected?.kind === "schema" ? (
              <TextField
                label="Expected columns, one name or name:TYPE per line"
                value={draft.expected}
                onChange={(event) => update("expected", event.target.value)}
                fullWidth
                multiline
                minRows={3}
              />
            ) : null}
            {selected?.kind === "custom_sql" ? (
              <TextField
                label={LABELS.sql}
                value={draft.sql}
                onChange={(event) => update("sql", event.target.value)}
                fullWidth
                multiline
                minRows={4}
              />
            ) : null}
            {(selected?.fields ?? [])
              .filter((field) => field !== "sql" && field !== "unique_id" && !(selected?.kind === "schema" && field === "columns"))
              .map((field) => (
                <TextField
                  key={field}
                  label={LABELS[field] || field}
                  value={textValue(draft, field)}
                  onChange={(event) => update(field as keyof Draft, event.target.value)}
                  fullWidth
                />
              ))}
            <FormControlLabel
              control={<Checkbox checked={draft.blocking} onChange={(event) => update("blocking", event.target.checked)} />}
              label="Blocking"
            />
            <Box sx={{ display: "flex", gap: 1, mt: 1 }}>
              <Button variant="outlined" onClick={() => void submit(false)}>
                Save
              </Button>
              <Button variant="contained" onClick={() => void submit(true)}>
                Save and run
              </Button>
            </Box>
          </Panel>
        </Box>
        <Box sx={{ flex: "1 1 320px" }}>
          <Panel title="Saved">
            {saved.length === 0 ? <Typography color="text.secondary">None yet.</Typography> : null}
            {saved.map((item) => (
              <Box key={item.id} sx={{ py: 1, borderTop: "1px solid #d9d6cf" }}>
                <Typography>{item.label}</Typography>
                <Typography color="text.secondary">
                  {item.kind}
                  {item.blocking ? " · blocking" : ""}
                </Typography>
                <Button sx={{ mt: 0.5 }} variant="outlined" onClick={() => void runSaved(item.id)}>
                  Run
                </Button>
              </Box>
            ))}
          </Panel>
        </Box>
      </Box>
    </Box>
  );
}

function textValue(draft: Draft, field: string): string {
  const value = draft[field as keyof Draft];
  return typeof value === "string" ? value : "";
}

function payload(kind: string, draft: Draft, selected: KindInfo | undefined) {
  const params: Record<string, unknown> = {};
  const fields = selected?.fields ?? [];
  for (const field of fields) {
    if (field === "unique_id") {
      params.unique_id = draft.unique_id.trim();
      continue;
    }
    if (kind === "schema" && field === "columns") {
      params.columns = draft.expected
        .split("\n")
        .map((line) => line.trim())
        .filter(Boolean)
        .map((line) => {
          const [name, type] = line.split(":").map((part) => part.trim());
          return type ? { name, type } : { name };
        });
      continue;
    }
    if (field === "sql") {
      params.sql = draft.sql;
      continue;
    }
    if (field === "columns" || field === "factors" || field === "values") {
      params[field] = draft[field]
        .split(",")
        .map((part) => part.trim())
        .filter(Boolean);
      continue;
    }
    const raw = textValue(draft, field);
    if (NUMERIC.has(field)) {
      if (raw !== "") params[field] = Number(raw);
      continue;
    }
    if (raw !== "") params[field] = raw;
  }
  return {
    name: draft.name.trim() || null,
    kind,
    label: draft.label.trim() || null,
    blocking: draft.blocking,
    target: {
      database: draft.database.trim() || null,
      schema_name: draft.schema_name.trim() || null,
      relation: draft.relation.trim() || null,
      unique_id: draft.unique_id.trim() || null,
    },
    params,
  };
}

export function ChecksPage() {
  return <DefinitionPage origin="check" title="Quick checks" />;
}

export function RulesPage() {
  return <DefinitionPage origin="rule" title="Business rules" />;
}
