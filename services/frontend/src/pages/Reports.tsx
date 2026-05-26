import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { BarChart3, Download, Calendar } from "lucide-react";
import PageTransition from "@/components/layout/PageTransition";
import Card, { CardHeader, CardTitle } from "@/components/ui/Card";
import Button from "@/components/ui/Button";
import TelemetryChart, { type DataPoint } from "@/components/ui/TelemetryChart";
import { api } from "@/lib/api";
import { cn } from "@/lib/utils";

type Resolution = "1m" | "5m" | "1h";

interface DailyReportPoint {
  bucket:     string;
  equipment_id: string;
  avg_value:  number;
  min_value:  number;
  max_value:  number;
}

const RESOLUTIONS: { value: Resolution; label: string }[] = [
  { value: "1m", label: "1 min" },
  { value: "5m", label: "5 min" },
  { value: "1h", label: "1 hour" },
];

export default function Reports() {
  const [resolution, setResolution] = useState<Resolution>("5m");
  const today = new Date().toISOString().split("T")[0];

  const { data: daily = [], isLoading } = useQuery({
    queryKey: ["reports", "daily", today, resolution],
    queryFn:  () => api.get<DailyReportPoint[]>(`/api/v1/reports/daily?date=${today}&resolution=${resolution}`),
    staleTime: 5 * 60_000,
  });

  // Group by equipment, build chart series
  const byEquipment = daily.reduce<Record<string, DataPoint[]>>((acc, p) => {
    if (!acc[p.equipment_id]) acc[p.equipment_id] = [];
    acc[p.equipment_id].push({ t: p.bucket, v: p.avg_value });
    return acc;
  }, {});

  const equipmentIds = Object.keys(byEquipment).slice(0, 4);

  return (
    <PageTransition>
      <div className="mb-6 flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="font-heading font-extrabold text-2xl text-tx-primary">Reports</h1>
          <p className="font-body text-sm text-tx-secondary mt-0.5">
            Historical telemetry and analytics
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="secondary" size="sm" aria-label="Export report data">
            <Download size={14} aria-hidden="true" />
            Export
          </Button>
        </div>
      </div>

      {/* Controls */}
      <Card padding="sm" className="mb-4">
        <div className="flex flex-wrap items-center gap-4">
          <div className="flex items-center gap-2">
            <Calendar size={14} className="text-tx-muted" aria-hidden="true" />
            <span className="font-body text-sm text-tx-secondary font-medium">Today</span>
            <span className="font-mono text-xs text-tx-muted">{today}</span>
          </div>

          {/* Resolution selector */}
          <fieldset className="flex items-center gap-1">
            <legend className="sr-only">Chart resolution</legend>
            {RESOLUTIONS.map(({ value, label }) => (
              <button
                key={value}
                onClick={() => setResolution(value)}
                aria-pressed={resolution === value}
                className={cn(
                  "rounded-lg px-3 py-1.5 font-mono text-xs font-medium transition-all duration-200",
                  "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand",
                  resolution === value
                    ? "bg-brand text-white shadow-glow-sm"
                    : "text-tx-muted hover:text-tx-secondary hover:bg-elevated"
                )}
              >
                {label}
              </button>
            ))}
          </fieldset>
        </div>
      </Card>

      {/* Charts grid */}
      {isLoading ? (
        <div className="grid gap-4 sm:grid-cols-2">
          {Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="shimmer rounded-2xl h-60" aria-hidden="true" />
          ))}
        </div>
      ) : equipmentIds.length === 0 ? (
        <div className="flex flex-col items-center gap-3 rounded-2xl border border-dashed border-border py-20 text-center">
          <BarChart3 size={40} className="text-tx-muted" aria-hidden="true" />
          <p className="font-heading font-semibold text-tx-secondary">No report data</p>
          <p className="font-body text-sm text-tx-muted">Historical data will appear here as telemetry is collected</p>
        </div>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2">
          {equipmentIds.map((eqId) => (
            <Card key={eqId} padding="md">
              <CardHeader>
                <CardTitle as="h3" className="text-sm truncate">{eqId}</CardTitle>
                <span className="font-mono text-xs text-tx-muted">{resolution} avg</span>
              </CardHeader>
              <TelemetryChart
                data={byEquipment[eqId]}
                label="Avg Value"
                height={180}
                smooth
                areaFill
              />
            </Card>
          ))}
        </div>
      )}
    </PageTransition>
  );
}
