import { useEffect, useState } from "react";
import { Box, Button, Table, TableBody, TableCell, TableHead, TableRow, Typography } from "@mui/material";
import { api } from "../api";
import { ErrorAlert, PageTitle, Panel } from "../ui";

type Settings = {
  account: string | null;
  role: string | null;
  repo: string | null;
  vars: Record<string, boolean>;
};

export function SettingsPage() {
  const [settings, setSettings] = useState<Settings | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [snowflake, setSnowflake] = useState<string | null>(null);
  const [token, setToken] = useState<string | null>(null);

  useEffect(() => {
    api<Settings>("/api/settings")
      .then(setSettings)
      .catch((reason: Error) => setError(reason.message));
  }, []);

  async function testSnowflake() {
    setSnowflake(null);
    try {
      const result = await api<{ ok: boolean; detail?: string; account?: string | null; role?: string | null }>(
        "/api/settings/test-snowflake",
        { method: "POST" },
      );
      setSnowflake(result.ok ? `Connected as ${result.role} on ${result.account}.` : result.detail || "Connection failed.");
    } catch (reason) {
      setSnowflake(reason instanceof Error ? reason.message : "Connection failed.");
    }
  }

  async function testToken() {
    setToken(null);
    try {
      const result = await api<{ ok: boolean; token_set: boolean; detail?: string | null }>(
        "/api/settings/test-token",
        { method: "POST" },
      );
      setToken(result.token_set ? "GITHUB_TOKEN is set." : result.detail || "GITHUB_TOKEN is not set.");
    } catch (reason) {
      setToken(reason instanceof Error ? reason.message : "Token check failed.");
    }
  }

  return (
    <Box>
      <PageTitle title="Settings" />
      <ErrorAlert message={error} />
      <Panel title="Loaded config">
        <Typography sx={{ mb: 1 }}>
          Account {settings?.account || "—"} · Role {settings?.role || "—"} · Repo {settings?.repo || "—"}
        </Typography>
        <Typography color="text.secondary" sx={{ mb: 1 }}>
          Values are booleans. Passwords, keys, and tokens are not shown.
        </Typography>
        <Table>
          <TableHead>
            <TableRow>
              <TableCell>Variable</TableCell>
              <TableCell>Set</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {Object.entries(settings?.vars ?? {}).map(([name, present]) => (
              <TableRow key={name}>
                <TableCell>{name}</TableCell>
                <TableCell>{present ? "yes" : "no"}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </Panel>
      <Box sx={{ display: "flex", gap: 1, mb: 2 }}>
        <Button variant="contained" onClick={testSnowflake}>
          Test Snowflake
        </Button>
        <Button variant="outlined" onClick={testToken}>
          Test token is present
        </Button>
      </Box>
      {snowflake ? <Typography sx={{ mb: 1 }}>{snowflake}</Typography> : null}
      {token ? <Typography>{token}</Typography> : null}
    </Box>
  );
}
