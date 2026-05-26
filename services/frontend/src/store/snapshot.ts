import { create } from "zustand";

export interface PointValue {
  v: number | null;
  q: string;
  t: string;
}

export interface PlantSnapshot {
  ts:        string;
  tenant_id: string;
  devices:   Record<string, Record<string, PointValue>>;
}

interface SnapshotState {
  snapshot:    PlantSnapshot | null;
  isConnected: boolean;
  lastUpdated: number | null;

  setSnapshot:  (s: PlantSnapshot | null) => void;
  setConnected: (v: boolean)             => void;
  getDevice:    (deviceId: string)       => Record<string, PointValue> | null;
  deviceIds:    ()                       => string[];
}

export const useSnapshotStore = create<SnapshotState>((set, get) => ({
  snapshot:    null,
  isConnected: false,
  lastUpdated: null,

  setSnapshot:  (snapshot)   => set({ snapshot, lastUpdated: Date.now() }),
  setConnected: (isConnected) => set({ isConnected }),
  getDevice: (deviceId) => get().snapshot?.devices[deviceId] ?? null,
  deviceIds: () => Object.keys(get().snapshot?.devices ?? {}),
}));
