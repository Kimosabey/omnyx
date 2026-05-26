import { Sun, Moon } from "lucide-react";
import { motion } from "framer-motion";
import { useThemeStore } from "@/store/theme";
import { cn } from "@/lib/utils";

export default function ThemeToggle() {
  const { theme, toggle } = useThemeStore();
  const isDark = theme === "dark";

  return (
    <button
      onClick={toggle}
      aria-label={isDark ? "Switch to light mode" : "Switch to dark mode"}
      aria-pressed={!isDark}
      role="switch"
      className={cn(
        "relative flex h-10 w-10 items-center justify-center rounded-xl",
        "text-tx-secondary hover:text-tx-primary hover:bg-elevated",
        "transition-colors duration-200",
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand"
      )}
    >
      <motion.div
        key={theme}
        initial={{ rotate: -90, opacity: 0 }}
        animate={{ rotate: 0,   opacity: 1 }}
        exit={{    rotate: 90,  opacity: 0 }}
        transition={{ duration: 0.25, ease: "easeOut" }}
      >
        {isDark
          ? <Sun  size={18} aria-hidden="true" />
          : <Moon size={18} aria-hidden="true" />
        }
      </motion.div>
    </button>
  );
}
