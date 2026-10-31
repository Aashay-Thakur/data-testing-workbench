import { useEffect, useState } from "react";
import { Box, Typography } from "@mui/material";
import { Link as RouterLink } from "react-router-dom";
import { api } from "../api";
import type { Run } from "../types";
import { ErrorAlert, Mono, PageTitle, Panel, StatusChip } from "../ui";

type Home = {
  failing: Run[];
  blocking: Run[];
  last_success: Run[];
};

export function HomePage() {
  const [data, setData] = useState<Home | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api<Home>("/api/home")
      .then(setData)
      .catch((reason: Error) => setError(reason.message));
  }, []);

  return (
    <Box>
      <PageTitle title="Recent runs" />
      <ErrorAlert message={error} />
      <Box sx={{ display: "flex", flexWrap: "wrap", gap: 2, alignItems: "stretch" }}>
        <RunColumn title="Failing" rows={data?.failing ?? []} />
        <RunColumn title="Blocking" rows={data?.blocking ?? []} />
        <RunColumn title="Last success" rows={data?.last_success ?? []} />
      </Box>
    </Box>
  );
}

function RunColumn({ title, rows }: { title: string; rows: Run[] }) {
  return (
    <Box sx={{ flex: "1 1 280px" }}>
      <Panel title={title}>
        {rows.length === 0 ? (
          <Typography color="text.secondary">None.</Typography>
        ) : (
          rows.map((run) => (
            <Box
              key={run.id}
              component={RouterLink}
              to={`/runs/${run.id}`}
              sx={{
                display: "block",
                textDecoration: "none",
                color: "inherit",
                borderTop: "1px solid #d9d6cf",
                py: 1,
              }}
            >
              <Box sx={{ display: "flex", justifyContent: "space-between", gap: 1 }}>
                <Typography>{run.name || run.kind}</Typography>
                <StatusChip status={run.status} />
              </Box>
              <Typography variant="body2" color="text.secondary">
                <Mono>{run.target || "unset"}</Mono>
                {" · "}
                {run.runtime_ms ?? 0} ms
              </Typography>
            </Box>
          ))
        )}
      </Panel>
    </Box>
  );
}
