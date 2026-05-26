import { useMemo } from "react";
import ReactECharts from "echarts-for-react";
import { useThemeStore } from "@/store/theme";
import type { EChartsOption } from "echarts";

export interface DataPoint {
  t:    string;   // ISO timestamp
  v:    number;
  name?: string;
}

interface TelemetryChartProps {
  data:       DataPoint[];
  label?:     string;
  unit?:      string;
  color?:     string;
  height?:    number;
  showGrid?:  boolean;
  smooth?:    boolean;
  areaFill?:  boolean;
  loading?:   boolean;
  thresholdWarn?: number;
  thresholdBad?:  number;
}

const BRAND   = "rgba(31, 63, 254, 1)";
const BRAND_A = "rgba(31, 63, 254, 0.12)";
const WARN    = "rgba(251,191,36,0.8)";
const BAD     = "rgba(248,113,113,0.8)";

export default function TelemetryChart({
  data,
  label       = "Value",
  unit        = "",
  color       = BRAND,
  height      = 220,
  showGrid    = true,
  smooth      = true,
  areaFill    = true,
  loading     = false,
  thresholdWarn,
  thresholdBad,
}: TelemetryChartProps) {
  const { theme } = useThemeStore();
  const isDark = theme === "dark";

  const axisColor  = isDark ? "rgba(136,146,176,0.4)" : "rgba(100,116,139,0.3)";
  const labelColor = isDark ? "#8892B0" : "#475569";
  const bgColor    = "transparent";

  const option = useMemo<EChartsOption>(() => {
    const xs = data.map((d) => {
      const dt = new Date(d.t);
      return `${dt.getHours().toString().padStart(2, "0")}:${dt.getMinutes().toString().padStart(2, "0")}`;
    });
    const ys = data.map((d) => d.v);

    const markLines: EChartsOption["series"] extends Array<infer S>
      ? S extends { markLine?: infer ML } ? ML : never
      : never = thresholdWarn || thresholdBad
      ? {
          silent: true,
          lineStyle: { type: "dashed" },
          data: [
            ...(thresholdWarn
              ? [{ yAxis: thresholdWarn, name: "Warn", lineStyle: { color: WARN } }]
              : []),
            ...(thresholdBad
              ? [{ yAxis: thresholdBad,  name: "Bad",  lineStyle: { color: BAD  } }]
              : []),
          ],
        }
      : undefined;

    return {
      backgroundColor: bgColor,
      animation:       true,
      animationDuration: 800,
      animationEasing: "cubicOut",
      tooltip: {
        trigger:   "axis",
        backgroundColor: isDark ? "#131933" : "#ffffff",
        borderColor:     isDark ? "#1E2A4A" : "#E2E8F0",
        textStyle: { color: isDark ? "#F1F5FF" : "#0A0E1F", fontSize: 12 },
        formatter: (params: unknown) => {
          const p = (params as { name: string; value: number }[])[0];
          return `<b>${p?.name}</b><br/>${label}: ${p?.value?.toFixed(2)} ${unit}`;
        },
      },
      grid: {
        top: 12, bottom: 32, left: 48, right: 12,
        show: showGrid,
        borderColor: axisColor,
      },
      xAxis: {
        type:        "category",
        data:        xs,
        boundaryGap: false,
        axisLine:  { lineStyle: { color: axisColor } },
        axisTick:  { show: false },
        axisLabel: { color: labelColor, fontSize: 11, fontFamily: "JetBrains Mono" },
        splitLine: { show: false },
      },
      yAxis: {
        type:      "value",
        axisLine:  { show: false },
        axisTick:  { show: false },
        axisLabel: { color: labelColor, fontSize: 11, fontFamily: "JetBrains Mono",
          formatter: (v: number) => `${v}${unit ? ` ${unit}` : ""}` },
        splitLine: { lineStyle: { color: axisColor, type: "dashed" } },
      },
      series: [
        {
          name:      label,
          type:      "line",
          data:      ys,
          smooth,
          symbol:    "none",
          lineStyle: { color, width: 2 },
          areaStyle: areaFill
            ? { color: { type: "linear", x: 0, y: 0, x2: 0, y2: 1,
                colorStops: [
                  { offset: 0,   color: color.replace("1)", "0.2)") || BRAND_A },
                  { offset: 1,   color: "transparent" },
                ] } }
            : undefined,
          markLine: markLines,
        },
      ],
    };
  }, [data, label, unit, color, showGrid, smooth, areaFill, isDark, axisColor, labelColor, thresholdWarn, thresholdBad]);

  return (
    <ReactECharts
      option={option}
      style={{ height, width: "100%" }}
      showLoading={loading}
      loadingOption={{
        text:      "",
        color:     BRAND,
        maskColor: isDark ? "rgba(19,25,51,0.7)" : "rgba(255,255,255,0.7)",
      }}
      opts={{ renderer: "svg" }}
    />
  );
}
