import { useState } from "react";
import { spriteUrl } from "../api";
import TypeBadge from "./TypeBadge";
import TierBadge from "./TierBadge";

/**
 * A draftable Pokémon. Clickable only when `draftable` (your turn + available).
 * Missing sprite → grey placeholder, never a broken image.
 */
export default function PokeCard({ entry, draftable, affordable, onDraft }) {
  const [imgError, setImgError] = useState(false);
  const taken = entry.taken;

  const clickable = draftable && !taken;
  const dimmed = taken || (draftable && !affordable);

  return (
    <button
      type="button"
      disabled={!clickable || !affordable}
      onClick={clickable && affordable ? () => onDraft(entry.name) : undefined}
      title={
        taken
          ? "Already drafted"
          : !draftable
            ? "Not your turn"
            : !affordable
              ? "Not enough points"
              : `Draft ${entry.display_name}`
      }
      className={`group relative flex flex-col items-center rounded-lg border p-2 text-center transition
        ${
          clickable && affordable
            ? "border-border bg-raised hover:border-accent hover:bg-[#232a34] cursor-pointer"
            : "border-border bg-surface cursor-default"
        }
        ${dimmed ? "opacity-45" : ""}`}
    >
      {taken && (
        <span className="absolute right-1 top-1 z-10 rounded bg-black/70 px-1.5 py-[1px] text-[9px] font-bold uppercase tracking-wider text-white">
          Taken
        </span>
      )}

      <div className="flex h-16 w-16 items-center justify-center">
        {imgError ? (
          <div className="h-14 w-14 rounded bg-border" aria-hidden />
        ) : (
          <img
            src={spriteUrl(entry.sprite_path)}
            alt={entry.display_name}
            width={64}
            height={64}
            loading="lazy"
            onError={() => setImgError(true)}
            className="h-16 w-16 object-contain [image-rendering:pixelated]"
          />
        )}
      </div>

      <div className="mt-1 line-clamp-1 w-full text-[13px] font-semibold text-ink">
        {entry.display_name}
      </div>

      <div className="mt-1 flex flex-wrap items-center justify-center gap-1">
        {entry.types.map((t) => (
          <TypeBadge key={t} type={t} />
        ))}
      </div>

      <div className="mt-1.5 flex items-center gap-1.5">
        <TierBadge tier={entry.vr_tier} />
        <span className="font-mono text-xs font-bold text-accent">{entry.cost}</span>
      </div>
    </button>
  );
}
