import { motion } from "framer-motion";
import { cn } from "@/lib/utils";

interface LivePulseProps {
  active?:    boolean;
  size?:      "sm" | "md" | "lg";
  label?:     string;
  className?: string;
}

const sizeMap = {
  sm: { dot: "h-2 w-2",   ring: "h-4 w-4"  },
  md: { dot: "h-2.5 w-2.5", ring: "h-5 w-5"},
  lg: { dot: "h-3 w-3",   ring: "h-6 w-6"  },
};

export default function LivePulse({
  active    = true,
  size      = "md",
  label,
  className,
}: LivePulseProps) {
  const { dot, ring } = sizeMap[size];

  return (
    <span
      className={cn("relative inline-flex items-center justify-center", className)}
      role="status"
      aria-label={label ?? (active ? "Live data active" : "Disconnected")}
    >
      {active && (
        <motion.span
          className={cn("absolute rounded-full bg-status-good/30", ring)}
          animate={{ scale: [1, 1.8], opacity: [0.6, 0] }}
          transition={{ duration: 1.5, repeat: Infinity, ease: "easeOut" }}
          aria-hidden="true"
        />
      )}
      <span
        className={cn(
          "relative rounded-full",
          dot,
          active ? "bg-status-good" : "bg-tx-muted"
        )}
        aria-hidden="true"
      />
    </span>
  );
}
