import { motion } from "framer-motion";
import { AlertTriangle, AlertCircle, Info, CheckCircle2, Clock } from "lucide-react";
import type { Alert } from "@/lib/api";
import { formatRelativeTime } from "@/lib/utils";
import StatusBadge from "./StatusBadge";
import Button from "./Button";
import { cn } from "@/lib/utils";

const severityConfig = {
  critical: { icon: AlertCircle,   color: "text-status-bad",  bg: "bg-status-bad/10",  status: "bad"  as const },
  high:     { icon: AlertTriangle, color: "text-status-warn", bg: "bg-status-warn/10", status: "warn" as const },
  medium:   { icon: AlertTriangle, color: "text-status-warn", bg: "bg-status-warn/10", status: "warn" as const },
  low:      { icon: Info,          color: "text-status-info", bg: "bg-status-info/10", status: "info" as const },
};

interface AlertRowProps {
  alert:         Alert;
  onAcknowledge?: (id: string) => void;
  onResolve?:    (id: string) => void;
  loading?:      boolean;
}

export default function AlertRow({
  alert,
  onAcknowledge,
  onResolve,
  loading,
}: AlertRowProps) {
  const cfg = severityConfig[alert.severity as keyof typeof severityConfig] ?? severityConfig.low;
  const Icon = cfg.icon;

  return (
    <motion.article
      initial={{ opacity: 0, x: -12 }}
      animate={{ opacity: 1, x:   0  }}
      transition={{ duration: 0.3, ease: "easeOut" }}
      className={cn(
        "flex items-start gap-3 rounded-xl border border-border bg-card p-4",
        "transition-colors duration-200 hover:border-border/80"
      )}
      aria-label={`Alert: ${alert.title}, severity: ${alert.severity}`}
    >
      {/* Severity icon */}
      <span
        className={cn(
          "flex h-9 w-9 shrink-0 items-center justify-center rounded-xl",
          cfg.bg
        )}
        aria-hidden="true"
      >
        <Icon size={16} className={cfg.color} />
      </span>

      {/* Content */}
      <div className="flex-1 min-w-0">
        <div className="flex flex-wrap items-center gap-2 mb-1">
          <p className="font-heading font-semibold text-sm text-tx-primary truncate">
            {alert.title}
          </p>
          <StatusBadge status={cfg.status} size="xs" dot>
            {alert.severity}
          </StatusBadge>
          {alert.status === "acknowledged" && (
            <StatusBadge status="info" size="xs">ack'd</StatusBadge>
          )}
          {alert.status === "resolved" && (
            <StatusBadge status="good" size="xs">resolved</StatusBadge>
          )}
        </div>

        <p className="font-body text-xs text-tx-secondary line-clamp-2 mb-2">
          {alert.description}
        </p>

        <div className="flex items-center gap-3 text-xs text-tx-muted">
          <Clock size={10} aria-hidden="true" />
          <time dateTime={alert.triggered_at}>
            {formatRelativeTime(alert.triggered_at)}
          </time>
        </div>
      </div>

      {/* Actions */}
      {alert.status === "open" && (
        <div className="flex flex-col gap-1 shrink-0">
          {onAcknowledge && (
            <Button
              size="xs"
              variant="secondary"
              loading={loading}
              onClick={() => onAcknowledge(alert.id)}
              aria-label={`Acknowledge alert: ${alert.title}`}
            >
              Ack
            </Button>
          )}
          {onResolve && (
            <Button
              size="xs"
              variant="success"
              loading={loading}
              onClick={() => onResolve(alert.id)}
              aria-label={`Resolve alert: ${alert.title}`}
            >
              <CheckCircle2 size={12} aria-hidden="true" />
              Resolve
            </Button>
          )}
        </div>
      )}
    </motion.article>
  );
}
