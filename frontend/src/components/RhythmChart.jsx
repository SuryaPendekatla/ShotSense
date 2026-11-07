import { SCALES, scale, scaleIndex } from "../labels";
import { timecode } from "../format";

const W = 1000;
const LEFT = 52;
const RIGHT = 12;
const TOP = 6;
const ROW = 30;
const AXIS = 28;
const H = TOP + ROW * SCALES.length + AXIS;

function tickStep(duration) {
  const steps = [0.5, 1, 2, 5, 10, 15, 30, 60, 120, 300];
  return steps.find((s) => duration / s <= 8) ?? 600;
}

/**
 * Framing rhythm: time runs left to right, shot scale top (tightest) to bottom (widest).
 * Each shot is a bar on its scale's row; the vertical joins show each cut's jump in framing.
 */
export default function RhythmChart({ shots, duration, activeIndex, onSelect, interactive = true }) {
  const span = Math.max(duration, shots.at(-1)?.end_sec ?? 0, 0.001);
  const x = (t) => LEFT + (t / span) * (W - LEFT - RIGHT);
  const rowY = (i) => TOP + i * ROW + ROW / 2;
  const step = tickStep(span);
  const ticks = [];
  for (let t = 0; t <= span + 1e-6; t += step) ticks.push(t);

  return (
    <svg
      viewBox={`0 0 ${W} ${H}`}
      className="block h-auto w-full"
      role="img"
      aria-label={`Framing over time for ${shots.length} shots`}
    >
      {SCALES.map((s, i) => (
        <g key={s.key}>
          <line x1={LEFT} x2={W - RIGHT} y1={rowY(i)} y2={rowY(i)} stroke="var(--color-rule)" strokeWidth="1" />
          <text x={LEFT - 10} y={rowY(i)} dy="0.35em" textAnchor="end" fontSize="13" fill="var(--color-graphite)">
            {s.abbr}
          </text>
        </g>
      ))}

      {ticks.map((t) => (
        <g key={t}>
          <line x1={x(t)} x2={x(t)} y1={TOP + ROW * SCALES.length} y2={TOP + ROW * SCALES.length + 5} stroke="var(--color-graphite)" />
          <text x={x(t)} y={H - 6} textAnchor="middle" fontSize="12" fill="var(--color-graphite)" className="tnum">
            {timecode(t).replace(/\.\d\d$/, "")}
          </text>
        </g>
      ))}

      {shots.map((shot, i) => {
        const prev = shots[i - 1];
        if (!prev) return null;
        return (
          <line
            key={`cut-${shot.index}`}
            x1={x(shot.start_sec)}
            x2={x(shot.start_sec)}
            y1={rowY(scaleIndex(prev.label))}
            y2={rowY(scaleIndex(shot.label))}
            stroke="var(--color-ink)"
            strokeOpacity="0.45"
            strokeWidth="1.5"
          />
        );
      })}

      {shots.map((shot) => {
        const row = Math.min(scaleIndex(shot.label), SCALES.length - 1);
        const x1 = x(shot.start_sec);
        const width = Math.max(3, x(shot.end_sec) - x1);
        const info = scale(shot.label);
        const active = activeIndex === shot.index;
        const label = `Shot ${shot.index}: ${info.name}, ${timecode(shot.start_sec)} to ${timecode(shot.end_sec)}`;
        const bar = (
          <rect
            x={x1}
            y={rowY(row) - 8}
            width={width}
            height={16}
            rx={2}
            fill={info.color}
            stroke={active ? "var(--color-marker)" : "var(--color-ink)"}
            strokeOpacity={active ? 1 : 0.18}
            strokeWidth={active ? 3 : 1}
          >
            <title>{label}</title>
          </rect>
        );
        if (!interactive) return <g key={shot.index}>{bar}</g>;
        return (
          <a
            key={shot.index}
            href={`#shot-${shot.index}`}
            aria-label={label}
            onClick={(e) => {
              e.preventDefault();
              onSelect?.(shot.index);
            }}
            className="cursor-pointer"
          >
            {bar}
          </a>
        );
      })}
    </svg>
  );
}
