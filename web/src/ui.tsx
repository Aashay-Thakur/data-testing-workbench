import { Alert, Box, Chip, Paper, Table, TableBody, TableCell, TableHead, TableRow, Typography } from "@mui/material";
import { Link as RouterLink, useLocation } from "react-router-dom";
import type { ReactNode } from "react";

const links = [
  ["/", "Home"],
  ["/settings", "Settings"],
  ["/snowflake", "Snowflake"],
  ["/manifest", "Manifest"],
  ["/explore", "Explore"],
  ["/checks", "Checks"],
  ["/rules", "Rules"],
  ["/compare", "Compare"],
] as const;

export function Shell({ children }: { children: ReactNode }) {
  const location = useLocation();
  return (
    <Box sx={{ minHeight: "100vh" }}>
      <Box
        component="header"
        sx={{
          position: "sticky",
          top: 0,
          zIndex: 2,
          backgroundColor: "#fffcf8",
          borderBottom: "1px solid #d9d6cf",
          px: 2,
          py: 1,
        }}
      >
        <Typography variant="h1" sx={{ mb: 0.5 }}>
          Data testing workbench
        </Typography>
        <Box sx={{ display: "flex", flexWrap: "wrap", gap: 0.5 }}>
          {links.map(([path, label]) => {
            const selected = path === "/" ? location.pathname === "/" : location.pathname.startsWith(path);
            return (
              <Box
                key={path}
                component={RouterLink}
                to={path}
                sx={{
                  px: 1,
                  py: 0.5,
                  textDecoration: "none",
                  color: selected ? "#1a56db" : "#161616",
                  borderBottom: selected ? "2px solid #1a56db" : "2px solid transparent",
                }}
              >
                {label}
              </Box>
            );
          })}
        </Box>
      </Box>
      <Box sx={{ p: 2, maxWidth: 1100, mx: "auto" }}>{children}</Box>
    </Box>
  );
}

export function PageTitle({ title, action }: { title: string; action?: ReactNode }) {
  return (
    <Box sx={{ display: "flex", alignItems: "center", justifyContent: "space-between", mb: 2, gap: 2 }}>
      <Typography variant="h1">{title}</Typography>
      {action}
    </Box>
  );
}

export function Panel({ title, children }: { title?: string; children: ReactNode }) {
  return (
    <Paper sx={{ p: 2, mb: 2 }}>
      {title ? (
        <Typography variant="h2" sx={{ mb: 1 }}>
          {title}
        </Typography>
      ) : null}
      {children}
    </Paper>
  );
}

export function ErrorAlert({ message }: { message: string | null }) {
  if (!message) return null;
  return (
    <Alert severity="error" sx={{ mb: 2 }}>
      {message}
    </Alert>
  );
}

export function StatusChip({ status }: { status: string }) {
  const color = status === "pass" ? "success" : status === "fail" ? "error" : status === "error" ? "warning" : "default";
  return <Chip label={status} color={color} />;
}

export function Mono({ children }: { children: ReactNode }) {
  return (
    <Box component="span" sx={{ fontFamily: "ui-monospace, SFMono-Regular, Menlo, Consolas, monospace", fontSize: 12 }}>
      {children}
    </Box>
  );
}

export function DataTable({ rows }: { rows: Record<string, unknown>[] }) {
  if (!rows.length) {
    return <Typography color="text.secondary">No rows.</Typography>;
  }
  const columns: string[] = [];
  rows.forEach((row) => {
    Object.keys(row).forEach((key) => {
      if (!columns.includes(key)) columns.push(key);
    });
  });
  return (
    <Table>
      <TableHead>
        <TableRow>
          {columns.map((column) => (
            <TableCell key={column}>{column}</TableCell>
          ))}
        </TableRow>
      </TableHead>
      <TableBody>
        {rows.map((row, index) => (
          <TableRow key={index}>
            {columns.map((column) => (
              <TableCell key={column}>{formatCell(row[column])}</TableCell>
            ))}
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}

function formatCell(value: unknown): string {
  if (value === null || value === undefined) return "";
  if (typeof value === "object") return JSON.stringify(value);
  return String(value);
}

export function NodeLink({ id }: { id: string }) {
  return (
    <Box component={RouterLink} to={`/explore?id=${encodeURIComponent(id)}`} sx={{ textDecoration: "none" }}>
      <Mono>{id}</Mono>
    </Box>
  );
}
