import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { motion } from "framer-motion";
import { Search, Cpu, MapPin, Tag } from "lucide-react";
import PageTransition from "@/components/layout/PageTransition";
import Card from "@/components/ui/Card";
import StatusBadge from "@/components/ui/StatusBadge";
import TelemetryChart, { type DataPoint } from "@/components/ui/TelemetryChart";
import { SkeletonCard } from "@/components/ui/SkeletonLoader";
import { equipmentApi, type Equipment } from "@/lib/api";
import { useSnapshotStore } from "@/store/snapshot";
import { qualityToStatus, formatValue } from "@/lib/utils";
import { cn } from "@/lib/utils";

function EquipmentCard({ eq, onClick, selected }: { eq: Equipment; onClick: () => void; selected: boolean }) {
  const snapshot = useSnapshotStore((s) => s.snapshot);
  const points   = snapshot?.devices[eq.tag_id] ?? {};
  const total    = Object.keys(points).length;
  const bad      = Object.values(points).filter((p) => p.q !== "GOOD").length;
  const status   = bad > 0 ? "bad" : total > 0 ? "good" : "muted";

  return (
    <button
      onClick={onClick}
      aria-label={`${eq.name} — ${eq.type} at ${eq.location}`}
      aria-pressed={selected}
      className={cn(
        "w-full text-left rounded-2xl border p-4 transition-all duration-200",
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand",
        selected
          ? "border-brand/50 bg-brand/5 shadow-glow-sm"
          : "border-border bg-card hover:border-brand/25 hover:bg-elevated"
      )}
    >
      <div className="flex items-start gap-3">
        <span
          className={cn(
            "flex h-10 w-10 items-center justify-center rounded-xl shrink-0",
            status === "bad"  ? "bg-status-bad/10"  :
            status === "good" ? "bg-status-good/10" :
                                "bg-elevated"
          )}
          aria-hidden="true"
        >
          <Cpu size={18} className={
            status === "bad"  ? "text-status-bad"  :
            status === "good" ? "text-status-good" :
                                "text-tx-muted"
          } />
        </span>

        <div className="flex-1 min-w-0">
          <p className="font-heading font-semibold text-sm text-tx-primary truncate">{eq.name}</p>
          <p className="font-mono text-xs text-tx-muted mt-0.5">{eq.tag_id}</p>
          <div className="flex items-center gap-1.5 mt-1.5">
            <MapPin size={10} className="text-tx-muted shrink-0" aria-hidden="true" />
            <span className="font-body text-xs text-tx-muted truncate">{eq.location}</span>
          </div>
        </div>

        <StatusBadge status={status} size="xs" dot>
          {bad > 0 ? `${bad} bad` : total > 0 ? "ok" : "no data"}
        </StatusBadge>
      </div>
    </button>
  );
}

function EquipmentDetail({ eq }: { eq: Equipment }) {
  const snapshot = useSnapshotStore((s) => s.snapshot);
  const points   = snapshot?.devices[eq.tag_id] ?? {};
  const entries  = Object.entries(points);

  const chartData: DataPoint[] = entries
    .filter(([, p]) => p.v !== null)
    .slice(0, 20)
    .map(([pid, p]) => ({ t: p.t, v: p.v as number, name: pid }));

  return (
    <motion.div
      key={eq.id}
      initial={{ opacity: 0, x: 20 }}
      animate={{ opacity: 1, x:  0 }}
      transition={{ duration: 0.35, ease: [0.16, 1, 0.3, 1] }}
      className="space-y-4"
    >
      {/* Header */}
      <Card padding="md">
        <div className="flex items-center gap-3 mb-4">
          <span className="flex h-12 w-12 items-center justify-center rounded-xl bg-brand/10 shrink-0" aria-hidden="true">
            <Cpu size={20} className="text-brand" />
          </span>
          <div>
            <h2 className="font-heading font-bold text-lg text-tx-primary">{eq.name}</h2>
            <div className="flex items-center gap-3 mt-0.5">
              <span className="flex items-center gap-1 font-mono text-xs text-tx-muted">
                <Tag size={10} aria-hidden="true" /> {eq.tag_id}
              </span>
              <span className="flex items-center gap-1 font-body text-xs text-tx-muted">
                <MapPin size={10} aria-hidden="true" /> {eq.location}
              </span>
            </div>
          </div>
        </div>
        <TelemetryChart data={chartData} label="Sensor" height={180} />
      </Card>

      {/* Point table */}
      <Card padding="none">
        <div className="px-5 py-3 border-b border-border">
          <h3 className="font-heading font-semibold text-sm text-tx-primary">
            Live Points ({entries.length})
          </h3>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm" aria-label={`Live points for ${eq.name}`}>
            <thead>
              <tr className="border-b border-border">
                {["Point", "Value", "Quality", "Updated"].map((h) => (
                  <th key={h} scope="col" className="px-4 py-2 text-left font-mono text-xs font-medium text-tx-muted uppercase tracking-wider">
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {entries.length === 0 ? (
                <tr>
                  <td colSpan={4} className="px-4 py-8 text-center font-body text-sm text-tx-muted">
                    No live data yet
                  </td>
                </tr>
              ) : entries.map(([pid, pv]) => {
                const status = qualityToStatus(pv.q);
                return (
                  <tr key={pid} className="hover:bg-elevated/40 transition-colors duration-150">
                    <td className="px-4 py-2 font-mono text-xs text-tx-primary">{pid}</td>
                    <td className="px-4 py-2 font-mono text-xs font-medium text-tx-primary">{formatValue(pv.v)}</td>
                    <td className="px-4 py-2">
                      <StatusBadge status={status} size="xs">{pv.q}</StatusBadge>
                    </td>
                    <td className="px-4 py-2 font-mono text-xs text-tx-muted">
                      {new Date(pv.t).toLocaleTimeString()}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </Card>
    </motion.div>
  );
}

export default function Equipment() {
  const [search,   setSearch]   = useState("");
  const [selected, setSelected] = useState<Equipment | null>(null);

  const { data: equipment = [], isLoading } = useQuery({
    queryKey: ["equipment"],
    queryFn:  equipmentApi.list,
    refetchInterval: 60_000,
  });

  const filtered = equipment.filter((eq) =>
    search === "" ||
    eq.name.toLowerCase().includes(search.toLowerCase()) ||
    eq.tag_id.toLowerCase().includes(search.toLowerCase())
  );

  return (
    <PageTransition>
      <div className="mb-6">
        <h1 className="font-heading font-extrabold text-2xl text-tx-primary">Equipment</h1>
        <p className="font-body text-sm text-tx-secondary mt-0.5">
          {equipment.length} devices · live monitoring
        </p>
      </div>

      <div className="grid gap-4 lg:grid-cols-2 xl:grid-cols-5">
        {/* Left: Equipment list */}
        <div className="xl:col-span-2 space-y-3">
          {/* Search */}
          <div className="relative">
            <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-tx-muted" aria-hidden="true" />
            <input
              type="search"
              placeholder="Search equipment…"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              aria-label="Search equipment"
              className={cn(
                "w-full rounded-xl border border-border bg-card pl-9 pr-4 py-2.5",
                "font-body text-sm text-tx-primary placeholder:text-tx-muted",
                "focus:outline-none focus:ring-2 focus:ring-brand focus:border-transparent",
                "transition-all duration-200"
              )}
            />
          </div>

          {/* List */}
          <div className="space-y-2" role="list" aria-label="Equipment list">
            {isLoading
              ? Array.from({ length: 5 }).map((_, i) => <SkeletonCard key={i} />)
              : filtered.map((eq) => (
                <div key={eq.id} role="listitem">
                  <EquipmentCard
                    eq={eq}
                    selected={selected?.id === eq.id}
                    onClick={() => setSelected(eq)}
                  />
                </div>
              ))
            }
          </div>
        </div>

        {/* Right: Detail panel */}
        <div className="xl:col-span-3">
          {selected
            ? <EquipmentDetail eq={selected} />
            : (
              <div className="flex h-64 items-center justify-center rounded-2xl border border-dashed border-border">
                <div className="text-center">
                  <Cpu size={32} className="mx-auto text-tx-muted mb-2" aria-hidden="true" />
                  <p className="font-body text-sm text-tx-muted">Select an equipment to view details</p>
                </div>
              </div>
            )
          }
        </div>
      </div>
    </PageTransition>
  );
}
