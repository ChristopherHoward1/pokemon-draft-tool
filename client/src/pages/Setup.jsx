import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { createSession } from "../api";
import { FORMATS } from "../constants";

const POOL_MODES = [
  { key: "random", label: "Full Random", hint: "Draw N Pokémon uniformly." },
  { key: "vr_weighted", label: "VR-Weighted", hint: "Split ranked vs. unranked." },
  { key: "stratified", label: "Stratified", hint: "Pick a count per tier band." },
];

const STRAT_GROUPS = ["S", "A", "B", "C", "D", "Unranked"];

function Field({ label, hint, children }) {
  return (
    <label className="flex flex-col gap-1.5">
      <span className="font-mono text-[11px] uppercase tracking-[0.15em] text-muted">
        {label}
      </span>
      {children}
      {hint && <span className="text-xs text-faint">{hint}</span>}
    </label>
  );
}

const numberCls =
  "w-full rounded-md border border-border bg-ground px-3 py-2 font-mono text-ink outline-none focus:border-accent";

export default function Setup() {
  const navigate = useNavigate();
  const [format, setFormat] = useState("aaa");
  const [numTeams, setNumTeams] = useState(4);
  const [draftOrder, setDraftOrder] = useState("snake");
  const [budget, setBudget] = useState(60);
  const [rosterSize, setRosterSize] = useState(10);
  const [poolMode, setPoolMode] = useState("random");
  const [poolSize, setPoolSize] = useState(120);
  const [vrCount, setVrCount] = useState(60);
  const [unrankedCount, setUnrankedCount] = useState(60);
  const [tierCounts, setTierCounts] = useState({
    S: 4, A: 16, B: 28, C: 20, D: 8, Unranked: 24,
  });
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState(null);

  const stratTotal = STRAT_GROUPS.reduce((n, g) => n + (tierCounts[g] || 0), 0);

  const submit = async (e) => {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    const config = {
      format,
      num_teams: numTeams,
      draft_order: draftOrder,
      budget,
      roster_size: rosterSize,
      pool_mode: poolMode,
    };
    if (poolMode === "random") config.pool_size = poolSize;
    if (poolMode === "vr_weighted") {
      config.vr_count = vrCount;
      config.unranked_count = unrankedCount;
    }
    if (poolMode === "stratified") {
      config.tier_counts = Object.fromEntries(
        STRAT_GROUPS.filter((g) => tierCounts[g] > 0).map((g) => [g, tierCounts[g]])
      );
    }
    try {
      const { session_id } = await createSession(config);
      navigate(`/lobby/${session_id}`);
    } catch (err) {
      setError(err.message);
      setSubmitting(false);
    }
  };

  return (
    <div className="mx-auto flex min-h-full max-w-2xl flex-col justify-center px-4 py-10">
      <header className="mb-8">
        <div className="font-mono text-[11px] uppercase tracking-[0.3em] text-accent">
          Draft Room
        </div>
        <h1 className="mt-1 font-display text-4xl font-bold tracking-tight text-ink">
          Set up the war room
        </h1>
        <p className="mt-2 text-sm text-muted">
          Configure the draft, then share the room code in Discord. First player to
          join picks first.
        </p>
      </header>

      <form onSubmit={submit} className="flex flex-col gap-6 rounded-2xl border border-border bg-surface p-6">
        <Field label="Format">
          <div className="grid grid-cols-2 gap-2">
            {FORMATS.map((f) => (
              <button
                key={f.key}
                type="button"
                onClick={() => setFormat(f.key)}
                className={`rounded-md border px-3 py-2 text-sm font-semibold transition ${
                  format === f.key
                    ? "border-accent bg-accent/10 text-accent"
                    : "border-border bg-ground text-muted hover:border-borderlite"
                }`}
              >
                {f.label}
              </button>
            ))}
          </div>
        </Field>

        <div className="grid grid-cols-2 gap-4">
          <Field label="Teams" hint="2–8">
            <input
              type="number" min={2} max={8} value={numTeams}
              onChange={(e) => setNumTeams(clampInt(e.target.value, 2, 8, 4))}
              className={numberCls}
            />
          </Field>
          <Field label="Draft order">
            <div className="grid grid-cols-2 gap-2">
              {["snake", "linear"].map((o) => (
                <button
                  key={o}
                  type="button"
                  onClick={() => setDraftOrder(o)}
                  className={`rounded-md border px-2 py-2 text-sm font-semibold capitalize transition ${
                    draftOrder === o
                      ? "border-accent bg-accent/10 text-accent"
                      : "border-border bg-ground text-muted hover:border-borderlite"
                  }`}
                >
                  {o}
                </button>
              ))}
            </div>
          </Field>
        </div>

        <div className="grid grid-cols-2 gap-4">
          <Field label="Budget / team">
            <input
              type="number" min={1} value={budget}
              onChange={(e) => setBudget(clampInt(e.target.value, 1, 999, 60))}
              className={numberCls}
            />
          </Field>
          <Field label="Roster size">
            <input
              type="number" min={1} max={30} value={rosterSize}
              onChange={(e) => setRosterSize(clampInt(e.target.value, 1, 30, 10))}
              className={numberCls}
            />
          </Field>
        </div>

        <Field label="Pool generation">
          <div className="grid grid-cols-3 gap-2">
            {POOL_MODES.map((m) => (
              <button
                key={m.key}
                type="button"
                onClick={() => setPoolMode(m.key)}
                title={m.hint}
                className={`rounded-md border px-2 py-2 text-xs font-semibold transition ${
                  poolMode === m.key
                    ? "border-accent bg-accent/10 text-accent"
                    : "border-border bg-ground text-muted hover:border-borderlite"
                }`}
              >
                {m.label}
              </button>
            ))}
          </div>
        </Field>

        {poolMode === "random" && (
          <Field label="Pool size" hint="Total Pokémon in the draftable pool.">
            <input
              type="number" min={1} value={poolSize}
              onChange={(e) => setPoolSize(clampInt(e.target.value, 1, 1200, 120))}
              className={numberCls}
            />
          </Field>
        )}

        {poolMode === "vr_weighted" && (
          <div className="grid grid-cols-2 gap-4">
            <Field label="VR-ranked">
              <input
                type="number" min={1} value={vrCount}
                onChange={(e) => setVrCount(clampInt(e.target.value, 1, 1200, 60))}
                className={numberCls}
              />
            </Field>
            <Field label="Unranked">
              <input
                type="number" min={1} value={unrankedCount}
                onChange={(e) => setUnrankedCount(clampInt(e.target.value, 1, 1200, 60))}
                className={numberCls}
              />
            </Field>
          </div>
        )}

        {poolMode === "stratified" && (
          <Field label="Per-tier counts" hint={`Total pool size: ${stratTotal}`}>
            <div className="grid grid-cols-3 gap-2">
              {STRAT_GROUPS.map((g) => (
                <label key={g} className="flex items-center gap-2 rounded-md border border-border bg-ground px-2 py-1.5">
                  <span className="w-14 font-mono text-xs text-muted">{g}</span>
                  <input
                    type="number" min={0} value={tierCounts[g]}
                    onChange={(e) =>
                      setTierCounts({ ...tierCounts, [g]: clampInt(e.target.value, 0, 500, 0) })
                    }
                    className="w-full bg-transparent font-mono text-sm text-ink outline-none"
                  />
                </label>
              ))}
            </div>
          </Field>
        )}

        {error && (
          <div className="rounded-md border border-warn/40 bg-warn/10 px-3 py-2 text-sm text-warn">
            {error}
          </div>
        )}

        <button
          type="submit"
          disabled={submitting}
          className="mt-1 rounded-lg bg-accent px-4 py-3 font-display text-base font-bold text-ground transition hover:brightness-110 disabled:opacity-50"
        >
          {submitting ? "Creating room…" : "Create draft room"}
        </button>
      </form>
    </div>
  );
}

function clampInt(raw, min, max, fallback) {
  const n = parseInt(raw, 10);
  if (Number.isNaN(n)) return fallback;
  return Math.max(min, Math.min(max, n));
}
