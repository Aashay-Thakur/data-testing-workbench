import { useEffect, useMemo, useState } from "react";
import { Box, TextField } from "@mui/material";
import { useSearchParams } from "react-router-dom";
import { api } from "../api";
import type { Catalog, CatalogNode } from "../types";
import { ErrorAlert, NodeLink, PageTitle, Panel } from "../ui";
import { ModelPage } from "./ModelPage";

export function ExplorePage() {
  const [params] = useSearchParams();
  const id = params.get("id");
  if (id) return <ModelPage uniqueId={id} />;
  return <ExploreList />;
}

function ExploreList() {
  const [catalog, setCatalog] = useState<Catalog | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [query, setQuery] = useState("");

  useEffect(() => {
    api<Catalog>("/api/manifest")
      .then(setCatalog)
      .catch((reason: Error) => setError(reason.message));
  }, []);

  const rows = useMemo(() => {
    const all = [
      ...(catalog?.models ?? []),
      ...(catalog?.sources ?? []),
      ...(catalog?.snapshots ?? []),
      ...(catalog?.tests ?? []),
    ];
    const needle = query.trim().toLowerCase();
    if (!needle) return all;
    return all.filter((node) => `${node.name} ${node.unique_id}`.toLowerCase().includes(needle));
  }, [catalog, query]);

  return (
    <Box>
      <PageTitle title="Explore" />
      <ErrorAlert message={error} />
      <TextField label="Filter" value={query} onChange={(event) => setQuery(event.target.value)} sx={{ mb: 2 }} />
      <Panel title="Nodes">
        {rows.map((node) => (
          <NodeRow key={node.unique_id} node={node} />
        ))}
        {rows.length === 0 ? "Nothing to show. Load the manifest first." : null}
      </Panel>
    </Box>
  );
}

function NodeRow({ node }: { node: CatalogNode }) {
  return (
    <Box sx={{ py: 0.5, borderTop: "1px solid #d9d6cf" }}>
      <NodeLink id={node.unique_id} />
      <Box sx={{ color: "#4a4844" }}>{node.resource_type}</Box>
    </Box>
  );
}
