export function Button({ variant = "primary", className = "", ...props }) {
  const styles = {
    primary: "bg-marker text-white hover:bg-marker-dark disabled:bg-graphite/50",
    secondary: "border border-rule bg-sheet text-ink hover:border-graphite disabled:text-graphite",
    quiet: "text-graphite hover:text-ink",
  };
  return (
    <button
      className={`inline-flex items-center justify-center gap-2 rounded-md px-4 py-2 text-sm font-semibold transition-colors disabled:cursor-not-allowed ${styles[variant]} ${className}`}
      {...props}
    />
  );
}

export function Field({ label, hint, children }) {
  return (
    <label className="block">
      <span className="mb-1.5 block text-sm font-semibold">{label}</span>
      {children}
      {hint && <span className="mt-1 block text-sm text-graphite">{hint}</span>}
    </label>
  );
}

export const inputClass =
  "w-full rounded-md border border-rule bg-sheet px-3 py-2 text-base placeholder:text-graphite/70 focus:border-ink focus:outline-none";

export function ErrorNote({ children }) {
  if (!children) return null;
  return (
    <p role="alert" className="rounded-md border-l-4 border-marker bg-marker/5 px-3 py-2 text-sm text-marker-dark">
      {children}
    </p>
  );
}

export function Sheet({ className = "", ...props }) {
  return <section className={`rounded-lg border border-rule bg-sheet ${className}`} {...props} />;
}

export function Spinner({ className = "size-4" }) {
  return (
    <svg className={`animate-spin ${className}`} viewBox="0 0 24 24" aria-hidden="true">
      <circle cx="12" cy="12" r="9" fill="none" stroke="currentColor" strokeOpacity="0.25" strokeWidth="3" />
      <path d="M21 12a9 9 0 0 0-9-9" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" />
    </svg>
  );
}
