import { TIER_COLORS } from "../constants";

export default function TierBadge({ tier, small = false }) {
  const color = TIER_COLORS[tier] || "#555";
  return (
    <span
      className={`inline-block rounded font-bold text-white ${
        small ? "px-1 text-[9px]" : "px-1.5 py-[1px] text-[10px]"
      }`}
      style={{ background: color }}
    >
      {tier}
    </span>
  );
}
