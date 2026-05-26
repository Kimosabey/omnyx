import { cn } from "@/lib/utils";

interface SkeletonProps {
  className?: string;
  rounded?:   "sm" | "md" | "lg" | "full";
  lines?:     number;
}

function Skeleton({ className, rounded = "md" }: SkeletonProps) {
  const roundMap = { sm: "rounded", md: "rounded-lg", lg: "rounded-xl", full: "rounded-full" };
  return <div className={cn("shimmer", roundMap[rounded], className)} aria-hidden="true" />;
}

export function SkeletonCard({ className }: { className?: string }) {
  return (
    <div className={cn("rounded-2xl border border-border bg-card p-5 space-y-3", className)}>
      <Skeleton className="h-3 w-20" />
      <Skeleton className="h-8 w-28" rounded="lg" />
      <Skeleton className="h-2.5 w-14" />
    </div>
  );
}

export function SkeletonRow({ className }: { className?: string }) {
  return (
    <div className={cn("flex items-center gap-3 py-3", className)}>
      <Skeleton className="h-8 w-8" rounded="lg" />
      <div className="flex-1 space-y-2">
        <Skeleton className="h-3 w-40" />
        <Skeleton className="h-2.5 w-24" />
      </div>
      <Skeleton className="h-6 w-16" rounded="full" />
    </div>
  );
}

export default Skeleton;
