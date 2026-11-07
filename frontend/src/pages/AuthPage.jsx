import { useEffect, useState } from "react";
import { api } from "../api";
import { demoUsedHere, useAuth } from "../auth";
import RhythmChart from "../components/RhythmChart";
import { Wordmark } from "../components/Header";
import { Button, ErrorNote, Field, Spinner, inputClass } from "../components/ui";

// An illustrative scene: establish wide, push in for the emotional beat, cut back out.
const SAMPLE = [
  ["extremeLongShot", 0, 4.2], ["longShot", 4.2, 7.0], ["mediumShot", 7.0, 10.5], ["mediumCloseUp", 10.5, 12.4],
  ["closeUp", 12.4, 14.0], ["mediumShot", 14.0, 16.8], ["closeUp", 16.8, 18.1], ["detail", 18.1, 19.0],
  ["closeUp", 19.0, 21.2], ["fullShot", 21.2, 24.6], ["longShot", 24.6, 28.0],
].map(([label, start_sec, end_sec], i) => ({ index: i + 1, label, start_sec, end_sec }));

export default function AuthPage() {
  const { authenticate, startDemo } = useAuth();
  const [demoUsed, setDemoUsed] = useState(demoUsedHere);
  const [mode, setMode] = useState(() => (demoUsedHere() ? "register" : "login"));
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [config, setConfig] = useState(null);

  useEffect(() => {
    api("/api/config").then(setConfig).catch(() => setConfig(null));
  }, []);

  async function submit(e) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      await authenticate(mode, email, password);
    } catch (err) {
      setError(err.message);
      setBusy(false);
    }
  }

  async function tryDemo() {
    setBusy(true);
    setError("");
    try {
      await startDemo();
    } catch (err) {
      if (err.status === 429) {
        setDemoUsed(true);
        setMode("register");
      } else {
        setError(err.message);
      }
      setBusy(false);
    }
  }

  const isLogin = mode === "login";

  return (
    <div className="mx-auto grid min-h-screen max-w-6xl items-center gap-10 px-4 py-10 sm:px-6 lg:grid-cols-[1.25fr_1fr] lg:gap-16">
      <div>
        <Wordmark />
        <h1 className="condensed mt-8 text-5xl leading-[0.95] font-extrabold tracking-tight sm:text-6xl lg:text-7xl">
          Read the framing of every shot.
        </h1>
        <p className="mt-5 max-w-xl text-lg text-graphite">
          Upload a clip. ShotSense finds each cut, labels its shot scale with a model trained on film frames, and writes
          a prompt to recreate the shot in Veo, Kling or any AI video tool.
        </p>
        <figure className="mt-8 rounded-lg border border-rule bg-sheet p-4">
          <RhythmChart shots={SAMPLE} duration={28} interactive={false} />
          <figcaption className="mt-2 text-sm text-graphite">
            A 28-second scene as ShotSense charts it: wide to establish, pushing in for the emotional beat, then back out.
          </figcaption>
        </figure>
      </div>

      <div className="rounded-lg border border-rule bg-sheet p-6 sm:p-8">
        <div className="flex gap-1 rounded-md bg-table p-1" role="tablist" aria-label="Account">
          {[["login", "Sign in"], ["register", "Create account"]].map(([key, label]) => (
            <button key={key} type="button" role="tab" aria-selected={mode === key}
              onClick={() => { setMode(key); setError(""); }}
              className={`flex-1 rounded px-3 py-1.5 text-sm font-semibold ${mode === key ? "bg-sheet shadow-sm" : "text-graphite hover:text-ink"}`}>
              {label}
            </button>
          ))}
        </div>

        <form onSubmit={submit} className="mt-6 space-y-4">
          <Field label="Email">
            <input type="email" required autoComplete="email" className={inputClass} value={email}
              onChange={(e) => setEmail(e.target.value)} />
          </Field>
          <Field label="Password" hint={isLogin ? null : "At least 8 characters."}>
            <input type="password" required minLength={8} autoComplete={isLogin ? "current-password" : "new-password"}
              className={inputClass} value={password} onChange={(e) => setPassword(e.target.value)} />
          </Field>
          <ErrorNote>{error}</ErrorNote>
          <Button type="submit" className="w-full" disabled={busy}>
            {busy && <Spinner />}
            {isLogin ? "Sign in" : "Create account"}
          </Button>
        </form>

        {config?.guest_enabled && (
          <div className="mt-6 border-t border-rule pt-6">
            {demoUsed ? (
              <p className="text-sm text-graphite">
                You've already used the free demo. Create a free account to keep analyzing clips.
              </p>
            ) : (
              <>
                <p className="text-sm text-graphite">
                  Just looking? Try it once without signing up: {config.guest_max_analyses} analyses, visible only to
                  you and deleted after {config.guest_session_hours} hours.
                </p>
                <Button variant="secondary" className="mt-3 w-full" disabled={busy} onClick={tryDemo}>
                  Try the demo
                </Button>
              </>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
