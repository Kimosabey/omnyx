import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { motion, AnimatePresence } from "framer-motion";
import { CheckSquare, Check, X, Clock, Shield } from "lucide-react";
import PageTransition from "@/components/layout/PageTransition";
import Card from "@/components/ui/Card";
import Button from "@/components/ui/Button";
import StatusBadge from "@/components/ui/StatusBadge";
import { SkeletonRow } from "@/components/ui/SkeletonLoader";
import { agentApi, type AgentRun } from "@/lib/api";
import { formatRelativeTime } from "@/lib/utils";
import { cn } from "@/lib/utils";

// Approvals are pending agent runs that require human confirmation
function ApprovalCard({
  run,
  onApprove,
  onReject,
  loading,
}: {
  run: AgentRun;
  onApprove: (id: string) => void;
  onReject:  (id: string) => void;
  loading:   boolean;
}) {
  const [expanded, setExpanded] = useState(false);

  return (
    <motion.article
      layout
      initial={{ opacity: 0, scale: 0.97 }}
      animate={{ opacity: 1, scale: 1 }}
      exit={{    opacity: 0, scale: 0.97 }}
      transition={{ duration: 0.3 }}
      className={cn(
        "rounded-2xl border border-brand/30 bg-card",
        "shadow-[0_0_20px_rgb(31,63,254,0.08)]"
      )}
      aria-label={`Pending approval: ${run.workflow_id}`}
    >
      <div className="flex items-start gap-3 p-5">
        <span
          className="flex h-10 w-10 items-center justify-center rounded-xl bg-brand/10 shrink-0"
          aria-hidden="true"
        >
          <Shield size={18} className="text-brand" />
        </span>

        <div className="flex-1 min-w-0">
          <div className="flex flex-wrap items-center gap-2 mb-1">
            <p className="font-heading font-semibold text-sm text-tx-primary">{run.workflow_id}</p>
            <StatusBadge status="warn" size="xs" dot pulse>Awaiting Approval</StatusBadge>
          </div>

          <div className="flex flex-wrap items-center gap-3 text-xs text-tx-muted font-body">
            <span>By: <span className="text-tx-secondary">{run.triggered_by}</span></span>
            <span className="flex items-center gap-1">
              <Clock size={10} aria-hidden="true" />
              <time dateTime={run.started_at}>{formatRelativeTime(run.started_at)}</time>
            </span>
          </div>

          {/* Expandable metadata */}
          {run.metadata && Object.keys(run.metadata).length > 0 && (
            <button
              onClick={() => setExpanded(!expanded)}
              aria-expanded={expanded}
              className={cn(
                "mt-2 font-mono text-xs text-tx-muted hover:text-tx-secondary",
                "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand rounded"
              )}
            >
              {expanded ? "Hide" : "Show"} details
            </button>
          )}

          <AnimatePresence>
            {expanded && (
              <motion.div
                initial={{ height: 0, opacity: 0 }}
                animate={{ height: "auto", opacity: 1 }}
                exit={{    height: 0, opacity: 0 }}
                transition={{ duration: 0.25 }}
                className="overflow-hidden"
              >
                <pre className="mt-2 rounded-xl bg-canvas p-3 font-mono text-xs text-tx-secondary overflow-x-auto">
                  {JSON.stringify(run.metadata, null, 2)}
                </pre>
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      </div>

      {/* Action bar */}
      <div className={cn(
        "flex gap-2 border-t border-border px-5 py-3",
        "bg-elevated/40 rounded-b-2xl"
      )}>
        <Button
          variant="success"
          size="sm"
          loading={loading}
          onClick={() => onApprove(run.id)}
          aria-label={`Approve ${run.workflow_id}`}
          className="flex-1"
        >
          <Check size={14} aria-hidden="true" />
          Approve
        </Button>
        <Button
          variant="danger"
          size="sm"
          loading={loading}
          onClick={() => onReject(run.id)}
          aria-label={`Reject ${run.workflow_id}`}
          className="flex-1"
        >
          <X size={14} aria-hidden="true" />
          Reject
        </Button>
      </div>
    </motion.article>
  );
}

export default function Approvals() {
  const qc = useQueryClient();

  const { data: runs = [], isLoading } = useQuery({
    queryKey:        ["agent-runs"],
    queryFn:         agentApi.runs,
    refetchInterval: 10_000,
    select:          (data) => data.filter((r) => r.status === "pending"),
  });

  const approveMutation = useMutation({
    mutationFn: agentApi.approve,
    onSuccess:  () => qc.invalidateQueries({ queryKey: ["agent-runs"] }),
  });

  const rejectMutation = useMutation({
    mutationFn: agentApi.reject,
    onSuccess:  () => qc.invalidateQueries({ queryKey: ["agent-runs"] }),
  });

  const loading = approveMutation.isPending || rejectMutation.isPending;

  return (
    <PageTransition>
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="font-heading font-extrabold text-2xl text-tx-primary">Approvals</h1>
          <p className="font-body text-sm text-tx-secondary mt-0.5">
            Human-in-the-loop confirmations for AI actions
          </p>
        </div>
        {runs.length > 0 && (
          <StatusBadge status="warn" size="md" dot pulse>
            {runs.length} pending
          </StatusBadge>
        )}
      </div>

      <div className="space-y-3" role="list" aria-label="Pending approvals" aria-live="polite">
        {isLoading
          ? Array.from({ length: 2 }).map((_, i) => <SkeletonRow key={i} />)
          : runs.length === 0
          ? (
            <div className="flex flex-col items-center gap-3 rounded-2xl border border-dashed border-border py-20 text-center">
              <CheckSquare size={40} className="text-status-good" aria-hidden="true" />
              <p className="font-heading font-semibold text-tx-secondary">All caught up!</p>
              <p className="font-body text-sm text-tx-muted">
                No pending approvals at this time
              </p>
            </div>
          )
          : (
            <AnimatePresence>
              {runs.map((run) => (
                <div key={run.id} role="listitem">
                  <ApprovalCard
                    run={run}
                    onApprove={(id) => approveMutation.mutate(id)}
                    onReject={(id)  => rejectMutation.mutate(id)}
                    loading={loading}
                  />
                </div>
              ))}
            </AnimatePresence>
          )
        }
      </div>
    </PageTransition>
  );
}
