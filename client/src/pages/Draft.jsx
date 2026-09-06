import { useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { useDraftSocket } from "../hooks/useDraftSocket";
import { useCopy } from "../hooks/useCopy";
import { TIER_ORDER, FORMATS } from "../constants";
import PokeCard from "../components/PokeCard";
import TeamRoster from "../components/TeamRoster";
import OnTheClock from "../components/OnTheClock";
import TierBadge from "../components/TierBadge";

const teamKey = (code) => `draft:${code}:team`;

/** Reconstruct the chronological pick log from per-team rosters + draft order. */
function buildLog(state) {
  const order = state.slots.map((s) => s.team_name); // index 0 = slot 1
  const n = order.length;
  const total = order.reduce((sum, name) => sum + state.teams[name].picks_made, 0);
  const log = [];
  for (let k = 0; k < total; k++) {
    const round = Math.floor(k / n);
    const pos = k % n;
    const idx = state.config.draft_order === "linear" || round % 2 === 0 ? pos : n - 1 - pos;
    const name = order[idx];
    const entry = state.teams[name].roster[round];
    if (entry) log.push({ team: name, entry });
  }
  return log;
}

const STATUS_STYLE = {
  connected: { dot: "var(--color-good)", label: "Live" },
  connecting: { dot: "var(--color-accent)", label: "Connecting…" },
  reconnecting: { dot: "var(--color-accent)", label: "Reconnecting…" },
  disconnected: { dot: "var(--color-warn)", label: "Disconnected" },
};

export default function Draft() {
  const { code } = useParams();
  const navigate = useNavigate();
  const teamName = sessionStorage.getItem(teamKey(code)) || "";

  const { state, error, lastPick, connectionStatus, sendPick, sendUndo } = useDraftSocket(
    code,
    teamName
  );

  const [search, setSearch] = useState("");
  const [typeFilter, setTypeFilter] = useState([]);
  const [tierFilter, setTierFilter] = useState([]);
  const { copied, copy } = useCopy();

  const allTypes = useMemo(() => {
    if (!state) return [];
    return [...new Set(state.pool.flatMap((e) => e.types))].sort();
  }, [state]);

  const presentTiers = useMemo(() => {
    if (!state) return [];
    return TIER_ORDER.filter((t) => state.pool.some((e) => e.vr_tier === t));
  }, [state]);

  if (!teamName) {
    return (
      <Centered>
        <p className="text-muted">You haven’t joined this room.</p>
        <button
          onClick={() => navigate(`/lobby/${code}`)}
          className="mt-3 rounded-md bg-accent px-4 py-2 font-semibold text-ground"
        >
          Go to lobby
        </button>
      </Centered>
    );
  }

  if (!state) {
    return (
      <Centered>
        <div className="h-3 w-3 animate-clockpulse rounded-full bg-accent" />
        <p className="mt-3 text-muted">Connecting to the draft…</p>
      </Centered>
    );
  }

  const order = state.slots.map((s) => s.team_name);
  const mySlot = state.slots.find((s) => s.team_name === teamName)?.slot;
  const isHost = mySlot === 1;
  const myTurn = !state.complete && state.current_team === teamName;
  const myBudget = state.teams[teamName]?.remaining_budget ?? 0;
  const log = buildLog(state);
  const formatLabel = FORMATS.find((f) => f.key === state.config.format)?.label;
  const status = STATUS_STYLE[connectionStatus] || STATUS_STYLE.connecting;

  const visible = state.pool.filter((e) => {
    if (search && !e.display_name.toLowerCase().includes(search.toLowerCase()) &&
        !e.name.toLowerCase().includes(search.toLowerCase())) return false;
    if (typeFilter.length && !e.types.some((t) => typeFilter.includes(t))) return false;
    if (tierFilter.length && !tierFilter.includes(e.vr_tier)) return false;
    return true;
  });
  const availCount = visible.filter((e) => !e.taken).length;

  const toggle = (list, setList, v) =>
    setList(list.includes(v) ? list.filter((x) => x !== v) : [...list, v]);

  return (
    <div className="flex min-h-full flex-col lg:flex-row">
      {/* Sidebar */}
      <aside className="flex shrink-0 flex-col gap-4 border-b border-border bg-surface p-4 lg:h-screen lg:w-72 lg:border-b-0 lg:border-r lg:sticky lg:top-0 lg:overflow-y-auto">
        <div className="flex items-center justify-between">
          <div>
            <div className="font-display text-lg font-bold text-ink">{formatLabel}</div>
            <div className="font-mono text-[11px] tracking-[0.2em] text-muted">
              ROOM {code}
            </div>
          </div>
          <span className="flex items-center gap-1.5 rounded-full border border-border px-2 py-1 text-[10px] text-muted">
            <span className="h-2 w-2 rounded-full" style={{ background: status.dot }} />
            {status.label}
          </span>
        </div>

        <button
          type="button"
          onClick={() => copy(window.location.href)}
          title="Copy a link to this live draft"
          className="rounded-md border border-border bg-ground px-3 py-2 text-sm font-semibold text-ink transition hover:border-accent"
        >
          {copied ? "Link copied!" : "Copy draft link"}
        </button>

        {/* Your team status */}
        <div className="rounded-lg border border-border bg-raised px-3 py-2.5">
          <div className="font-mono text-[10px] uppercase tracking-[0.2em] text-muted">
            You · #{mySlot} {teamName}
          </div>
          <div className="mt-1 flex items-baseline justify-between">
            <span
              className="font-mono text-2xl font-bold"
              style={{ color: myBudget <= 10 ? "var(--color-warn)" : "var(--color-good)" }}
            >
              {myBudget}
              <span className="ml-1 text-xs font-medium text-muted">pts left</span>
            </span>
            {myTurn && (
              <span className="rounded bg-accent px-2 py-0.5 text-[10px] font-bold uppercase text-ground">
                Your pick
              </span>
            )}
          </div>
        </div>

        {isHost && (
          <button
            onClick={sendUndo}
            disabled={log.length === 0}
            className="rounded-md border border-border bg-ground px-3 py-2 text-sm font-semibold text-ink transition hover:border-accent disabled:opacity-40"
          >
            Undo last pick
          </button>
        )}

        {error && (
          <div className="rounded-md border border-warn/40 bg-warn/10 px-3 py-2 text-xs text-warn">
            {error}
          </div>
        )}

        {/* Draft log */}
        <div className="flex min-h-0 flex-1 flex-col">
          <div className="mb-1.5 font-mono text-[10px] uppercase tracking-[0.2em] text-muted">
            Pick history
          </div>
          <div className="flex flex-col gap-1 overflow-y-auto pr-1 lg:flex-1">
            {log.length === 0 && <span className="text-xs text-faint">No picks yet.</span>}
            {[...log].reverse().map((pick, i) => (
              <div
                key={log.length - 1 - i}
                className="flex items-center gap-1.5 text-xs"
              >
                <span className="font-mono text-[10px] text-faint">
                  {log.length - i}.
                </span>
                <span className="truncate font-semibold text-ink">{pick.entry.display_name}</span>
                <TierBadge tier={pick.entry.vr_tier} small />
                <span className="ml-auto shrink-0 truncate text-[10px] text-muted">
                  {pick.team}
                </span>
              </div>
            ))}
          </div>
        </div>
      </aside>

      {/* Main */}
      <main className="flex min-w-0 flex-1 flex-col gap-4 p-4">
        <OnTheClock state={state} lastPick={lastPick} />

        {/* Filters */}
        <div className="flex flex-col gap-2">
          <div className="flex flex-wrap items-center gap-2">
            <input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search Pokémon…"
              className="w-full max-w-xs rounded-md border border-border bg-surface px-3 py-2 text-sm text-ink outline-none focus:border-accent"
            />
            <span className="font-mono text-xs text-muted">
              {availCount} available · {visible.length - availCount} taken
            </span>
          </div>
          <div className="flex flex-wrap gap-1">
            {presentTiers.map((t) => (
              <FilterChip key={t} active={tierFilter.includes(t)} onClick={() => toggle(tierFilter, setTierFilter, t)}>
                {t}
              </FilterChip>
            ))}
            <span className="mx-1 w-px self-stretch bg-border" />
            {allTypes.map((t) => (
              <FilterChip key={t} active={typeFilter.includes(t)} onClick={() => toggle(typeFilter, setTypeFilter, t)}>
                {t}
              </FilterChip>
            ))}
          </div>
        </div>

        {/* Pool grid */}
        <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 md:grid-cols-4 xl:grid-cols-5 2xl:grid-cols-6">
          {visible.map((entry) => (
            <PokeCard
              key={entry.name}
              entry={entry}
              draftable={myTurn}
              affordable={entry.cost <= myBudget}
              onDraft={sendPick}
            />
          ))}
        </div>
        {visible.length === 0 && (
          <p className="py-8 text-center text-sm text-faint">No Pokémon match those filters.</p>
        )}

        {/* Team roster board */}
        <div className="mt-2">
          <div className="mb-2 font-mono text-[11px] uppercase tracking-[0.2em] text-muted">
            Rosters
          </div>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
            {order.map((name, i) => (
              <TeamRoster
                key={name}
                team={state.teams[name]}
                slot={i + 1}
                rosterSize={state.config.roster_size}
                active={!state.complete && state.current_team === name}
              />
            ))}
          </div>
        </div>
      </main>
    </div>
  );
}

function FilterChip({ active, onClick, children }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`rounded-full border px-2.5 py-1 text-[11px] font-semibold capitalize transition ${
        active
          ? "border-accent bg-accent/15 text-accent"
          : "border-border bg-surface text-muted hover:border-borderlite"
      }`}
    >
      {children}
    </button>
  );
}

function Centered({ children }) {
  return (
    <div className="flex min-h-full flex-col items-center justify-center px-4 text-center">
      {children}
    </div>
  );
}
