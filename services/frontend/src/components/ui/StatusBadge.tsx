import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

const badgeVariants = cva(
  "inline-flex items-center gap-1.5 rounded-full font-mono font-medium uppercase tracking-widest",
  {
    variants: {
      status: {
        good: "bg-status-good/10 text-status-good border border-status-good/20",
        warn: "bg-status-warn/10 text-status-warn border border-status-warn/20",
        bad:  "bg-status-bad/10  text-status-bad  border border-status-bad/20",
        info: "bg-status-info/10 text-status-info border border-status-info/20",
        muted:"bg-elevated text-tx-muted border border-border",
      },
      size: {
        xs:  "text-2xs px-2   py-0.5",
        sm:  "text-xs  px-2.5 py-1",
        md:  "text-xs  px-3   py-1",
      },
      dot: {
        true:  "",
        false: "",
      },
    },
    defaultVariants: {
      status: "muted",
      size: "sm",
      dot: false,
    },
  }
);

interface StatusBadgeProps extends VariantProps<typeof badgeVariants> {
  className?: string;
  children:   React.ReactNode;
  pulse?:     boolean;
}

export default function StatusBadge({
  status,
  size,
  dot,
  pulse,
  className,
  children,
}: StatusBadgeProps) {
  const dotColorMap: Record<string, string> = {
    good:  "bg-status-good",
    warn:  "bg-status-warn",
    bad:   "bg-status-bad",
    info:  "bg-status-info",
    muted: "bg-tx-muted",
  };

  return (
    <span
      className={cn(badgeVariants({ status, size, dot }), className)}
      aria-label={`Status: ${children}`}
    >
      {dot && (
        <span
          className={cn(
            "h-1.5 w-1.5 rounded-full shrink-0",
            dotColorMap[status ?? "muted"],
            pulse && "animate-pulse-slow"
          )}
          aria-hidden="true"
        />
      )}
      {children}
    </span>
  );
}
