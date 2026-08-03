import { spriteUrl } from "../api";
import TierBadge from "./TierBadge";
import PointsBadge from "./PointsBadge";

function RosterSprite({ entry }) {
  return (
    <img
      src={spriteUrl(entry.sprite_path)}
      alt={entry.display_name}
      width={40}
      height={40}
      loading="lazy"
      onError={(e) => {
        e.currentTarget.style.visibility = "hidden";
      }}
      className="h-10 w-10 shrink-0 object-contain [image-rendering:pixelated]"
    />
  );
}

/**
 * One team's column in the roster board. Highlighted when it's this team's turn
 * and marked with its draft slot so spectators can follow the order.
 */
export default function TeamRoster({ team, slot, rosterSize, active }) {
  const filled = team.roster.length;
  const openSlots = Math.max(0, rosterSize - filled);

  return (
    <div
      className={`flex min-w-0 flex-col rounded-lg border bg-surface transition
        ${active ? "border-accent shadow-[0_0_0_1px_var(--color-accent)]" : "border-border"}`}
    >
      <div
        className={`flex items-center justify-between gap-2 rounded-t-lg px-3 py-2
          ${active ? "bg-accent/10" : ""}`}
      >
        <div className="min-w-0">
          <div className="flex items-center gap-1.5">
            <span className="font-mono text-[10px] text-faint">#{slot}</span>
            <span className="truncate font-display text-sm font-semibold text-ink">
              {team.name}
            </span>
          </div>
          <div className="text-[10px] text-muted">
            {filled}/{rosterSize} picks
          </div>
        </div>
        <PointsBadge points={team.remaining_budget} size="sm" />
      </div>

      <div className="flex flex-col gap-1 p-2">
        {team.roster.map((entry) => (
          <div key={entry.name} className="flex items-center gap-2 rounded bg-raised/60 px-1.5 py-1">
            <RosterSprite entry={entry} />
            <div className="min-w-0 flex-1">
              <div className="truncate text-xs font-semibold text-ink">
                {entry.display_name}
              </div>
              <div className="mt-0.5 flex items-center gap-1">
                <TierBadge tier={entry.vr_tier} small />
                <span className="font-mono text-[10px] text-muted">{entry.cost} pts</span>
              </div>
            </div>
          </div>
        ))}

        {Array.from({ length: openSlots }).map((_, i) => (
          <div
            key={`open-${i}`}
            className="flex items-center gap-2 rounded border border-dashed border-border/70 px-1.5 py-1"
          >
            <div className="h-10 w-10 shrink-0 rounded bg-border/30" />
            <span className="text-[10px] uppercase tracking-wide text-faint">open</span>
          </div>
        ))}
      </div>
    </div>
  );
}
