import { useEffect } from "react";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { useThemeStore } from "@/store/theme";
import { useAuthStore } from "@/store/auth";
import { initKeycloak } from "@/lib/keycloak";
import AppShell from "@/components/layout/AppShell";
import Dashboard    from "@/pages/Dashboard";
import Equipment    from "@/pages/Equipment";
import Alerts       from "@/pages/Alerts";
import WorkOrders   from "@/pages/WorkOrders";
import AgentActivity from "@/pages/AgentActivity";
import Approvals    from "@/pages/Approvals";
import Reports      from "@/pages/Reports";
import Login        from "@/pages/Login";

function AuthGuard({ children }: { children: React.ReactNode }) {
  const { isAuthenticated, isLoading } = useAuthStore();

  if (isLoading) {
    return (
      <div className="flex h-screen w-screen items-center justify-center bg-canvas">
        <div className="flex flex-col items-center gap-4">
          <div className="h-10 w-10 animate-spin rounded-full border-2 border-border border-t-brand" />
          <p className="font-body text-sm text-tx-secondary">Initialising OMNYX…</p>
        </div>
      </div>
    );
  }

  if (!isAuthenticated) return <Navigate to="/login" replace />;
  return <>{children}</>;
}

export default function App() {
  const { theme } = useThemeStore();
  const { setUser, setLoading } = useAuthStore();

  // Apply theme class on <html>
  useEffect(() => {
    const html = document.documentElement;
    html.classList.remove("dark", "light");
    html.classList.add(theme);
  }, [theme]);

  // Bootstrap Keycloak
  useEffect(() => {
    setLoading(true);
    initKeycloak()
      .then((user) => setUser(user))
      .finally(() => setLoading(false));
  }, [setUser, setLoading]);

  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route
          path="/*"
          element={
            <AuthGuard>
              <AppShell>
                <Routes>
                  <Route path="/"              element={<Dashboard />} />
                  <Route path="/equipment"     element={<Equipment />} />
                  <Route path="/alerts"        element={<Alerts />} />
                  <Route path="/work-orders"   element={<WorkOrders />} />
                  <Route path="/agent"         element={<AgentActivity />} />
                  <Route path="/approvals"     element={<Approvals />} />
                  <Route path="/reports"       element={<Reports />} />
                  <Route path="*"              element={<Navigate to="/" replace />} />
                </Routes>
              </AppShell>
            </AuthGuard>
          }
        />
      </Routes>
    </BrowserRouter>
  );
}
