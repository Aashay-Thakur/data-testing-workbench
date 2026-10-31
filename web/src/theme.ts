import { createTheme, type Shadows } from "@mui/material/styles";

const shadows = Array.from({ length: 25 }, () => "none") as Shadows;

export const theme = createTheme({
  palette: {
    mode: "light",
    primary: { main: "#1a56db" },
    background: { default: "#f6f5f2", paper: "#fffcf8" },
    text: { primary: "#161616", secondary: "#4a4844" },
    divider: "#d9d6cf",
    error: { main: "#9f1d1d" },
    success: { main: "#1d6b3a" },
    warning: { main: "#8a5a00" },
  },
  shape: { borderRadius: 2 },
  spacing: 8,
  shadows,
  typography: {
    fontFamily: '"Segoe UI", "Helvetica Neue", Arial, sans-serif',
    fontSize: 13,
    h1: { fontSize: "1.35rem", fontWeight: 650, letterSpacing: 0 },
    h2: { fontSize: "1rem", fontWeight: 650 },
    button: { textTransform: "none", fontWeight: 600 },
  },
  components: {
    MuiCssBaseline: {
      styleOverrides: { body: { backgroundColor: "#f6f5f2" } },
    },
    MuiPaper: {
      styleOverrides: {
        root: { backgroundImage: "none", boxShadow: "none", border: "1px solid #d9d6cf" },
      },
    },
    MuiAppBar: {
      defaultProps: { elevation: 0, color: "default" },
      styleOverrides: {
        root: {
          boxShadow: "none",
          borderBottom: "1px solid #d9d6cf",
          backgroundColor: "#fffcf8",
          color: "#161616",
        },
      },
    },
    MuiButton: {
      defaultProps: { size: "small", disableElevation: true },
      styleOverrides: { root: { boxShadow: "none", borderRadius: 2 } },
    },
    MuiTextField: { defaultProps: { size: "small", margin: "dense" } },
    MuiTable: { defaultProps: { size: "small" } },
    MuiTableCell: {
      styleOverrides: {
        root: { borderColor: "#d9d6cf", padding: "6px 8px" },
        head: { fontWeight: 650 },
      },
    },
    MuiChip: { defaultProps: { size: "small", variant: "outlined" } },
    MuiAlert: {
      styleOverrides: { root: { borderRadius: 2 } },
    },
    MuiTab: { styleOverrides: { root: { textTransform: "none", minHeight: 36 } } },
    MuiTabs: { styleOverrides: { root: { minHeight: 36 } } },
  },
});
