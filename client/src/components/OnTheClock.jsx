import { spriteUrl } from "../api";
import PointsBadge from "./PointsBadge";
import TierBadge from "./TierBadge";

/**
 * Signature stream element. A wide "ON THE CLOCK" bar naming the active team and
 * its budget, plus a pick-reveal that flashes the most-recent selection across
 * the bar — so spectators who never click still get the drama of each pick.
 */
export default function OnTheClock({ state, lastPick }) {
  if (state.complete) {
    return (
      <div className="flex items-center justify-center rounded-xl border border-good/40 bg-good/10 px-6 py-4">
        <span className="font-display text-lg font-bold tracking-wide text-good">
          DRAFT COMPLETE — all rosters full
        </span>
      </div>
    );
  }

  const current = state.current_team;
  const team = state.teams[current];
  const totalPicks = Object.values(state.teams).reduce((n, t) => n + t.picks_made, 0);
  const round = Math.floor(totalPicks / state.config.num_teams) + 1;
  const rounds = state.config.roster_size;

  // Only flash a pick that landed within the last few seconds.
  const showPick = lastPick && Date.now() - lastPick.at < 3200;

  return (
    <div className="relative overflow-hidden rounded-xl border border-accent/30 bg-gradient-to-r from-surface via-raised to-surface px-5 py-3">
      <div className="flex items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <span className="h-2.5 w-2.5 rounded-full bg-accent animate-clockpulse" aria-hidden />
          <div>
            <div className="font-mono text-[10px] uppercase tracking-[0.2em] text-accent">
              On the clock · Round {round}/{rounds}
            </div>
            <div className="font-display text-2xl font-bold leading-tight text-ink">
              {current}
            </div>
          </div>
        </div>

        <div className="text-right">
          <div className="font-mono text-[10px] uppercase tracking-[0.2em] text-muted">
            Budget
          </div>
          <PointsBadge points={team.remaining_budget} size="md" />
        </div>
      </div>

      {showPick && (
        <div
          key={lastPick.at}
          className="animate-pickflash pointer-events-none absolute inset-0 flex items-center justify-center gap-3 bg-ground/85 backdrop-blur-sm"
        >
          <img
            src={spriteUrl(lastPick.entry.sprite_path)}
            alt=""
            width={48}
            height={48}
            onError={(e) => (e.currentTarget.style.display = "none")}
            className="h-12 w-12 object-contain [image-rendering:pixelated]"
          />
          <div className="text-left">
            <div className="font-mono text-[10px] uppercase tracking-[0.2em] text-accent">
              Drafted
            </div>
            <div className="flex items-center gap-2">
              <span className="font-display text-xl font-bold text-ink">
                {lastPick.entry.display_name}
              </span>
              <TierBadge tier={lastPick.entry.vr_tier} />
              <span className="font-mono text-sm font-bold text-accent">
                −{lastPick.entry.cost}
              </span>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
