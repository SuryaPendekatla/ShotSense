import { useState } from "react";
import { scale } from "../labels";
import { percent, seconds, timecode } from "../format";

export function ScaleChip({ label }) {
  const s = scale(label);
  return (
    <span
      className={`inline-flex items-center rounded-[3px] px-2 py-0.5 text-sm font-semibold ${s.light ? "text-ink" : "text-white"}`}
      style={{ background: s.color }}
    >
      {s.name}
    </span>
  );
}

export function CopyButton({ text, label = "Copy prompt" }) {
  const [copied, setCopied] = useState(false);
  async function copy() {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      setTimeout(() => setCopied(false), 1600);
    } catch {
      setCopied(false);
    }
  }
  return (
    <button type="button" onClick={copy}
      className="rounded px-2 py-1 text-sm font-semibold text-marker hover:bg-marker/5 hover:text-marker-dark">
      <span aria-live="polite">{copied ? "Copied" : label}</span>
    </button>
  );
}

export default function ShotRow({ shot, isVideo, active }) {
  const alternatives = shot.top3.slice(1).filter((p) => p.confidence >= 0.05);
  return (
    <li
      id={`shot-${shot.index}`}
      className={`scroll-mt-6 grid gap-4 p-4 sm:grid-cols-[minmax(0,15rem)_1fr] sm:gap-6 sm:p-5 ${active ? "bg-marker/[0.04]" : ""}`}
    >
      <div>
        <div className={`aspect-video overflow-hidden rounded-[3px] bg-ink ring-offset-2 ${active ? "ring-2 ring-marker" : ""}`}>
          <img src={shot.thumbnail} alt={`Key frame of shot ${shot.index}`} className="size-full object-contain" loading="lazy" />
        </div>
      </div>
      <div className="min-w-0">
        <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
          <h3 className="condensed text-lg font-bold">Shot {shot.index}</h3>
          {isVideo && (
            <p className="text-sm text-graphite tnum">
              {timecode(shot.start_sec)} to {timecode(shot.end_sec)}, {seconds(shot.end_sec - shot.start_sec)}
            </p>
          )}
        </div>
        <div className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1.5">
          <ScaleChip label={shot.label} />
          <span className="text-sm tnum">{percent(shot.confidence)} confident</span>
          {alternatives.length > 0 && (
            <span className="text-sm text-graphite">
              Next guess: {alternatives.map((p) => `${scale(p.label).short} ${percent(p.confidence)}`).join(", ")}
            </span>
          )}
        </div>
        {shot.description && <p className="mt-3 max-w-prose">{shot.description}</p>}
        {shot.prompt && (
          <div className="mt-3 rounded-md border border-rule bg-table/50">
            <div className="flex items-center justify-between border-b border-rule px-3 py-1">
              <span className="text-sm font-semibold text-graphite">Video prompt</span>
              <CopyButton text={shot.prompt} />
            </div>
            <p className="px-3 py-2.5 text-[15px] leading-relaxed">{shot.prompt}</p>
          </div>
        )}
      </div>
    </li>
  );
}
