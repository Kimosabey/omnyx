import { useEffect, useRef, useState } from "react";
import { motion } from "framer-motion";
import { TrendingUp, TrendingDown, Minus } from "lucide-react";
import Card from "./Card";
import { cn } from "@/lib/utils";

interface KpiCardProps {
  title:       string;
  value:       number | string;
  unit?:       string;
  trend?:      number;           // % change (positive = up, negative = down)
  trendLabel?: string;
  status?:     "good" | "warn" | "bad" | "neutral";
  icon?:       React.ElementType;
  animate?:    boolean;
  loading?:    boolean;
  className?:  string;
}

function AnimatedNumber({ target, duration = 1200 }: { target: number; duration?: number }) {
  const [current, setCurrent] = useState(0);
  const rafRef = useRef<number>();

  useEffect(() => {
    const start     = performance.now();
    const startVal  = current;
    const diff      = target - startVal;

    const tick = (now: number) => {
      const elapsed  = now - start;
      const progress = Math.min(elapsed / duration, 1);
      // Ease out expo
      const eased = progress === 1 ? 1 : 1 - Math.pow(2, -10 * progress);
      setCurrent(startVal + diff * eased);
      if (progress < 1) rafRef.current = requestAnimationFrame(tick);
    };

    rafRef.current = requestAnimationFrame(tick);
    return () => { if (rafRef.current) cancelAnimationFrame(rafRef.current); };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [target]);

  return <>{Number.isInteger(target) ? Math.round(current) : current.toFixed(1)}</>;
}

const statusGlowMap: Record<string, string> = {
  good:    "shadow-status-good",
  warn:    "",
  bad:     "shadow-status-bad",
  neutral: "",
};

const statusTextMap: Record<string, string> = {
  good:    "text-status-good",
  warn:    "text-status-warn",
  bad:     "text-status-bad",
  neutral: "text-tx-primary",
};

export default function KpiCard({
  title,
  value,
  unit,
  trend,
  trendLabel,
  status    = "neutral",
  icon: Icon,
  animate   = true,
  loading   = false,
  className,
}: KpiCardProps) {
  const isNumeric = typeof value === "number";

  if (loading) {
    return (
      <Card className={cn("min-h-[120px]", className)}>
        <div className="space-y-3">
          <div className="shimmer h-4 w-24 rounded-lg" />
          <div className="shimmer h-8 w-32 rounded-xl" />
          <div className="shimmer h-3 w-16 rounded" />
        </div>
      </Card>
    );
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4, ease: [0.16, 1, 0.3, 1] }}
    >
      <Card
        className={cn(
          "relative overflow-hidden transition-shadow duration-300",
          statusGlowMap[status],
          className
        )}
        hover
      >
        {/* Icon accent */}
        {Icon && (
          <span
            className="absolute top-4 right-4 opacity-10"
            aria-hidden="true"
          >
            <Icon size={48} className="text-brand" />
          </span>
        )}

        <p className="font-body text-xs font-medium text-tx-secondary uppercase tracking-wider mb-2">
          {title}
        </p>

        <div className="flex items-baseline gap-2">
          <span
            className={cn(
              "font-heading font-extrabold text-3xl tabular-nums",
              statusTextMap[status]
            )}
            aria-label={`${title}: ${value}${unit ? ` ${unit}` : ""}`}
          >
            {isNumeric && animate
              ? <AnimatedNumber target={value as number} />
              : value
            }
          </span>
          {unit && (
            <span className="font-mono text-sm text-tx-muted">{unit}</span>
          )}
        </div>

        {trend !== undefined && (
          <div className="flex items-center gap-1 mt-2">
            {trend > 0  && <TrendingUp  size={12} className="text-status-good" aria-hidden="true" />}
            {trend < 0  && <TrendingDown size={12} className="text-status-bad"  aria-hidden="true" />}
            {trend === 0 && <Minus       size={12} className="text-tx-muted"    aria-hidden="true" />}
            <span
              className={cn(
                "font-mono text-xs font-medium",
                trend > 0  && "text-status-good",
                trend < 0  && "text-status-bad",
                trend === 0 && "text-tx-muted"
              )}
            >
              {trend > 0 ? "+" : ""}{trend.toFixed(1)}%
            </span>
            {trendLabel && (
              <span className="font-body text-xs text-tx-muted">{trendLabel}</span>
            )}
          </div>
        )}
      </Card>
    </motion.div>
  );
}
