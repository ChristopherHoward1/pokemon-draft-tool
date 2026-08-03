import { TYPE_COLORS } from "../constants";

export default function TypeBadge({ type }) {
  const color = TYPE_COLORS[type] || "#999";
  return (
    <span
      className="inline-block rounded-full px-2 py-[1px] text-[10px] font-semibold uppercase tracking-wide text-white/95"
      style={{ background: color }}
    >
      {type}
    </span>
  );
}
