import { useEffect, useState } from "react";
import { Alert, Box, Button, Table, TableBody, TableCell, TableHead, TableRow, Typography } from "@mui/material";
import { useNavigate } from "react-router-dom";
import { api } from "../api";
import type { Run } from "../types";
import { ErrorAlert, Mono, NodeLink, PageTitle, Panel } from "../ui";

type Explore = {
  node: {
    unique_id: string;
    name: string;
    resource_type: string;
    database?: string | null;
    schema_name?: string | null;
    alias?: string | null;
    description?: string;
    compiled_code_present: boolean;
  };
  upstream: string[];
  downstream: string[];
  upstream_all: string[];
  downstream_all: string[];
  columns: { column_name: string; data_type: string; is_nullable: string; ordinal_position: number }[];
  column_error: string | null;
  ctes: { name: string; columns: string[] }[];
  lineage: { name: string; sources: { column?: string; table?: string | null; expression?: string | null }[]; gap: string | null }[];
  gaps: string[];
};

export function ModelPage({ uniqueId }: { uniqueId: string }) {
  const [data, setData] = useState<Explore | null>(null);
  const [error, setError] = useState<string | null>(null);
  const navigate = useNavigate();

  useEffect(() => {
    setData(null);
    api<Explore>(`/api/explore/node?unique_id=${encodeURIComponent(uniqueId)}`)
      .then(setData)
      .catch((reason: Error) => setError(reason.message));
  }, [uniqueId]);

  async function rerun() {
    setError(null);
    try {
      const run = await api<Run>("/api/manifest/tests/rerun", {
        method: "POST",
        body: JSON.stringify({ unique_id: uniqueId }),
      });
      navigate(`/runs/${run.id}`);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Re-run failed.");
    }
  }

  const node = data?.node;
  return (
    <Box>
      <PageTitle
        title={node?.name || uniqueId}
        action={
          node?.resource_type === "test" ? (
            <Button variant="contained" onClick={() => void rerun()}>
              Re-run compiled_code
            </Button>
          ) : null
        }
      />
      <ErrorAlert message={error} />
      {node ? (
        <Typography sx={{ mb: 2 }}>
          {node.resource_type} · {[node.database, node.schema_name, node.alias].filter(Boolean).join(".") || "no relation"} ·{" "}
          compiled SQL {node.compiled_code_present ? "present" : "absent"}
        </Typography>
      ) : null}
      {node?.description ? <Typography sx={{ mb: 2 }}>{node.description}</Typography> : null}
      {data && data.gaps.length > 0 ? (
        <Alert severity="warning" sx={{ mb: 2 }}>
          {data.gaps.map((gap) => (
            <div key={gap}>{gap}</div>
          ))}
        </Alert>
      ) : null}
      <Box sx={{ display: "flex", flexWrap: "wrap", gap: 2 }}>
        <Box sx={{ flex: "1 1 320px" }}>
          <IdList title="Upstream (parent_map)" ids={data?.upstream ?? []} />
          <IdList title="Upstream reachable" ids={data?.upstream_all ?? []} />
        </Box>
        <Box sx={{ flex: "1 1 320px" }}>
          <IdList title="Downstream (child_map)" ids={data?.downstream ?? []} />
          <IdList title="Downstream reachable" ids={data?.downstream_all ?? []} />
        </Box>
      </Box>
      <Panel title="Columns from information_schema">
        {data?.column_error ? <Typography sx={{ mb: 1 }}>{data.column_error}</Typography> : null}
        <Table>
          <TableHead>
            <TableRow>
              <TableCell>Column</TableCell>
              <TableCell>Type</TableCell>
              <TableCell>Nullable</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {(data?.columns ?? []).map((column) => (
              <TableRow key={column.column_name}>
                <TableCell>{column.column_name}</TableCell>
                <TableCell>{column.data_type}</TableCell>
                <TableCell>{column.is_nullable}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </Panel>
      <Panel title="CTEs">
        {(data?.ctes ?? []).length === 0 ? <Typography color="text.secondary">No CTEs.</Typography> : null}
        {(data?.ctes ?? []).map((cte) => (
          <Box key={cte.name} sx={{ py: 0.5 }}>
            <Mono>{cte.name}</Mono> {cte.columns.join(", ") || "(no columns)"}
          </Box>
        ))}
      </Panel>
      <Panel title="Column lineage">
        <Table>
          <TableHead>
            <TableRow>
              <TableCell>Column</TableCell>
              <TableCell>Sources</TableCell>
              <TableCell>Gap</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {(data?.lineage ?? []).map((column) => (
              <TableRow key={column.name}>
                <TableCell>{column.name}</TableCell>
                <TableCell>
                  {column.sources.length === 0
                    ? ""
                    : column.sources.map((source) => source.column || source.expression || source.table || "").join(", ")}
                </TableCell>
                <TableCell>{column.gap || ""}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </Panel>
    </Box>
  );
}

function IdList({ title, ids }: { title: string; ids: string[] }) {
  return (
    <Panel title={title}>
      {ids.length === 0 ? <Typography color="text.secondary">None.</Typography> : null}
      {ids.map((id) => (
        <Box key={id} sx={{ py: 0.25 }}>
          <NodeLink id={id} />
        </Box>
      ))}
    </Panel>
  );
}
