import { useEffect, useState } from "react";
import { Box, Button } from "@mui/material";
import { useNavigate } from "react-router-dom";
import { api } from "../api";
import type { Catalog, CatalogNode, Run } from "../types";
import { ErrorAlert, NodeLink, PageTitle, Panel } from "../ui";

export function ManifestPage() {
  const [catalog, setCatalog] = useState<Catalog | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();

  async function load(refresh: boolean) {
    setLoading(true);
    setError(null);
    try {
      const result = refresh ? await api<Catalog>("/api/manifest/load", { method: "POST" }) : await api<Catalog>("/api/manifest");
      setCatalog(result);
    } catch (reason) {
      setCatalog(null);
      setError(reason instanceof Error ? reason.message : "Manifest load failed.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void load(false);
  }, []);

  async function rerun(uniqueId: string) {
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

  return (
    <Box>
      <PageTitle
        title="Manifest"
        action={
          <Button variant="contained" disabled={loading} onClick={() => void load(true)}>
            {loading ? "Loading…" : "Load from Snowflake"}
          </Button>
        }
      />
      <ErrorAlert message={error} />
      <NodeList title="Models" rows={catalog?.models ?? []} />
      <NodeList title="Sources" rows={catalog?.sources ?? []} />
      <NodeList title="Snapshots" rows={catalog?.snapshots ?? []} />
      <NodeList title="Tests" rows={catalog?.tests ?? []} onRerun={(id) => void rerun(id)} />
    </Box>
  );
}

function NodeList({
  title,
  rows,
  onRerun,
}: {
  title: string;
  rows: CatalogNode[];
  onRerun?: (uniqueId: string) => void;
}) {
  return (
    <Panel title={`${title} (${rows.length})`}>
      {rows.length === 0 ? "None loaded." : null}
      {rows.map((node) => (
        <Box key={node.unique_id} sx={{ display: "flex", justifyContent: "space-between", gap: 1, py: 0.5, borderTop: "1px solid #d9d6cf" }}>
          <Box>
            <NodeLink id={node.unique_id} />
            <Box sx={{ color: "#4a4844" }}>
              {[node.database, node.schema_name, node.alias || node.name].filter(Boolean).join(".")}
            </Box>
          </Box>
          {onRerun ? (
            <Button variant="outlined" onClick={() => onRerun(node.unique_id)}>
              Re-run as SELECT
            </Button>
          ) : null}
        </Box>
      ))}
    </Panel>
  );
}
