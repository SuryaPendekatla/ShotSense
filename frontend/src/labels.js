// Shot scales ordered from tightest to widest. Colours form an ordered ramp so the
// rhythm chart and distribution bars read as "tighter = darker".
export const SCALES = [
  { key: "detail", name: "Detail / Extreme Close-Up", short: "Detail", abbr: "ECU", color: "var(--color-ecu)", light: false },
  { key: "closeUp", name: "Close-Up", short: "Close-up", abbr: "CU", color: "var(--color-cu)", light: false },
  { key: "mediumCloseUp", name: "Medium Close-Up", short: "Medium close-up", abbr: "MCU", color: "var(--color-mcu)", light: false },
  { key: "mediumShot", name: "Medium Shot", short: "Medium", abbr: "MS", color: "var(--color-ms)", light: false },
  { key: "fullShot", name: "Full Shot", short: "Full", abbr: "FS", color: "var(--color-fs)", light: true },
  { key: "longShot", name: "Long Shot", short: "Long", abbr: "LS", color: "var(--color-ls)", light: true },
  { key: "extremeLongShot", name: "Extreme Long Shot", short: "Extreme long", abbr: "ELS", color: "var(--color-els)", light: true },
];

const FALLBACK = { name: "Unknown", short: "Unknown", abbr: "?", color: "#9aa3ab", light: true };

export function scale(key) {
  return SCALES.find((s) => s.key === key) ?? { ...FALLBACK, key, name: key, short: key };
}

export function scaleIndex(key) {
  const i = SCALES.findIndex((s) => s.key === key);
  return i === -1 ? SCALES.length : i;
}

export function countByScale(shots) {
  const counts = {};
  for (const s of shots) counts[s.label] = (counts[s.label] ?? 0) + 1;
  return counts;
}
