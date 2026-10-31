import { useEffect, useState } from "react";
import { Box, Typography } from "@mui/material";
import { useParams } from "react-router-dom";
import { api } from "../api";
import type { Run } from "../types";
import { DataTable, ErrorAlert, Mono, PageTitle, Panel, StatusChip } from "../ui";

export function RunPage() {
  const params = useParams();
  const [run, setRun] = useState<Run | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!params.id) return;
    api<Run>(`/api/runs/${params.id}`)
      .then(setRun)
      .catch((reason: Error) => setError(reason.message));
  }, [params.id]);

  return (
    <Box>
      <PageTitle title={run?.name || "Run"} action={run ? <StatusChip status={run.status} /> : undefined} />
      <ErrorAlert message={error} />
      {run ? (
        <>
          <Panel title="Result">
            <Fact label="Status" value={run.status} />
            <Fact label="Target" value={run.target || "—"} />
            <Fact label="Runtime" value={run.runtime_ms === null ? "—" : `${run.runtime_ms} ms`} />
            {run.git_sha ? <Fact label="Git sha" value={run.git_sha} /> : null}
            <Fact label="Message" value={run.message || "—"} />
            <Typography sx={{ mt: 1 }}>Threshold</Typography>
            <Mono>{JSON.stringify(run.threshold)}</Mono>
          </Panel>
          <Panel title="Metrics">
            <Mono>{JSON.stringify(run.metrics)}</Mono>
          </Panel>
          <Panel title="Sample">
            <DataTable rows={run.sample} />
          </Panel>
        </>
      ) : null}
    </Box>
  );
}

function Fact({ label, value }: { label: string; value: string }) {
  return (
    <Typography>
      {label}: {value}
    </Typography>
  );
}
