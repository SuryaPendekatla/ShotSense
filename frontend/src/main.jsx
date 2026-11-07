import { StrictMode, useEffect, useState } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter, Link, Route, Routes } from "react-router-dom";
import "@fontsource-variable/archivo/wdth.css";
import "./index.css";
import { api } from "./api";
import { AuthProvider, useAuth } from "./auth";
import Header from "./components/Header";
import { Spinner } from "./components/ui";
import AnalysisPage from "./pages/AnalysisPage";
import AuthPage from "./pages/AuthPage";
import Dashboard from "./pages/Dashboard";

function App() {
  const { token, checking } = useAuth();
  const [model, setModel] = useState(null);
  const [config, setConfig] = useState(null);

  useEffect(() => {
    api("/api/model").then(setModel).catch(() => setModel(null));
    api("/api/config").then(setConfig).catch(() => setConfig(null));
  }, []);

  if (checking) {
    return (
      <div className="flex min-h-screen items-center justify-center gap-2 text-graphite">
        <Spinner /> Loading
      </div>
    );
  }
  if (!token) return <AuthPage />;

  return (
    <>
      <Header />
      <Routes>
        <Route path="/" element={<Dashboard model={model} config={config} />} />
        <Route path="/analyses/:id" element={<AnalysisPage model={model} />} />
        <Route
          path="*"
          element={
            <main className="mx-auto max-w-6xl px-4 py-12 sm:px-6">
              <h1 className="condensed text-3xl font-bold">Page not found</h1>
              <Link to="/" className="mt-3 inline-block font-semibold text-marker">Go to your analyses</Link>
            </main>
          }
        />
      </Routes>
    </>
  );
}

createRoot(document.getElementById("root")).render(
  <StrictMode>
    <BrowserRouter>
      <AuthProvider>
        <App />
      </AuthProvider>
    </BrowserRouter>
  </StrictMode>,
);
