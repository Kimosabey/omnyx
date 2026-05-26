import { cn } from "@/lib/utils";

interface CardProps extends React.HTMLAttributes<HTMLDivElement> {
  variant?: "default" | "elevated" | "ghost";
  hover?:   boolean;
  padding?: "none" | "sm" | "md" | "lg";
}

export default function Card({
  variant  = "default",
  hover    = false,
  padding  = "md",
  className,
  children,
  ...props
}: CardProps) {
  return (
    <div
      {...props}
      className={cn(
        "rounded-2xl border transition-all duration-300",
        variant === "default"  && "bg-card border-border shadow-card",
        variant === "elevated" && "bg-elevated border-border/50 shadow-card",
        variant === "ghost"    && "bg-transparent border-border/30",
        hover && "hover:shadow-card-hover hover:border-brand/30 cursor-pointer",
        padding === "none" && "p-0",
        padding === "sm"   && "p-3",
        padding === "md"   && "p-5",
        padding === "lg"   && "p-6",
        className
      )}
    >
      {children}
    </div>
  );
}

interface CardHeaderProps extends React.HTMLAttributes<HTMLDivElement> {}
export function CardHeader({ className, children, ...props }: CardHeaderProps) {
  return (
    <div {...props} className={cn("flex items-center justify-between mb-4", className)}>
      {children}
    </div>
  );
}

interface CardTitleProps extends React.HTMLAttributes<HTMLHeadingElement> {
  as?: "h2" | "h3" | "h4";
}
export function CardTitle({ as: Tag = "h3", className, children, ...props }: CardTitleProps) {
  return (
    <Tag {...props} className={cn("font-heading font-semibold text-tx-primary", className)}>
      {children}
    </Tag>
  );
}
