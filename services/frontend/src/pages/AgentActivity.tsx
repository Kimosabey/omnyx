import { useQuery } from "@tanstack/react-query";
import { motion } from "framer-motion";
import { Bot, Clock, CheckCircle2, XCircle, Loader2, Activity } from "lucide-react";
import PageTransition from "@/components/layout/PageTransition";
import Card, { CardHeader, CardTitle } from "@/components/ui/Card";
import StatusBadge from "@/components/ui/StatusBadge";
import { SkeletonRow } from "@/components/ui/SkeletonLoader";
import { agentApi, type AgentRun } from "@/lib/api";
import { formatRelativeTime } from "@/lib/utils";
import { cn } from "@/lib/utils";

const runStatusConfig: Record<string, { icon: React.ElementType; status: "good" | "bad" | "info" | "warn" | "muted"; label: string }> = {
  completed:  { icon: CheckCircle2, status: "good",  label: "Completed" },
  failed:     { icon: XCircle,      status: "bad",   label: "Failed"    },
  running:    { icon: Loader2,      status: "info",  label: "Running"   },
  pending:    { icon: Clock,        status: "muted", label: "Pending"   },
  cancelled:  { icon: XCircle,      status: "warn",  label: "Cancelled" },
};

function AgentRunRow({ run }: { run: AgentRun }) {
  const cfg  = runStatusConfig[run.status] ?? runStatusConfig.pending;
  const Icon = cfg.icon;

  return (
    <motion.article
      layout
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      className={cn(
        "flex items-start gap-3 rounded-xl border border-border bg-card p-4",
        "transition-colors duration-200 hover:border-border/60"
      )}
      aria-label={`Agent run: ${run.workflow_id}, status: ${run.status}`}
    >
      <span
        className={cn(
          "flex h-9 w-9 items-center justify-center rounded-xl shrink-0",
          cfg.status === "good" ? "bg-status-good/10" :
          cfg.status === "bad"  ? "bg-status-bad/10"  :
          cfg.status === "info" ? "bg-status-info/10"  :
                                   "bg-elevated"
        )}
        aria-hidden="true"
      >
        <Icon
          size={16}
          className={cn(
            cfg.status === "good" ? "text-status-good" :
            cfg.status === "bad"  ? "text-status-bad"  :
            cfg.status === "info" ? "text-status-info animate-spin"  :
                                     "text-tx-muted"
          )}
        />
      </span>

      <div className="flex-1 min-w-0">
        <div className="flex flex-wrap items-center gap-2 mb-1">
          <p className="font-heading font-semibold text-sm text-tx-primary">{run.workflow_id}</p>
          <StatusBadge status={cfg.status} size="xs" dot pulse={run.status === "running"}>
            {cfg.label}
          </StatusBadge>
        </div>

        <div className="flex flex-wrap items-center gap-3 text-xs text-tx-muted font-body">
          <span>Triggered by: <span className="text-tx-secondary">{run.triggered_by}</span></span>
          <span className="flex items-center gap-1">
            <Clock size={10} aria-hidden="true" />
            <time dateTime={run.started_at}>{formatRelativeTime(run.started_at)}</time>
          </span>
          {run.finished_at && (
            <span>
              Duration:{" "}
              <span className="font-mono text-tx-secondary">
                {Math.round((new Date(run.finished_at).getTime() - new Date(run.started_at).getTime()) / 1000)}s
              </span>
            </span>
          )}
        </div>

        {run.metadata && Object.keys(run.metadata).length > 0 && (
          <details className="mt-2">
            <summary className="font-mono text-xs text-tx-muted cursor-pointer hover:text-tx-secondary">
              Metadata
            </summary>
            <pre className="mt-1 rounded-lg bg-canvas p-2 font-mono text-xs text-tx-secondary overflow-x-auto">
              {JSON.stringify(run.metadata, null, 2)}
            </pre>
          </details>
        )}
      </div>
    </motion.article>
  );
}

export default function AgentActivity() {
  const { data: runs = [], isLoading } = useQuery({
    queryKey:       ["agent-runs"],
    queryFn:        agentApi.runs,
    refetchInterval: 15_000,
  });

  const runningCount   = runs.filter((r) => r.status === "running").length;
  const completedCount = runs.filter((r) => r.status === "completed").length;
  const failedCount    = runs.filter((r) => r.status === "failed").length;

  return (
    <PageTransition>
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="font-heading font-extrabold text-2xl text-tx-primary">Agent Activity</h1>
          <p className="font-body text-sm text-tx-secondary mt-0.5">
            AI workflow runs and automation history
          </p>
        </div>
        <div className="flex items-center gap-2" aria-live="polite">
          {runningCount > 0 && (
            <span className="flex items-center gap-1.5 rounded-xl bg-status-info/10 px-3 py-1.5 text-xs font-medium text-status-info">
              <Activity size={12} className="animate-pulse" aria-hidden="true" />
              {runningCount} running
            </span>
          )}
        </div>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-3 gap-3 mb-6">
        {[
          { label: "Completed", count: completedCount, status: "good"  as const },
          { label: "Running",   count: runningCount,   status: "info"  as const },
          { label: "Failed",    count: failedCount,    status: "bad"   as const },
        ].map(({ label, count }) => (
          <Card key={label} padding="sm" className="text-center">
            <p className="font-mono text-2xl font-bold text-tx-primary">{count}</p>
            <p className="font-body text-xs text-tx-muted mt-0.5">{label}</p>
          </Card>
        ))}
      </div>

      <Card padding="none">
        <CardHeader className="px-5 pt-4 pb-0">
          <CardTitle as="h2">Run History</CardTitle>
          <Bot size={16} className="text-tx-muted" aria-hidden="true" />
        </CardHeader>

        <div className="p-4 space-y-2" role="list" aria-label="Agent run history">
          {isLoading
            ? Array.from({ length: 5 }).map((_, i) => <SkeletonRow key={i} />)
            : runs.length === 0
            ? (
              <div className="flex flex-col items-center gap-3 py-16 text-center">
                <Bot size={32} className="text-tx-muted" aria-hidden="true" />
                <p className="font-heading font-semibold text-tx-secondary">No agent runs yet</p>
                <p className="font-body text-sm text-tx-muted">Automated workflows will appear here</p>
              </div>
            )
            : runs.map((run) => (
              <div key={run.id} role="listitem">
                <AgentRunRow run={run} />
              </div>
            ))
          }
        </div>
      </Card>
    </PageTransition>
  );
}
