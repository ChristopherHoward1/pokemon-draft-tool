/**
 * Remaining-budget readout. Turns warning-red at or below `warnAt` points so a
 * team running low reads at a glance — semantic color, separate from the accent.
 */
export default function PointsBadge({ points, warnAt = 10, size = "md" }) {
  const low = points <= warnAt;
  const sizes = {
    sm: "text-sm",
    md: "text-xl",
    lg: "text-3xl",
  };
  return (
    <span
      className={`font-mono font-bold leading-none ${sizes[size] || sizes.md}`}
      style={{ color: low ? "var(--color-warn)" : "var(--color-good)" }}
    >
      {points}
      <span className="ml-1 text-[0.6em] font-medium text-muted">pts</span>
    </span>
  );
}
