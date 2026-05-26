import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { motion } from "framer-motion";
import { Filter, RefreshCw } from "lucide-react";
import PageTransition from "@/components/layout/PageTransition";
import AlertRow from "@/components/ui/AlertRow";
import Button from "@/components/ui/Button";
import Card, { CardHeader, CardTitle } from "@/components/ui/Card";
import StatusBadge from "@/components/ui/StatusBadge";
import { SkeletonRow } from "@/components/ui/SkeletonLoader";
import { alertsApi } from "@/lib/api";
import { cn } from "@/lib/utils";

type Filter = "all" | "open" | "acknowledged" | "resolved";

const FILTERS: { value: Filter; label: string }[] = [
  { value: "all",          label: "All"          },
  { value: "open",         label: "Open"         },
  { value: "acknowledged", label: "Acknowledged" },
  { value: "resolved",     label: "Resolved"     },
];

export default function Alerts() {
  const [activeFilter, setActiveFilter] = useState<Filter>("open");
  const qc = useQueryClient();

  const { data: alerts = [], isLoading, isFetching, refetch } = useQuery({
    queryKey:       ["alerts"],
    queryFn:        alertsApi.list,
    refetchInterval: 30_000,
  });

  const ackMutation = useMutation({
    mutationFn: alertsApi.acknowledge,
    onSuccess:  () => qc.invalidateQueries({ queryKey: ["alerts"] }),
  });

  const resMutation = useMutation({
    mutationFn: alertsApi.resolve,
    onSuccess:  () => qc.invalidateQueries({ queryKey: ["alerts"] }),
  });

  const filtered = alerts.filter((a) => activeFilter === "all" || a.status === activeFilter);
  const counts = {
    open:         alerts.filter((a) => a.status === "open").length,
    acknowledged: alerts.filter((a) => a.status === "acknowledged").length,
    resolved:     alerts.filter((a) => a.status === "resolved").length,
  };

  return (
    <PageTransition>
      <div className="mb-6 flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="font-heading font-extrabold text-2xl text-tx-primary">Alerts</h1>
          <p className="font-body text-sm text-tx-secondary mt-0.5">
            Monitor and manage system alerts
          </p>
        </div>
        <Button
          variant="secondary"
          size="sm"
          onClick={() => refetch()}
          loading={isFetching}
          aria-label="Refresh alerts"
        >
          <RefreshCw size={14} aria-hidden="true" />
          Refresh
        </Button>
      </div>

      {/* Summary badges */}
      <div className="flex flex-wrap gap-3 mb-6" role="status" aria-live="polite">
        <StatusBadge status="bad"  size="md" dot pulse={counts.open > 0}>
          {counts.open} Open
        </StatusBadge>
        <StatusBadge status="info" size="md" dot>
          {counts.acknowledged} Acknowledged
        </StatusBadge>
        <StatusBadge status="good" size="md" dot>
          {counts.resolved} Resolved
        </StatusBadge>
      </div>

      <Card padding="none">
        {/* Filter tabs */}
        <div
          className="flex gap-1 border-b border-border px-4 pt-2"
          role="tablist"
          aria-label="Alert filters"
        >
          {FILTERS.map(({ value, label }) => (
            <button
              key={value}
              role="tab"
              aria-selected={activeFilter === value}
              aria-controls={`tab-panel-${value}`}
              onClick={() => setActiveFilter(value)}
              className={cn(
                "relative px-4 py-2.5 font-body text-sm font-medium rounded-t-lg",
                "transition-colors duration-200",
                "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand",
                activeFilter === value
                  ? "text-brand"
                  : "text-tx-muted hover:text-tx-secondary"
              )}
            >
              {label}
              {value !== "all" && counts[value as keyof typeof counts] > 0 && (
                <span className="ml-1.5 font-mono text-xs opacity-60">
                  {counts[value as keyof typeof counts]}
                </span>
              )}
              {activeFilter === value && (
                <motion.span
                  layoutId="alert-tab-indicator"
                  className="absolute bottom-0 left-0 right-0 h-0.5 bg-brand rounded-full"
                  transition={{ type: "spring", stiffness: 400, damping: 35 }}
                />
              )}
            </button>
          ))}
        </div>

        {/* Alert list */}
        <div
          id={`tab-panel-${activeFilter}`}
          role="tabpanel"
          aria-label={`${activeFilter} alerts`}
          className="p-4 space-y-2"
        >
          {isLoading
            ? Array.from({ length: 4 }).map((_, i) => <SkeletonRow key={i} />)
            : filtered.length === 0
            ? (
              <div className="flex flex-col items-center gap-3 py-16 text-center">
                <Filter size={32} className="text-tx-muted" aria-hidden="true" />
                <p className="font-heading font-semibold text-tx-secondary">No alerts</p>
                <p className="font-body text-sm text-tx-muted">No {activeFilter} alerts at this time</p>
              </div>
            )
            : filtered.map((alert) => (
              <AlertRow
                key={alert.id}
                alert={alert}
                onAcknowledge={alert.status === "open" ? (id) => ackMutation.mutate(id) : undefined}
                onResolve={alert.status === "open" ? (id) => resMutation.mutate(id) : undefined}
                loading={ackMutation.isPending || resMutation.isPending}
              />
            ))
          }
        </div>
      </Card>
    </PageTransition>
  );
}
