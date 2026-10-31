import { useState } from "react";
import { Box, Button, Tab, Tabs, TextField, Typography } from "@mui/material";
import { api } from "../api";
import { DataTable, ErrorAlert, Mono, PageTitle, Panel } from "../ui";

type Change = {
  unique_id: string;
  name?: string | null;
  change: string;
  downstream: string[];
};

type CompileResult = {
  added: Change[];
  removed: Change[];
  changed: Change[];
  downstream: string[];
  git_sha?: string | null;
  note?: string;
};

type EnvResult = {
  left_exists: boolean;
  right_exists: boolean;
  skipped?: string;
  left_error?: string | null;
  right_error?: string | null;
  schema?: {
    only_left: string[];
    only_right: string[];
    type_mismatches: { column: string; left_type: string; right_type: string }[];
  };
  row_count?: { left: number | null; right: number | null };
  nulls?: Record<string, unknown>[];
  aggregates?: Record<string, unknown>[];
  keys?: {
    skipped?: boolean;
    gap?: string;
    match_rate?: number | null;
    match_rate_definition?: string;
    left_keys?: number | null;
    right_keys?: number | null;
    matched?: number | null;
    mismatch_sample?: Record<string, unknown>[];
  };
};

type FileResult = {
  source: string | null;
  raw_diff: string;
  compiled_diff: string;
  git_diff: string | null;
  git_sha?: string | null;
  gaps: string[];
};

export function ComparePage() {
  const [tab, setTab] = useState(0);
  return (
    <Box>
      <PageTitle title="Compare" />
      <Tabs value={tab} onChange={(_event, value) => setTab(value)} sx={{ mb: 2 }}>
        <Tab label="Change" />
        <Tab label="Environments" />
        <Tab label="Files" />
      </Tabs>
      {tab === 0 ? <ChangeTab /> : null}
      {tab === 1 ? <EnvironmentTab /> : null}
      {tab === 2 ? <FileTab /> : null}
    </Box>
  );
}

function ChangeTab() {
  const [branch, setBranch] = useState("");
  const [modelName, setModelName] = useState("");
  const [modelPath, setModelPath] = useState("");
  const [sql, setSql] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<CompileResult | null>(null);
  const [busy, setBusy] = useState(false);

  async function compile() {
    setBusy(true);
    setError(null);
    try {
      const payload = await api<CompileResult>("/api/compare/compile", {
        method: "POST",
        body: JSON.stringify({
          branch: branch.trim() || null,
          sql: sql.trim() || null,
          model_name: modelName.trim() || null,
          model_path: modelPath.trim() || null,
        }),
      });
      setResult(payload);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Compile failed.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <Box>
      <ErrorAlert message={error} />
      <Panel title="dbt compile">
        <Typography color="text.secondary" sx={{ mb: 1 }}>
          Compiles a read-only branch or pasted SQL with the query role. This does not build the model.
        </Typography>
        <TextField label="Branch" value={branch} onChange={(event) => setBranch(event.target.value)} fullWidth />
        <TextField label="Model name" value={modelName} onChange={(event) => setModelName(event.target.value)} fullWidth />
        <TextField label="Model path" value={modelPath} onChange={(event) => setModelPath(event.target.value)} fullWidth />
        <TextField label="Pasted SQL" value={sql} onChange={(event) => setSql(event.target.value)} fullWidth multiline minRows={4} />
        <Button variant="contained" disabled={busy} onClick={() => void compile()}>
          {busy ? "Compiling…" : "Compile and diff"}
        </Button>
      </Panel>
      {result ? (
        <>
          <Typography sx={{ mb: 1 }}>{result.note}</Typography>
          {result.git_sha ? <Typography sx={{ mb: 1 }}>Git sha {result.git_sha}</Typography> : null}
          <ChangeList title="Added" rows={result.added} />
          <ChangeList title="Removed" rows={result.removed} />
          <ChangeList title="Changed" rows={result.changed} />
          <Panel title="Downstream">
            {result.downstream.length === 0 ? "None." : result.downstream.map((id) => <div key={id}><Mono>{id}</Mono></div>)}
          </Panel>
        </>
      ) : null}
    </Box>
  );
}

function ChangeList({ title, rows }: { title: string; rows: Change[] }) {
  return (
    <Panel title={title}>
      {rows.length === 0 ? "None." : null}
      {rows.map((row) => (
        <Box key={row.unique_id} sx={{ py: 0.5, borderTop: "1px solid #d9d6cf" }}>
          <Mono>{row.unique_id}</Mono>
          <Typography color="text.secondary">
            downstream {row.downstream.length ? row.downstream.join(", ") : "none"}
          </Typography>
        </Box>
      ))}
    </Panel>
  );
}

function EnvironmentTab() {
  const [relation, setRelation] = useState("");
  const [leftDb, setLeftDb] = useState("");
  const [leftSchema, setLeftSchema] = useState("");
  const [rightDb, setRightDb] = useState("");
  const [rightSchema, setRightSchema] = useState("");
  const [keys, setKeys] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<EnvResult | null>(null);

  async function compare() {
    setError(null);
    try {
      const payload = await api<EnvResult>("/api/compare/environments", {
        method: "POST",
        body: JSON.stringify({
          relation: relation.trim(),
          left: { database: leftDb.trim(), schema_name: leftSchema.trim() },
          right: { database: rightDb.trim(), schema_name: rightSchema.trim() },
          key_columns: keys.split(",").map((part) => part.trim()).filter(Boolean),
        }),
      });
      setResult(payload);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Compare failed.");
    }
  }

  return (
    <Box>
      <ErrorAlert message={error} />
      <Panel title="Same relation, two databases">
        <TextField label="Relation" value={relation} onChange={(event) => setRelation(event.target.value)} fullWidth />
        <Box sx={{ display: "flex", gap: 1 }}>
          <TextField label="Left database" value={leftDb} onChange={(event) => setLeftDb(event.target.value)} />
          <TextField label="Left schema" value={leftSchema} onChange={(event) => setLeftSchema(event.target.value)} />
          <TextField label="Right database" value={rightDb} onChange={(event) => setRightDb(event.target.value)} />
          <TextField label="Right schema" value={rightSchema} onChange={(event) => setRightSchema(event.target.value)} />
        </Box>
        <TextField label="Key columns" value={keys} onChange={(event) => setKeys(event.target.value)} fullWidth />
        <Button variant="contained" onClick={() => void compare()}>
          Compare
        </Button>
      </Panel>
      {result?.skipped ? <Typography sx={{ mb: 2 }}>{result.skipped}</Typography> : null}
      {result?.left_error ? <Typography>{result.left_error}</Typography> : null}
      {result?.right_error ? <Typography>{result.right_error}</Typography> : null}
      {result?.row_count ? (
        <Panel title="Row count">
          Left {String(result.row_count.left)} · Right {String(result.row_count.right)}
        </Panel>
      ) : null}
      {result?.schema ? (
        <Panel title="Schema">
          <Typography>Only left: {result.schema.only_left.join(", ") || "none"}</Typography>
          <Typography>Only right: {result.schema.only_right.join(", ") || "none"}</Typography>
          <Typography>
            Type mismatches:{" "}
            {result.schema.type_mismatches.map((item) => `${item.column} ${item.left_type}/${item.right_type}`).join(", ") || "none"}
          </Typography>
        </Panel>
      ) : null}
      {result?.nulls ? (
        <Panel title="Null rates">
          <DataTable rows={result.nulls} />
        </Panel>
      ) : null}
      {result?.aggregates ? (
        <Panel title="Numeric aggregates">
          <DataTable rows={result.aggregates} />
        </Panel>
      ) : null}
      {result?.keys ? (
        <Panel title="Keys">
          {result.keys.gap ? <Typography>{result.keys.gap}</Typography> : null}
          {result.keys.skipped ? null : (
            <Typography>
              matched {String(result.keys.matched)} / left {String(result.keys.left_keys)} / right {String(result.keys.right_keys)} · rate{" "}
              {result.keys.match_rate === null || result.keys.match_rate === undefined ? "—" : result.keys.match_rate} (
              {result.keys.match_rate_definition})
            </Typography>
          )}
          <DataTable rows={result.keys.mismatch_sample ?? []} />
        </Panel>
      ) : null}
    </Box>
  );
}

function FileTab() {
  const [uniqueId, setUniqueId] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<FileResult | null>(null);

  async function compare() {
    setError(null);
    try {
      setResult(await api<FileResult>("/api/compare/files", { method: "POST", body: JSON.stringify({ unique_id: uniqueId.trim() }) }));
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "File compare failed.");
    }
  }

  return (
    <Box>
      <ErrorAlert message={error} />
      <Panel title="Model SQL and compiled_code">
        <TextField label="Model unique id" value={uniqueId} onChange={(event) => setUniqueId(event.target.value)} fullWidth />
        <Button variant="contained" onClick={() => void compare()}>
          Diff
        </Button>
      </Panel>
      {result ? (
        <>
          <Typography sx={{ mb: 1 }}>Source: {result.source || "none"} {result.git_sha ? `· ${result.git_sha}` : ""}</Typography>
          {result.gaps.map((gap) => (
            <Typography key={gap}>{gap}</Typography>
          ))}
          <Diff title="Model SQL" text={result.raw_diff} />
          <Diff title="Compiled SQL" text={result.compiled_diff} />
          {result.git_diff !== null ? <Diff title="Git diff" text={result.git_diff} /> : null}
        </>
      ) : null}
    </Box>
  );
}

function Diff({ title, text }: { title: string; text: string }) {
  return (
    <Panel title={title}>
      <Box component="pre" sx={{ m: 0, whiteSpace: "pre-wrap", fontFamily: "ui-monospace, SFMono-Regular, Menlo, Consolas, monospace", fontSize: 12 }}>
        {text || "No differences."}
      </Box>
    </Panel>
  );
}
