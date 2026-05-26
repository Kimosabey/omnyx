import { useState, useEffect } from "react";
import { AnimatePresence } from "framer-motion";
import { useLocation } from "react-router-dom";
import Sidebar from "./Sidebar";
import Header  from "./Header";
import { connectWs, disconnectWs } from "@/lib/ws";
import { useAuthStore } from "@/store/auth";
import { cn } from "@/lib/utils";

interface AppShellProps {
  children: React.ReactNode;
}

export default function AppShell({ children }: AppShellProps) {
  const [collapsed,     setCollapsed]     = useState(false);
  const [mobileOpen,   setMobileOpen]     = useState(false);
  const { isAuthenticated } = useAuthStore();
  const location = useLocation();

  // Close mobile drawer on route change
  useEffect(() => {
    setMobileOpen(false);
  }, [location.pathname]);

  // Connect WebSocket once authenticated
  useEffect(() => {
    if (!isAuthenticated) return;
    connectWs();
    return disconnectWs;
  }, [isAuthenticated]);

  return (
    <div className="flex h-screen overflow-hidden bg-canvas">
      {/* Desktop Sidebar */}
      <div className="hidden lg:block">
        <Sidebar collapsed={collapsed} onCollapse={setCollapsed} />
      </div>

      {/* Mobile Sidebar Overlay */}
      <AnimatePresence>
        {mobileOpen && (
          <>
            {/* Backdrop */}
            <div
              className="fixed inset-0 z-40 bg-black/60 backdrop-blur-sm lg:hidden"
              onClick={() => setMobileOpen(false)}
              aria-hidden="true"
            />
            {/* Drawer */}
            <div className="fixed left-0 top-0 z-50 h-screen lg:hidden">
              <Sidebar collapsed={false} onCollapse={() => setMobileOpen(false)} />
            </div>
          </>
        )}
      </AnimatePresence>

      {/* Main content */}
      <div className="flex flex-1 flex-col min-w-0 overflow-hidden">
        <Header onMenuToggle={() => setMobileOpen(!mobileOpen)} />

        <main
          id="main-content"
          role="main"
          aria-label="Main content"
          className={cn(
            "flex-1 overflow-y-auto overflow-x-hidden",
            "px-4 py-6 sm:px-6 lg:px-8"
          )}
        >
          <AnimatePresence mode="wait">
            <div key={location.pathname}>
              {children}
            </div>
          </AnimatePresence>
        </main>
      </div>
    </div>
  );
}
