import { NavLink, useLocation } from "react-router-dom";
import { motion, AnimatePresence } from "framer-motion";
import {
  LayoutDashboard, Cpu, Bell, ClipboardList,
  Bot, CheckSquare, BarChart3, ChevronLeft, ChevronRight,
} from "lucide-react";
import { cn } from "@/lib/utils";
import GraylinxLogo from "./GraylinxLogo";
import { useSnapshotStore } from "@/store/snapshot";

interface SidebarProps {
  collapsed:   boolean;
  onCollapse:  (v: boolean) => void;
}

interface NavItem {
  label:   string;
  to:      string;
  icon:    React.ElementType;
  badge?:  () => number | null;
}

const NAV_ITEMS: NavItem[] = [
  { label: "Dashboard",    to: "/",            icon: LayoutDashboard },
  { label: "Equipment",    to: "/equipment",   icon: Cpu },
  { label: "Alerts",       to: "/alerts",      icon: Bell },
  { label: "Work Orders",  to: "/work-orders", icon: ClipboardList },
  { label: "Agent AI",     to: "/agent",       icon: Bot },
  { label: "Approvals",    to: "/approvals",   icon: CheckSquare },
  { label: "Reports",      to: "/reports",     icon: BarChart3 },
];

function LiveIndicator() {
  const isConnected = useSnapshotStore((s) => s.isConnected);
  return (
    <div className="flex items-center gap-2 px-3 py-2">
      <span
        className={cn(
          "h-2 w-2 rounded-full shrink-0",
          isConnected
            ? "bg-status-good animate-pulse-slow shadow-status-good"
            : "bg-tx-muted"
        )}
        aria-label={isConnected ? "Live data connected" : "Disconnected"}
      />
      <AnimatePresence>
        {!isConnected ? null : (
          <motion.span
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="font-mono text-2xs text-status-good tracking-widest uppercase"
          >
            Live
          </motion.span>
        )}
      </AnimatePresence>
    </div>
  );
}

export default function Sidebar({ collapsed, onCollapse }: SidebarProps) {
  const location = useLocation();

  return (
    <motion.aside
      animate={{ width: collapsed ? 64 : 240 }}
      transition={{ type: "spring", stiffness: 300, damping: 30 }}
      className={cn(
        "relative flex h-screen flex-col",
        "bg-sidebar border-r border-white/5",
        "z-30 shrink-0 overflow-hidden"
      )}
      aria-label="Main navigation"
    >
      {/* Logo */}
      <div className="flex h-16 items-center px-4 border-b border-white/5">
        <GraylinxLogo collapsed={collapsed} />
      </div>

      {/* Nav */}
      <nav className="flex-1 overflow-y-auto overflow-x-hidden py-4" aria-label="Primary navigation">
        <ul className="flex flex-col gap-1 px-2" role="list">
          {NAV_ITEMS.map(({ label, to, icon: Icon }) => {
            const isActive =
              to === "/" ? location.pathname === "/" : location.pathname.startsWith(to);

            return (
              <li key={to}>
                <NavLink
                  to={to}
                  aria-label={label}
                  aria-current={isActive ? "page" : undefined}
                  className={({ isActive: active }) =>
                    cn(
                      "group relative flex items-center gap-3 rounded-xl px-3 py-2.5",
                      "min-h-touch transition-all duration-200 ease-out-expo",
                      "focus-visible:ring-2 focus-visible:ring-white/50 focus-visible:outline-none",
                      active
                        ? "bg-white/15 text-white shadow-glow-sm"
                        : "text-white/60 hover:bg-white/8 hover:text-white"
                    )
                  }
                  end={to === "/"}
                >
                  {({ isActive: active }) => (
                    <>
                      {/* Active indicator bar */}
                      {active && (
                        <motion.span
                          layoutId="nav-pill"
                          className="absolute left-0 top-1/2 -translate-y-1/2 w-1 h-8 rounded-r-full bg-white"
                          transition={{ type: "spring", stiffness: 400, damping: 30 }}
                        />
                      )}

                      <Icon
                        size={18}
                        className={cn(
                          "shrink-0 transition-transform duration-200",
                          "group-hover:scale-110",
                          active ? "text-white" : "text-white/60"
                        )}
                        aria-hidden="true"
                      />

                      <AnimatePresence>
                        {!collapsed && (
                          <motion.span
                            initial={{ opacity: 0, x: -8 }}
                            animate={{ opacity: 1, x: 0 }}
                            exit={{ opacity: 0, x: -8 }}
                            transition={{ duration: 0.2 }}
                            className={cn(
                              "font-body text-sm font-medium whitespace-nowrap",
                              active ? "text-white" : "text-white/70"
                            )}
                          >
                            {label}
                          </motion.span>
                        )}
                      </AnimatePresence>
                    </>
                  )}
                </NavLink>
              </li>
            );
          })}
        </ul>
      </nav>

      {/* Live status */}
      <div className="border-t border-white/5">
        <LiveIndicator />
      </div>

      {/* Collapse toggle */}
      <button
        onClick={() => onCollapse(!collapsed)}
        aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
        aria-expanded={!collapsed}
        className={cn(
          "flex h-10 w-full items-center justify-center",
          "border-t border-white/5 text-white/40",
          "hover:text-white hover:bg-white/5 transition-colors duration-200",
          "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white/50"
        )}
      >
        {collapsed
          ? <ChevronRight size={16} aria-hidden="true" />
          : <ChevronLeft  size={16} aria-hidden="true" />
        }
      </button>
    </motion.aside>
  );
}
