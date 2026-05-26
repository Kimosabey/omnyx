import { config } from "@/config";
import { getToken } from "@/lib/keycloak";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const token = getToken();
  const headers: HeadersInit = {
    "Content-Type": "application/json",
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
    ...init?.headers,
  };

  const res = await fetch(`${config.apiBase}${path}`, { ...init, headers });

  if (!res.ok) {
    const body = await res.text().catch(() => "");
    throw new Error(`API ${res.status}: ${body || res.statusText}`);
  }

  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

export const api = {
  get:    <T>(path: string) => request<T>(path),
  post:   <T>(path: string, body: unknown) => request<T>(path, { method: "POST",   body: JSON.stringify(body) }),
  patch:  <T>(path: string, body: unknown) => request<T>(path, { method: "PATCH",  body: JSON.stringify(body) }),
  delete: <T>(path: string)                => request<T>(path, { method: "DELETE" }),
};

// ── Typed endpoints ───────────────────────────────────────────────────────

export interface Equipment {
  id: string;
  name: string;
  tag_id: string;
  type: string;
  location: string;
  status: string;
  tenant_id: string;
}

export interface LatestReading {
  point_id: string;
  device_id: string;
  value_num: number | null;
  quality_flag: string;
  measured_at: string;
  unit: string;
}

export interface Alert {
  id: string;
  alert_rule_id: string;
  equipment_id: string | null;
  tenant_id: string;
  severity: string;
  title: string;
  description: string;
  status: string;
  triggered_at: string;
  acknowledged_at: string | null;
  resolved_at: string | null;
  metadata: Record<string, unknown>;
}

export interface WorkOrder {
  id: string;
  title: string;
  description: string;
  status: string;
  priority: string;
  assigned_to: string | null;
  equipment_id: string | null;
  alert_id: string | null;
  tenant_id: string;
  created_at: string;
  due_at: string | null;
  completed_at: string | null;
}

export interface AgentRun {
  id: string;
  workflow_id: string;
  tenant_id: string;
  status: string;
  triggered_by: string;
  started_at: string;
  finished_at: string | null;
  metadata: Record<string, unknown>;
}

export interface Notification {
  id: string;
  tenant_id: string;
  user_id: string;
  type: string;
  title: string;
  body: string;
  read_at: string | null;
  created_at: string;
  metadata: Record<string, unknown>;
}

export const equipmentApi = {
  list:   ()         => api.get<Equipment[]>("/api/v1/equipment"),
  get:    (id: string) => api.get<Equipment>(`/api/v1/equipment/${id}`),
  latest: (id: string) => api.get<LatestReading[]>(`/api/v1/equipment/${id}/readings/latest`),
};

export const alertsApi = {
  list:        ()           => api.get<Alert[]>("/api/v1/alerts"),
  acknowledge: (id: string) => api.post<Alert>(`/api/v1/alerts/${id}/acknowledge`, {}),
  resolve:     (id: string) => api.post<Alert>(`/api/v1/alerts/${id}/resolve`, {}),
};

export const workOrdersApi = {
  list:   ()                       => api.get<WorkOrder[]>("/api/v1/work-orders"),
  create: (body: Partial<WorkOrder>) => api.post<WorkOrder>("/api/v1/work-orders", body),
  update: (id: string, body: Partial<WorkOrder>) => api.patch<WorkOrder>(`/api/v1/work-orders/${id}`, body),
};

export const agentApi = {
  runs:    ()          => api.get<AgentRun[]>("/api/v1/agent/runs"),
  approve: (id: string) => api.post<void>(`/api/v1/approvals/${id}/approve`, {}),
  reject:  (id: string) => api.post<void>(`/api/v1/approvals/${id}/reject`, {}),
};

export const notificationsApi = {
  list:    ()           => api.get<Notification[]>("/api/v1/notifications"),
  read:    (id: string)  => api.post<void>(`/api/v1/notifications/${id}/read`, {}),
  readAll: ()            => api.post<void>("/api/v1/notifications/read-all", {}),
};
