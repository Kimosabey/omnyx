/**
 * In-memory PlantSnapshot store.
 * Kafka consumer calls update() per reading.
 * WS broadcaster calls get() every 5 s.
 */
export interface PointValue {
  v: number | null;
  q: string;         // quality_flag
  t: string;         // ISO timestamp
}

export interface PlantSnapshot {
  ts: string;
  tenant_id: string;
  devices: Record<string, Record<string, PointValue>>;
}

// latest[device_id][point_id] = PointValue
const latest: Record<string, Record<string, PointValue>> = {};

export function update(msg: Record<string, unknown>): void {
  const deviceId = msg.device_id as string;
  const pointId  = msg.point_id  as string;
  if (!deviceId || !pointId) return;

  if (!latest[deviceId]) latest[deviceId] = {};
  latest[deviceId][pointId] = {
    v: msg.value_num as number | null,
    q: (msg.quality_flag as string) ?? "GOOD",
    t: (msg.measured_at as string) ?? new Date().toISOString(),
  };
}

export function get(tenantId: string): PlantSnapshot {
  return {
    ts:        new Date().toISOString(),
    tenant_id: tenantId,
    devices:   structuredClone(latest),
  };
}

export function deviceCount(): number {
  return Object.keys(latest).length;
}

export function pointCount(): number {
  return Object.values(latest).reduce((s, pts) => s + Object.keys(pts).length, 0);
}
