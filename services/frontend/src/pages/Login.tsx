import { useEffect } from "react";
import { Navigate } from "react-router-dom";
import { motion } from "framer-motion";
import { useAuthStore } from "@/store/auth";
import GraylinxLogo from "@/components/layout/GraylinxLogo";

export default function Login() {
  const { isAuthenticated, isLoading } = useAuthStore();

  // Keycloak will redirect automatically via initKeycloak in App.tsx
  // This page shows a branded loading screen
  if (isAuthenticated) return <Navigate to="/" replace />;

  return (
    <div
      className="flex h-screen w-screen flex-col items-center justify-center bg-canvas"
      role="main"
      aria-label="Login loading"
    >
      {/* Background grid pattern */}
      <div
        className="pointer-events-none absolute inset-0 opacity-5"
        aria-hidden="true"
        style={{
          backgroundImage:
            "radial-gradient(circle at 1px 1px, rgba(31,63,254,0.5) 1px, transparent 0)",
          backgroundSize: "32px 32px",
        }}
      />

      <motion.div
        initial={{ opacity: 0, y: 24 }}
        animate={{ opacity: 1, y:  0 }}
        transition={{ duration: 0.6, ease: [0.16, 1, 0.3, 1] }}
        className="relative flex flex-col items-center gap-8 text-center"
      >
        {/* Logo */}
        <div className="flex flex-col items-center gap-4">
          <GraylinxLogo className="scale-150" />
          <div className="h-px w-16 bg-gradient-to-r from-transparent via-brand to-transparent" />
        </div>

        {/* Loading state */}
        <div className="flex flex-col items-center gap-4">
          {isLoading ? (
            <>
              <div
                className="h-10 w-10 animate-spin rounded-full border-2 border-border border-t-brand"
                aria-label="Authenticating"
                role="status"
              />
              <p className="font-body text-sm text-tx-secondary">
                Authenticating with Keycloak…
              </p>
            </>
          ) : (
            <p className="font-body text-sm text-tx-secondary">
              Redirecting to login…
            </p>
          )}
        </div>

        <p className="font-mono text-2xs text-tx-muted tracking-widest uppercase">
          OMNYX IoT Operations Platform
        </p>
      </motion.div>
    </div>
  );
}
