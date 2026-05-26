import { type ClassValue, clsx } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function formatValue(v: number | null, unit?: string): string {
  if (v === null || v === undefined) return "—";
  const formatted = Number.isInteger(v) ? v.toString() : v.toFixed(2);
  return unit ? `${formatted} ${unit}` : formatted;
}

export function formatTimestamp(iso: string): string {
  return new Date(iso).toLocaleString("en-US", {
    month: "short",
    day:   "numeric",
    hour:  "2-digit",
    minute:"2-digit",
    hour12: false,
  });
}

export function formatRelativeTime(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime();
  if (diff < 60_000)  return "just now";
  if (diff < 3_600_000) return `${Math.floor(diff / 60_000)}m ago`;
  if (diff < 86_400_000) return `${Math.floor(diff / 3_600_000)}h ago`;
  return `${Math.floor(diff / 86_400_000)}d ago`;
}

export function qualityToStatus(q: string): "good" | "warn" | "bad" {
  const s = q?.toUpperCase();
  if (s === "GOOD") return "good";
  if (s === "BAD" || s === "STALE" || s === "FROZEN") return "bad";
  return "warn";
}

export function clamp(value: number, min: number, max: number): number {
  return Math.min(Math.max(value, min), max);
}

export function sleep(ms: number) {
  return new Promise<void>((r) => setTimeout(r, ms));
}
