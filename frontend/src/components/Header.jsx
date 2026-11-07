import { Link } from "react-router-dom";
import { useAuth } from "../auth";

export function Wordmark({ className = "" }) {
  return (
    <span className={`inline-flex items-center gap-2 ${className}`}>
      <svg viewBox="0 0 32 32" className="size-7" aria-hidden="true">
        <rect width="32" height="32" rx="6" fill="var(--color-ink)" />
        <rect x="5" y="8" width="7" height="4" fill="var(--color-els)" />
        <rect x="12" y="14" width="8" height="4" fill="var(--color-ms)" />
        <rect x="20" y="20" width="7" height="4" fill="var(--color-marker)" />
      </svg>
      <span className="condensed text-xl font-bold tracking-tight">ShotSense</span>
    </span>
  );
}

export default function Header() {
  const { user, signOut } = useAuth();
  return (
    <header className="border-b border-rule bg-sheet">
      <div className="mx-auto flex max-w-6xl items-center justify-between gap-4 px-4 py-3 sm:px-6">
        <Link to="/" aria-label="ShotSense home">
          <Wordmark />
        </Link>
        <div className="flex items-center gap-4 text-sm">
          {user?.is_guest ? (
            <span className="text-graphite tnum">
              Demo: {user.guest_analyses_left} {user.guest_analyses_left === 1 ? "analysis" : "analyses"} left
            </span>
          ) : (
            user && <span className="hidden text-graphite sm:inline">{user.email}</span>
          )}
          <button type="button" onClick={signOut} className="rounded px-2 py-1 font-medium text-graphite hover:text-ink">
            {user?.is_guest ? "Exit demo" : "Sign out"}
          </button>
        </div>
      </div>
    </header>
  );
}
