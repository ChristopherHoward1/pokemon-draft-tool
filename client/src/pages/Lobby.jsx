import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { getSession, joinSession, startSession } from "../api";
import { useLobbySocket } from "../hooks/useLobbySocket";
import { FORMATS } from "../constants";

const teamKey = (code) => `draft:${code}:team`;
const ordinal = (n) => {
  const s = ["th", "st", "nd", "rd"];
  const v = n % 100;
  return n + (s[(v - 20) % 10] || s[v] || s[0]);
};

export default function Lobby() {
  const { code } = useParams();
  const navigate = useNavigate();
  const { slots, numTeams, started } = useLobbySocket(code);

  const [meta, setMeta] = useState(null); // {format, draft_order, num_teams, ...}
  const [myTeam, setMyTeam] = useState(() => sessionStorage.getItem(teamKey(code)) || "");
  const [nameInput, setNameInput] = useState("");
  const [joined, setJoined] = useState(false);
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    getSession(code).then(setMeta).catch((e) => setError(e.message));
  }, [code]);

  // If our stored name already occupies a slot, we're joined (survives refresh).
  useEffect(() => {
    if (myTeam && slots.some((s) => s.team_name === myTeam)) setJoined(true);
  }, [myTeam, slots]);

  // When the host starts, everyone jumps to the draft.
  useEffect(() => {
    if (started && myTeam) navigate(`/draft/${code}`);
  }, [started, myTeam, code, navigate]);

  const totalSlots = numTeams ?? meta?.num_teams;
  const full = totalSlots != null && slots.length >= totalSlots;
  const mySlot = slots.find((s) => s.team_name === myTeam)?.slot;
  const isHost = mySlot === 1;

  const join = async (e) => {
    e.preventDefault();
    const name = nameInput.trim();
    if (!name) return;
    setBusy(true);
    setError(null);
    try {
      await joinSession(code, name);
      sessionStorage.setItem(teamKey(code), name);
      setMyTeam(name);
      setJoined(true);
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  };

  const start = async () => {
    setBusy(true);
    setError(null);
    try {
      await startSession(code);
    } catch (err) {
      setError(err.message);
      setBusy(false);
    }
  };

  const formatLabel = FORMATS.find((f) => f.key === meta?.format)?.label ?? meta?.format;

  return (
    <div className="mx-auto flex min-h-full max-w-3xl flex-col px-4 py-10">
      {/* Room code header */}
      <div className="mb-6 flex flex-col items-center gap-2 text-center">
        <span className="font-mono text-[11px] uppercase tracking-[0.3em] text-muted">
          Room code — share in Discord
        </span>
        <div className="font-display text-6xl font-bold tracking-[0.2em] text-accent">
          {code}
        </div>
        {meta && (
          <div className="text-sm text-muted">
            {formatLabel} · {meta.budget} pt budget · {meta.roster_size} picks ·{" "}
            <span className="capitalize">{meta.draft_order}</span> order
          </div>
        )}
      </div>

      {/* Join form (until this browser has joined) */}
      {!joined && (
        <form
          onSubmit={join}
          className="mb-6 flex flex-col gap-3 rounded-xl border border-border bg-surface p-5"
        >
          <label className="font-mono text-[11px] uppercase tracking-[0.15em] text-muted">
            Your team name
          </label>
          <div className="flex gap-2">
            <input
              value={nameInput}
              onChange={(e) => setNameInput(e.target.value)}
              maxLength={40}
              placeholder="e.g. Team Nova"
              disabled={full}
              className="flex-1 rounded-md border border-border bg-ground px-3 py-2 text-ink outline-none focus:border-accent disabled:opacity-50"
            />
            <button
              type="submit"
              disabled={busy || full || !nameInput.trim()}
              className="rounded-md bg-accent px-5 py-2 font-semibold text-ground transition hover:brightness-110 disabled:opacity-50"
            >
              Join
            </button>
          </div>
          {full && !joined && (
            <span className="text-sm text-warn">This room is full.</span>
          )}
        </form>
      )}

      {joined && mySlot && (
        <div className="mb-6 rounded-xl border border-accent/40 bg-accent/10 px-5 py-3 text-center">
          <span className="text-sm text-ink">
            You joined as{" "}
            <span className="font-display font-bold text-accent">{myTeam}</span> — you
            are picking{" "}
            <span className="font-bold text-accent">{ordinal(mySlot)}</span>
          </span>
        </div>
      )}

      {/* Slot list */}
      <div className="flex flex-col gap-2">
        {Array.from({ length: totalSlots ?? slots.length }).map((_, i) => {
          const slot = slots[i];
          const mine = slot && slot.team_name === myTeam;
          return (
            <div
              key={i}
              className={`flex items-center gap-3 rounded-lg border px-4 py-3 transition ${
                slot
                  ? mine
                    ? "border-accent bg-accent/10"
                    : "border-border bg-surface"
                  : "border-dashed border-border/60 bg-transparent"
              }`}
            >
              <span className="font-mono text-sm text-faint">#{i + 1}</span>
              {slot ? (
                <span className="font-display text-lg font-semibold text-ink">
                  {slot.team_name}
                  {mine && <span className="ml-2 text-xs text-accent">(you)</span>}
                  {slot.slot === 1 && (
                    <span className="ml-2 font-mono text-[10px] uppercase tracking-wider text-muted">
                      host
                    </span>
                  )}
                </span>
              ) : (
                <span className="text-sm italic text-faint">waiting for a player…</span>
              )}
            </div>
          );
        })}
      </div>

      {error && (
        <div className="mt-4 rounded-md border border-warn/40 bg-warn/10 px-3 py-2 text-sm text-warn">
          {error}
        </div>
      )}

      {/* Start / waiting footer */}
      <div className="mt-8 flex flex-col items-center gap-2">
        {isHost ? (
          <button
            onClick={start}
            disabled={!full || busy}
            className="rounded-lg bg-accent px-8 py-3 font-display text-lg font-bold text-ground transition hover:brightness-110 disabled:cursor-not-allowed disabled:opacity-40"
          >
            {full ? "Start Draft" : `Waiting for players (${slots.length}/${totalSlots})`}
          </button>
        ) : (
          <span className="text-sm text-muted">
            {full ? "Waiting for host to start…" : "Waiting for more players…"}
          </span>
        )}
      </div>
    </div>
  );
}
