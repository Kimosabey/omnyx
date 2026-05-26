interface LogoProps {
  collapsed?: boolean;
  className?: string;
}

export default function GraylinxLogo({ collapsed, className = "" }: LogoProps) {
  return (
    <div className={`flex items-center gap-3 select-none ${className}`} aria-label="Graylinx OMNYX">
      {/* Logomark — G hex symbol */}
      <svg
        width="36"
        height="36"
        viewBox="0 0 36 36"
        fill="none"
        xmlns="http://www.w3.org/2000/svg"
        aria-hidden="true"
        className="shrink-0"
      >
        <defs>
          <linearGradient id="lg1" x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stopColor="#3D56FE" />
            <stop offset="100%" stopColor="#1F3FFE" />
          </linearGradient>
          <linearGradient id="lg2" x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stopColor="#6272FE" />
            <stop offset="100%" stopColor="#1F3FFE" />
          </linearGradient>
        </defs>
        {/* Hexagon background */}
        <path
          d="M18 2L33 10.5V25.5L18 34L3 25.5V10.5L18 2Z"
          fill="url(#lg1)"
        />
        {/* G letter mark */}
        <path
          d="M23.5 14.5C22 12.5 20 11.5 17.5 11.5C13.5 11.5 10.5 14.5 10.5 18.5C10.5 22.5 13.5 25.5 17.5 25.5C20.5 25.5 23 23.5 23.5 21H18V18H26V19C26 23.5 22.5 27 17.5 27C12.5 27 9 23.5 9 18.5C9 13.5 12.5 10 17.5 10C20.5 10 23 11.5 24.5 14L23.5 14.5Z"
          fill="white"
          fillOpacity="0.95"
        />
        {/* Accent line */}
        <path d="M18 2L33 10.5" stroke="white" strokeOpacity="0.15" strokeWidth="0.5" />
      </svg>

      {/* Wordmark */}
      {!collapsed && (
        <div className="flex flex-col leading-none">
          <span className="font-heading font-extrabold text-sm tracking-widest text-tx-inverse dark:text-tx-primary uppercase">
            Graylinx
          </span>
          <span className="font-mono text-2xs tracking-[0.2em] text-tx-inverse/60 dark:text-brand uppercase">
            OMNYX
          </span>
        </div>
      )}
    </div>
  );
}
