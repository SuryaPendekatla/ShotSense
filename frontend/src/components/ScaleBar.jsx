import { SCALES } from "../labels";

/** Share of shots per scale as one stacked bar, tightest on the left. */
export default function ScaleBar({ counts, legend = false, className = "h-2.5" }) {
  const total = Object.values(counts).reduce((a, b) => a + b, 0) || 1;
  const present = SCALES.filter((s) => counts[s.key]);
  return (
    <div>
      <div className={`flex w-full overflow-hidden rounded-sm bg-rule ${className}`} role="img"
        aria-label={present.map((s) => `${s.short}: ${counts[s.key]}`).join(", ")}>
        {present.map((s) => (
          <div key={s.key} style={{ width: `${(100 * counts[s.key]) / total}%`, background: s.color }} />
        ))}
      </div>
      {legend && (
        <ul className="mt-3 flex flex-wrap gap-x-5 gap-y-1.5 text-sm text-graphite">
          {present.map((s) => (
            <li key={s.key} className="flex items-center gap-1.5">
              <span className="inline-block size-3 rounded-[2px] border border-ink/15" style={{ background: s.color }} />
              <span className="text-ink">{s.short}</span>
              <span className="tnum">{counts[s.key]}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
