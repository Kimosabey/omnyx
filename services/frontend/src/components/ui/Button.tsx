import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

const buttonVariants = cva(
  [
    "inline-flex items-center justify-center gap-2 rounded-xl font-body font-medium",
    "transition-all duration-200 ease-out-expo",
    "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand focus-visible:ring-offset-2 focus-visible:ring-offset-canvas",
    "disabled:pointer-events-none disabled:opacity-40",
    "min-h-touch min-w-touch",
    "select-none",
  ],
  {
    variants: {
      variant: {
        primary:   "bg-brand text-white hover:bg-brand-hover shadow-glow-sm hover:shadow-glow active:scale-95",
        secondary: "bg-elevated border border-border text-tx-primary hover:border-brand/40 hover:bg-card",
        ghost:     "text-tx-secondary hover:text-tx-primary hover:bg-elevated",
        danger:    "bg-status-bad/10 text-status-bad border border-status-bad/30 hover:bg-status-bad/20",
        success:   "bg-status-good/10 text-status-good border border-status-good/30 hover:bg-status-good/20",
      },
      size: {
        xs:  "h-7  px-2.5 text-xs",
        sm:  "h-8  px-3   text-sm",
        md:  "h-10 px-4   text-sm",
        lg:  "h-12 px-6   text-base",
        icon:"h-10 w-10   text-sm p-0",
      },
    },
    defaultVariants: {
      variant: "primary",
      size:    "md",
    },
  }
);

interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {
  loading?: boolean;
}

export default function Button({
  variant,
  size,
  loading,
  className,
  children,
  disabled,
  ...props
}: ButtonProps) {
  return (
    <button
      {...props}
      disabled={disabled || loading}
      aria-busy={loading}
      className={cn(buttonVariants({ variant, size }), className)}
    >
      {loading ? (
        <span
          className="h-4 w-4 animate-spin rounded-full border-2 border-current border-t-transparent"
          aria-label="Loading"
        />
      ) : null}
      {children}
    </button>
  );
}
