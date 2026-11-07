export function timecode(sec) {
  const m = Math.floor(sec / 60);
  const s = sec - m * 60;
  return `${String(m).padStart(2, "0")}:${s.toFixed(2).padStart(5, "0")}`;
}

export function seconds(sec) {
  if (sec >= 60) {
    const m = Math.floor(sec / 60);
    return `${m}m ${Math.round(sec - m * 60)}s`;
  }
  return `${sec < 10 ? sec.toFixed(1) : Math.round(sec)}s`;
}

export function percent(p) {
  return `${Math.round(p * 100)}%`;
}

export function fileSize(bytes) {
  if (bytes > 1e9) return `${(bytes / 1e9).toFixed(1)} GB`;
  if (bytes > 1e6) return `${(bytes / 1e6).toFixed(1)} MB`;
  return `${Math.max(1, Math.round(bytes / 1e3))} KB`;
}

export function date(iso) {
  return new Date(iso).toLocaleDateString(undefined, { day: "numeric", month: "short", year: "numeric" });
}

export const BREAKDOWN_SOURCES = {
  anthropic: "Claude",
  openai: "GPT",
  template: "Built-in templates",
};
