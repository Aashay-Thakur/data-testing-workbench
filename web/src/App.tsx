import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { Shell } from "./ui";
import { HomePage } from "./pages/HomePage";
import { SettingsPage } from "./pages/SettingsPage";
import { SnowflakePage } from "./pages/SnowflakePage";
import { ManifestPage } from "./pages/ManifestPage";
import { ExplorePage } from "./pages/ExplorePage";
import { ChecksPage, RulesPage } from "./pages/DefinitionPage";
import { ComparePage } from "./pages/ComparePage";
import { RunPage } from "./pages/RunPage";

export function App() {
  return (
    <BrowserRouter>
      <Shell>
        <Routes>
          <Route path="/" element={<HomePage />} />
          <Route path="/settings" element={<SettingsPage />} />
          <Route path="/snowflake" element={<SnowflakePage />} />
          <Route path="/manifest" element={<ManifestPage />} />
          <Route path="/explore" element={<ExplorePage />} />
          <Route path="/checks" element={<ChecksPage />} />
          <Route path="/rules" element={<RulesPage />} />
          <Route path="/compare" element={<ComparePage />} />
          <Route path="/runs/:id" element={<RunPage />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </Shell>
    </BrowserRouter>
  );
}
