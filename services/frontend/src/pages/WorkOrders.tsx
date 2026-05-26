import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { motion } from "framer-motion";
import { Plus, ClipboardList, Calendar, User, AlertTriangle } from "lucide-react";
import * as Dialog from "@radix-ui/react-dialog";
import * as VisuallyHidden from "@radix-ui/react-visually-hidden";
import PageTransition from "@/components/layout/PageTransition";
import Card from "@/components/ui/Card";
import Button from "@/components/ui/Button";
import StatusBadge from "@/components/ui/StatusBadge";
import { SkeletonRow } from "@/components/ui/SkeletonLoader";
import { workOrdersApi, type WorkOrder } from "@/lib/api";
import { formatRelativeTime } from "@/lib/utils";
import { cn } from "@/lib/utils";

const priorityStatusMap: Record<string, "bad" | "warn" | "info" | "muted"> = {
  critical: "bad",
  high:     "warn",
  medium:   "info",
  low:      "muted",
};

const statusMap: Record<string, "good" | "info" | "warn" | "muted"> = {
  open:        "warn",
  in_progress: "info",
  completed:   "good",
  closed:      "muted",
};

function WorkOrderRow({ wo, onUpdate }: { wo: WorkOrder; onUpdate: (id: string, status: string) => void }) {
  return (
    <motion.article
      layout
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      className={cn(
        "flex flex-wrap items-start gap-3 rounded-xl border border-border bg-card p-4",
        "transition-colors duration-200 hover:border-border/60"
      )}
      aria-label={`Work order: ${wo.title}`}
    >
      <span className="flex h-9 w-9 items-center justify-center rounded-xl bg-elevated shrink-0" aria-hidden="true">
        <ClipboardList size={16} className="text-tx-secondary" />
      </span>

      <div className="flex-1 min-w-0">
        <div className="flex flex-wrap items-center gap-2 mb-1">
          <p className="font-heading font-semibold text-sm text-tx-primary">{wo.title}</p>
          <StatusBadge status={priorityStatusMap[wo.priority] ?? "muted"} size="xs" dot>
            {wo.priority}
          </StatusBadge>
          <StatusBadge status={statusMap[wo.status] ?? "muted"} size="xs">
            {wo.status.replace("_", " ")}
          </StatusBadge>
        </div>

        {wo.description && (
          <p className="font-body text-xs text-tx-secondary line-clamp-2 mb-2">{wo.description}</p>
        )}

        <div className="flex flex-wrap items-center gap-3 text-xs text-tx-muted">
          {wo.assigned_to && (
            <span className="flex items-center gap-1">
              <User size={10} aria-label="Assigned to" /> {wo.assigned_to}
            </span>
          )}
          {wo.due_at && (
            <span className="flex items-center gap-1">
              <Calendar size={10} aria-label="Due" />
              <time dateTime={wo.due_at}>{formatRelativeTime(wo.due_at)}</time>
            </span>
          )}
          <span className="flex items-center gap-1">
            Created {formatRelativeTime(wo.created_at)}
          </span>
        </div>
      </div>

      {/* Status actions */}
      {wo.status === "open" && (
        <Button
          size="xs"
          variant="secondary"
          onClick={() => onUpdate(wo.id, "in_progress")}
          aria-label={`Start work on: ${wo.title}`}
        >
          Start
        </Button>
      )}
      {wo.status === "in_progress" && (
        <Button
          size="xs"
          variant="success"
          onClick={() => onUpdate(wo.id, "completed")}
          aria-label={`Mark complete: ${wo.title}`}
        >
          Complete
        </Button>
      )}
    </motion.article>
  );
}

function CreateWorkOrderDialog({ open, onClose }: { open: boolean; onClose: () => void }) {
  const qc = useQueryClient();
  const [title,       setTitle]       = useState("");
  const [description, setDescription] = useState("");
  const [priority,    setPriority]    = useState("medium");

  const createMutation = useMutation({
    mutationFn: workOrdersApi.create,
    onSuccess:  () => {
      qc.invalidateQueries({ queryKey: ["work-orders"] });
      onClose();
      setTitle(""); setDescription(""); setPriority("medium");
    },
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!title.trim()) return;
    createMutation.mutate({ title, description, priority, status: "open" });
  };

  return (
    <Dialog.Root open={open} onOpenChange={(o) => !o && onClose()}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm" />
        <Dialog.Content
          className={cn(
            "fixed left-1/2 top-1/2 z-50 -translate-x-1/2 -translate-y-1/2",
            "w-full max-w-md rounded-2xl border border-border bg-card p-6 shadow-card",
            "focus:outline-none"
          )}
          aria-describedby="create-wo-desc"
        >
          <Dialog.Title className="font-heading font-bold text-lg text-tx-primary mb-1">
            New Work Order
          </Dialog.Title>
          <VisuallyHidden.Root>
            <Dialog.Description id="create-wo-desc">
              Create a new work order with title, description, and priority.
            </Dialog.Description>
          </VisuallyHidden.Root>

          <form onSubmit={handleSubmit} className="mt-4 space-y-4">
            <div>
              <label htmlFor="wo-title" className="block font-body text-xs font-medium text-tx-secondary mb-1.5">
                Title <span aria-hidden="true">*</span>
                <span className="sr-only">(required)</span>
              </label>
              <input
                id="wo-title"
                required
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                placeholder="Describe the work needed…"
                className={cn(
                  "w-full rounded-xl border border-border bg-elevated px-3 py-2.5",
                  "font-body text-sm text-tx-primary placeholder:text-tx-muted",
                  "focus:outline-none focus:ring-2 focus:ring-brand focus:border-transparent"
                )}
              />
            </div>

            <div>
              <label htmlFor="wo-desc" className="block font-body text-xs font-medium text-tx-secondary mb-1.5">
                Description
              </label>
              <textarea
                id="wo-desc"
                rows={3}
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder="Additional details…"
                className={cn(
                  "w-full rounded-xl border border-border bg-elevated px-3 py-2.5 resize-none",
                  "font-body text-sm text-tx-primary placeholder:text-tx-muted",
                  "focus:outline-none focus:ring-2 focus:ring-brand focus:border-transparent"
                )}
              />
            </div>

            <div>
              <label htmlFor="wo-priority" className="block font-body text-xs font-medium text-tx-secondary mb-1.5">
                Priority
              </label>
              <select
                id="wo-priority"
                value={priority}
                onChange={(e) => setPriority(e.target.value)}
                className={cn(
                  "w-full rounded-xl border border-border bg-elevated px-3 py-2.5",
                  "font-body text-sm text-tx-primary",
                  "focus:outline-none focus:ring-2 focus:ring-brand focus:border-transparent"
                )}
              >
                <option value="low">Low</option>
                <option value="medium">Medium</option>
                <option value="high">High</option>
                <option value="critical">Critical</option>
              </select>
            </div>

            <div className="flex gap-3 pt-2">
              <Button type="button" variant="secondary" className="flex-1" onClick={onClose}>
                Cancel
              </Button>
              <Button
                type="submit"
                className="flex-1"
                loading={createMutation.isPending}
                disabled={!title.trim()}
              >
                Create
              </Button>
            </div>
          </form>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}

export default function WorkOrders() {
  const [createOpen, setCreateOpen] = useState(false);
  const qc = useQueryClient();

  const { data: workOrders = [], isLoading } = useQuery({
    queryKey: ["work-orders"],
    queryFn:  workOrdersApi.list,
    refetchInterval: 60_000,
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, status }: { id: string; status: string }) =>
      workOrdersApi.update(id, { status }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["work-orders"] }),
  });

  const open = workOrders.filter((w) => w.status === "open").length;
  const inProgress = workOrders.filter((w) => w.status === "in_progress").length;

  return (
    <PageTransition>
      <div className="mb-6 flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="font-heading font-extrabold text-2xl text-tx-primary">Work Orders</h1>
          <p className="font-body text-sm text-tx-secondary mt-0.5">
            {open} open · {inProgress} in progress
          </p>
        </div>
        <Button onClick={() => setCreateOpen(true)} aria-label="Create new work order">
          <Plus size={16} aria-hidden="true" />
          New Work Order
        </Button>
      </div>

      <Card padding="none">
        <div className="p-4 space-y-2" role="list" aria-label="Work orders">
          {isLoading
            ? Array.from({ length: 4 }).map((_, i) => <SkeletonRow key={i} />)
            : workOrders.length === 0
            ? (
              <div className="flex flex-col items-center gap-3 py-16 text-center">
                <ClipboardList size={32} className="text-tx-muted" aria-hidden="true" />
                <p className="font-heading font-semibold text-tx-secondary">No work orders</p>
                <Button onClick={() => setCreateOpen(true)}>
                  <Plus size={14} aria-hidden="true" /> Create first work order
                </Button>
              </div>
            )
            : workOrders.map((wo) => (
              <div key={wo.id} role="listitem">
                <WorkOrderRow
                  wo={wo}
                  onUpdate={(id, status) => updateMutation.mutate({ id, status })}
                />
              </div>
            ))
          }
        </div>
      </Card>

      <CreateWorkOrderDialog open={createOpen} onClose={() => setCreateOpen(false)} />
    </PageTransition>
  );
}
