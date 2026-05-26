import { useQuery } from "@tanstack/react-query";
import { motion } from "framer-motion";
import { Cpu, Bell, ClipboardList, Wifi } from "lucide-react";
import { useMemo } from "react";
import PageTransition from "@/components/layout/PageTransition";
import KpiCard from "@/components/ui/KpiCard";
import Card, { CardHeader, CardTitle } from "@/components/ui/Card";
import AlertRow from "@/components/ui/AlertRow";
import LivePulse from "@/components/ui/LivePulse";
import TelemetryChart, { type DataPoint } from "@/components/ui/TelemetryChart";
import { equipmentApi, alertsApi, workOrdersApi } from "@/lib/api";
import { useSnapshotStore } from "@/store/snapshot";

const staggerContainer = {
  animate: { transition: { staggerChildren: 0.08 } },
};

export default function Dashboard() {
  const { data: equipment  = [], isLoading: eqLoading  } = useQuery({ queryKey: ["equipment"],   queryFn: equipmentApi.list,  refetchInterval: 60_000 });
  const { data: alerts     = [], isLoading: alLoading  } = useQuery({ queryKey: ["alerts"],      queryFn: alertsApi.list,     refetchInterval: 30_000 });
  const { data: workOrders = [], isLoading: woLoading  } = useQuery({ queryKey: ["work-orders"], queryFn: workOrdersApi.list, refetchInterval: 60_000 });

  const snapshot    = useSnapshotStore((s) => s.snapshot);
  const isConnected = useSnapshotStore((s) => s.isConnected);

  const openAlerts    = alerts.filter((a) => a.status === "open");
  const criticalCount = openAlerts.filter((a) => a.severity === "critical").length;
  const openWOs       = workOrders.filter((w) => w.status !== "closed" && w.status !== "completed").length;
  const deviceCount   = Object.keys(snapshot?.devices ?? {}).length;

  // Build sparkline data from snapshot point history (flatten first 50 points as demo)
  const chartData = useMemo<DataPoint[]>(() => {
    if (!snapshot) return [];
    const pts: DataPoint[] = [];
    for (const [, points] of Object.entries(snapshot.devices).slice(0, 3)) {
      for (const [pid, pv] of Object.entries(points).slice(0, 20)) {
        if (pv.v !== null) pts.push({ t: pv.t, v: pv.v, name: pid });
      }
    }
    return pts.sort((a, b) => new Date(a.t).getTime() - new Date(b.t).getTime()).slice(-60);
  }, [snapshot]);

  return (
    <PageTransition>
      {/* Page header */}
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="font-heading font-extrabold text-2xl text-tx-primary">Dashboard</h1>
          <p className="font-body text-sm text-tx-secondary mt-0.5">
            Live plant overview · THERMYNX HVAC
          </p>
        </div>
        <div className="flex items-center gap-2">
          <LivePulse active={isConnected} label={isConnected ? "WebSocket live" : "Reconnecting"} />
          <span className="font-mono text-xs text-tx-muted">
            {isConnected ? "WS Connected" : "Reconnecting…"}
          </span>
        </div>
      </div>

      {/* KPI Grid */}
      <motion.div
        variants={staggerContainer}
        initial="initial"
        animate="animate"
        className="grid grid-cols-2 gap-4 mb-6 lg:grid-cols-4"
      >
        <KpiCard
          title="Active Devices"
          value={deviceCount}
          icon={Cpu}
          status={deviceCount > 0 ? "good" : "bad"}
          loading={eqLoading}
        />
        <KpiCard
          title="Equipment"
          value={equipment.length}
          icon={Cpu}
          loading={eqLoading}
        />
        <KpiCard
          title="Open Alerts"
          value={openAlerts.length}
          icon={Bell}
          status={criticalCount > 0 ? "bad" : openAlerts.length > 0 ? "warn" : "good"}
          loading={alLoading}
        />
        <KpiCard
          title="Open Work Orders"
          value={openWOs}
          icon={ClipboardList}
          status={openWOs > 5 ? "warn" : "good"}
          loading={woLoading}
        />
      </motion.div>

      {/* Charts + Alerts row */}
      <div className="grid gap-4 lg:grid-cols-3">
        {/* Live telemetry chart — 2/3 width */}
        <Card className="lg:col-span-2" padding="md">
          <CardHeader>
            <CardTitle as="h2">Live Telemetry Feed</CardTitle>
            <div className="flex items-center gap-2">
              <LivePulse active={isConnected} size="sm" />
              <span className="font-mono text-xs text-tx-muted">
                {snapshot
                  ? `${Object.values(snapshot.devices).reduce((s, pts) => s + Object.keys(pts).length, 0)} points`
                  : "No data"}
              </span>
            </div>
          </CardHeader>
          <TelemetryChart
            data={chartData}
            label="Sensor Value"
            loading={!snapshot && isConnected}
            height={240}
          />
        </Card>

        {/* Recent critical alerts — 1/3 width */}
        <Card padding="md">
          <CardHeader>
            <CardTitle as="h2">Critical Alerts</CardTitle>
            {criticalCount > 0 && (
              <span className="font-mono text-xs text-status-bad">{criticalCount} critical</span>
            )}
          </CardHeader>

          <div className="flex flex-col gap-2" role="list" aria-label="Critical alerts">
            {alLoading
              ? Array.from({ length: 3 }).map((_, i) => (
                  <div key={i} className="shimmer h-20 rounded-xl" aria-hidden="true" />
                ))
              : openAlerts.filter((a) => a.severity === "critical" || a.severity === "high").slice(0, 4).map((alert) => (
                  <div key={alert.id} role="listitem">
                    <AlertRow alert={alert} />
                  </div>
                ))
            }
            {!alLoading && openAlerts.length === 0 && (
              <div className="flex flex-col items-center justify-center gap-2 py-8 text-center">
                <span className="text-2xl" aria-hidden="true">✓</span>
                <p className="font-body text-sm text-tx-muted">All clear — no active alerts</p>
              </div>
            )}
          </div>
        </Card>
      </div>

      {/* Device snapshot table */}
      {snapshot && (
        <Card className="mt-4" padding="md">
          <CardHeader>
            <CardTitle as="h2">Device Snapshot</CardTitle>
            <div className="flex items-center gap-1 text-xs text-tx-muted font-mono">
              <Wifi size={12} aria-hidden="true" />
              {snapshot.ts ? new Date(snapshot.ts).toLocaleTimeString() : "—"}
            </div>
          </CardHeader>

          <div className="overflow-x-auto -mx-1">
            <table className="w-full text-sm" aria-label="Device snapshot data">
              <thead>
                <tr className="border-b border-border">
                  {["Device", "Points", "Good", "Bad"].map((h) => (
                    <th
                      key={h}
                      scope="col"
                      className="px-3 py-2 text-left font-mono text-xs font-medium text-tx-muted uppercase tracking-widest"
                    >
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {Object.entries(snapshot.devices).slice(0, 11).map(([ddc, points]) => {
                  const vals   = Object.values(points);
                  const good   = vals.filter((p) => p.q === "GOOD").length;
                  const bad    = vals.length - good;
                  return (
                    <tr key={ddc} className="hover:bg-elevated/50 transition-colors duration-150">
                      <td className="px-3 py-2 font-mono text-xs text-tx-primary">{ddc}</td>
                      <td className="px-3 py-2 font-mono text-xs text-tx-secondary">{vals.length}</td>
                      <td className="px-3 py-2 font-mono text-xs text-status-good">{good}</td>
                      <td className="px-3 py-2 font-mono text-xs text-status-bad">{bad > 0 ? bad : "—"}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </Card>
      )}
    </PageTransition>
  );
}
