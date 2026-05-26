import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Bell, User, LogOut, ChevronDown, Menu } from "lucide-react";
import * as DropdownMenu from "@radix-ui/react-dropdown-menu";
import * as Tooltip from "@radix-ui/react-tooltip";
import { motion, AnimatePresence } from "framer-motion";
import { useAuthStore } from "@/store/auth";
import { notificationsApi } from "@/lib/api";
import { logout } from "@/lib/keycloak";
import { cn } from "@/lib/utils";
import ThemeToggle from "@/components/ui/ThemeToggle";

interface HeaderProps {
  onMenuToggle?: () => void;
}

function NotificationBell() {
  const [open, setOpen] = useState(false);
  const { data: notifications = [] } = useQuery({
    queryKey: ["notifications"],
    queryFn:  notificationsApi.list,
    refetchInterval: 30_000,
  });

  const unread = notifications.filter((n) => !n.read_at).length;

  return (
    <DropdownMenu.Root open={open} onOpenChange={setOpen}>
      <Tooltip.Root>
        <Tooltip.Trigger asChild>
          <DropdownMenu.Trigger asChild>
            <button
              aria-label={`Notifications${unread ? `, ${unread} unread` : ""}`}
              className={cn(
                "relative flex h-10 w-10 items-center justify-center rounded-xl",
                "text-tx-secondary hover:text-tx-primary hover:bg-elevated",
                "transition-colors duration-200",
                "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand"
              )}
            >
              <Bell size={18} aria-hidden="true" />
              {unread > 0 && (
                <motion.span
                  initial={{ scale: 0 }}
                  animate={{ scale: 1 }}
                  className={cn(
                    "absolute -top-0.5 -right-0.5 flex h-4 w-4 items-center justify-center",
                    "rounded-full bg-status-bad text-white font-mono text-2xs font-medium"
                  )}
                  aria-hidden="true"
                >
                  {unread > 9 ? "9+" : unread}
                </motion.span>
              )}
            </button>
          </DropdownMenu.Trigger>
        </Tooltip.Trigger>
        <Tooltip.Content side="bottom" className="rounded-lg bg-elevated px-2 py-1 text-xs text-tx-secondary shadow-card">
          Notifications
        </Tooltip.Content>
      </Tooltip.Root>

      <DropdownMenu.Portal>
        <AnimatePresence>
          {open && (
            <DropdownMenu.Content
              asChild
              align="end"
              sideOffset={8}
              className="z-50"
            >
              <motion.div
                initial={{ opacity: 0, y: -8 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -8 }}
                transition={{ duration: 0.2, ease: "easeOut" }}
                className={cn(
                  "w-80 rounded-2xl border border-border bg-card shadow-card",
                  "p-2 space-y-1 max-h-96 overflow-y-auto"
                )}
              >
                <p className="px-3 py-2 font-heading text-xs font-semibold text-tx-muted uppercase tracking-widest">
                  Notifications
                </p>
                {notifications.length === 0 ? (
                  <p className="px-3 py-4 text-center text-sm text-tx-muted">All caught up</p>
                ) : (
                  notifications.slice(0, 8).map((n) => (
                    <DropdownMenu.Item
                      key={n.id}
                      className={cn(
                        "flex flex-col gap-0.5 rounded-xl px-3 py-2 cursor-default",
                        "hover:bg-elevated focus:bg-elevated outline-none",
                        !n.read_at && "border-l-2 border-brand"
                      )}
                    >
                      <span className="text-sm font-medium text-tx-primary">{n.title}</span>
                      <span className="text-xs text-tx-secondary line-clamp-2">{n.body}</span>
                    </DropdownMenu.Item>
                  ))
                )}
              </motion.div>
            </DropdownMenu.Content>
          )}
        </AnimatePresence>
      </DropdownMenu.Portal>
    </DropdownMenu.Root>
  );
}

function UserMenu() {
  const { user } = useAuthStore();
  const [open, setOpen] = useState(false);
  const initials = user?.name?.split(" ").map((w) => w[0]).join("").slice(0, 2).toUpperCase() ?? "U";

  return (
    <DropdownMenu.Root open={open} onOpenChange={setOpen}>
      <DropdownMenu.Trigger asChild>
        <button
          aria-label={`User menu for ${user?.name ?? "user"}`}
          aria-haspopup="menu"
          aria-expanded={open}
          className={cn(
            "flex items-center gap-2 rounded-xl px-2 py-1.5",
            "hover:bg-elevated transition-colors duration-200",
            "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand"
          )}
        >
          <span
            className={cn(
              "flex h-8 w-8 items-center justify-center rounded-xl",
              "bg-gradient-brand text-white font-heading font-bold text-xs shrink-0"
            )}
            aria-hidden="true"
          >
            {initials}
          </span>
          <span className="hidden sm:block text-sm font-medium text-tx-primary max-w-24 truncate">
            {user?.name ?? "User"}
          </span>
          <ChevronDown size={14} className="text-tx-muted hidden sm:block" aria-hidden="true" />
        </button>
      </DropdownMenu.Trigger>

      <DropdownMenu.Portal>
        <AnimatePresence>
          {open && (
            <DropdownMenu.Content asChild align="end" sideOffset={8} className="z-50">
              <motion.div
                initial={{ opacity: 0, y: -8 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -8 }}
                transition={{ duration: 0.2 }}
                className="w-56 rounded-2xl border border-border bg-card shadow-card p-2"
              >
                <div className="px-3 py-2 border-b border-border mb-1">
                  <p className="text-sm font-semibold text-tx-primary">{user?.name}</p>
                  <p className="text-xs text-tx-muted truncate">{user?.email}</p>
                </div>

                <DropdownMenu.Item
                  className={cn(
                    "flex items-center gap-2 rounded-xl px-3 py-2 text-sm cursor-default",
                    "text-tx-secondary hover:bg-elevated hover:text-tx-primary outline-none"
                  )}
                >
                  <User size={14} aria-hidden="true" />
                  Profile
                </DropdownMenu.Item>

                <DropdownMenu.Item
                  onSelect={() => logout()}
                  className={cn(
                    "flex items-center gap-2 rounded-xl px-3 py-2 text-sm cursor-default",
                    "text-status-bad hover:bg-status-bad/10 outline-none mt-1"
                  )}
                >
                  <LogOut size={14} aria-hidden="true" />
                  Sign out
                </DropdownMenu.Item>
              </motion.div>
            </DropdownMenu.Content>
          )}
        </AnimatePresence>
      </DropdownMenu.Portal>
    </DropdownMenu.Root>
  );
}

export default function Header({ onMenuToggle }: HeaderProps) {
  return (
    <Tooltip.Provider delayDuration={400}>
      <header
        role="banner"
        className={cn(
          "flex h-16 items-center justify-between px-4 sm:px-6",
          "border-b border-border bg-card/80 backdrop-blur-sm",
          "sticky top-0 z-20"
        )}
      >
        {/* Left — mobile menu toggle */}
        <div className="flex items-center gap-3">
          {onMenuToggle && (
            <button
              onClick={onMenuToggle}
              aria-label="Toggle navigation menu"
              className={cn(
                "flex h-10 w-10 items-center justify-center rounded-xl lg:hidden",
                "text-tx-secondary hover:text-tx-primary hover:bg-elevated",
                "transition-colors duration-200",
                "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand"
              )}
            >
              <Menu size={18} aria-hidden="true" />
            </button>
          )}
          <div>
            <p className="font-heading font-bold text-sm text-tx-primary">OMNYX</p>
            <p className="font-body text-xs text-tx-muted">IoT Operations Platform</p>
          </div>
        </div>

        {/* Right — actions */}
        <div className="flex items-center gap-2">
          <ThemeToggle />
          <NotificationBell />
          <UserMenu />
        </div>
      </header>
    </Tooltip.Provider>
  );
}
