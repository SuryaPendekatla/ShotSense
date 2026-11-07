import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { api } from "../api";
import { useAuth } from "../auth";
import RhythmChart from "../components/RhythmChart";
import ScaleBar from "../components/ScaleBar";
import ShotRow, { CopyButton, ScaleChip } from "../components/ShotRow";
import { Button, ErrorNote, Sheet, Spinner } from "../components/ui";
import { countByScale } from "../labels";
import { BREAKDOWN_SOURCES, date, seconds } from "../format";

function Stat({ label, value }) {
  return (
    <div>
      <dt className="text-sm text-graphite">{label}</dt>
      <dd className="condensed text-2xl font-bold tnum">{value}</dd>
    </div>
  );
}

function downloadJson(analysis) {
  const { shots, ...rest } = analysis;
  const data = { ...rest, shots: shots.map(({ thumbnail, ...s }) => s) };
  const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `${analysis.title.replace(/[^\w-]+/g, "_")}_shotsense.json`;
  a.click();
  URL.revokeObjectURL(url);
}

export default function AnalysisPage({ model }) {
  const { id } = useParams();
  const { token } = useAuth();
  const navigate = useNavigate();
  const [analysis, setAnalysis] = useState(null);
  const [error, setError] = useState("");
  const [active, setActive] = useState(null);
  const [confirmDelete, setConfirmDelete] = useState(false);

  useEffect(() => {
    setAnalysis(null);
    setError("");
    api(`/api/analyses/${id}`, { token })
      .then(setAnalysis)
      .catch((err) => setError(err.status === 404 ? "This analysis doesn't exist or belongs to another account." : err.message));
  }, [id, token]);

  function select(index) {
    setActive(index);
    document.getElementById(`shot-${index}`)?.scrollIntoView({
      behavior: window.matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth",
      block: "start",
    });
  }

  async function remove() {
    try {
      await api(`/api/analyses/${id}`, { method: "DELETE", token });
      navigate("/");
    } catch (err) {
      setError(err.message);
    }
  }

  if (error) {
    return (
      <main className="mx-auto max-w-6xl space-y-4 px-4 py-8 sm:px-6">
        <ErrorNote>{error}</ErrorNote>
        <Link to="/" className="font-semibold text-marker hover:text-marker-dark">Back to your analyses</Link>
      </main>
    );
  }
  if (!analysis) {
    return (
      <main className="mx-auto flex max-w-6xl items-center gap-2 px-4 py-8 text-graphite sm:px-6">
        <Spinner /> Loading analysis
      </main>
    );
  }

  const isVideo = analysis.source_type === "video";
  const shots = analysis.shots;
  // Same basis as the server's pacing note: time inside detected shots, excluding fades to black.
  const avg = isVideo && shots.length ? shots.reduce((t, s) => t + s.end_sec - s.start_sec, 0) / shots.length : 0;
  const allPrompts = shots.map((s) => `Shot ${s.index}: ${s.prompt}`).join("\n\n");

  return (
    <main className="mx-auto max-w-6xl px-4 py-8 sm:px-6">
      <Link to="/" className="text-sm font-semibold text-graphite hover:text-ink">All analyses</Link>

      <div className="mt-3 flex flex-wrap items-end justify-between gap-4">
        <div className="min-w-0">
          <h1 className="condensed text-4xl leading-tight font-extrabold tracking-tight break-words sm:text-5xl">
            {analysis.title}
          </h1>
          <p className="mt-1 text-graphite">
            {analysis.filename}, analyzed {date(analysis.created_at)}
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button variant="secondary" onClick={() => downloadJson(analysis)}>Download JSON</Button>
          {confirmDelete ? (
            <>
              <Button variant="primary" onClick={remove}>Confirm delete</Button>
              <Button variant="quiet" onClick={() => setConfirmDelete(false)}>Keep it</Button>
            </>
          ) : (
            <Button variant="quiet" onClick={() => setConfirmDelete(true)}>Delete</Button>
          )}
        </div>
      </div>

      {model?.dummy && (
        <p className="mt-5 rounded-md border-l-4 border-marker bg-sheet px-4 py-2.5 text-sm">
          These labels come from a placeholder model and are random. Add the trained model to the server for real results.
        </p>
      )}
      {analysis.truncated && (
        <p className="mt-5 rounded-md border-l-4 border-graphite bg-sheet px-4 py-2.5 text-sm">
          This video has more cuts than the per-analysis limit, so only the first {shots.length} shots were analyzed.
        </p>
      )}

      <dl className="mt-6 grid grid-cols-2 gap-x-6 gap-y-4 sm:grid-cols-4">
        {isVideo ? (
          <>
            <Stat label="Duration" value={seconds(analysis.duration_sec)} />
            <Stat label="Shots" value={shots.length} />
            <Stat label="Average shot" value={seconds(avg)} />
          </>
        ) : (
          <Stat label="Frame" value={`${analysis.width}×${analysis.height}`} />
        )}
        <Stat label="Prompts by" value={BREAKDOWN_SOURCES[analysis.breakdown_source] ?? analysis.breakdown_source} />
      </dl>

      {isVideo ? (
        <Sheet className="mt-6 p-4 sm:p-5">
          <div className="flex flex-wrap items-baseline justify-between gap-2">
            <h2 className="condensed text-xl font-bold">Framing over time</h2>
            <p className="text-sm text-graphite">Tightest framing at the top. Select a bar to jump to that shot.</p>
          </div>
          <div className="mt-3 overflow-x-auto">
            <div className="min-w-[36rem]">
              <RhythmChart shots={shots} duration={analysis.duration_sec} activeIndex={active} onSelect={select} />
            </div>
          </div>
          <div className="mt-4 border-t border-rule pt-4">
            <ScaleBar counts={countByScale(shots)} legend className="h-3" />
          </div>
        </Sheet>
      ) : (
        <Sheet className="mt-6 flex flex-wrap items-center gap-3 p-4 sm:p-5">
          <span className="text-graphite">Predicted framing</span>
          <ScaleChip label={shots[0].label} />
        </Sheet>
      )}

      <div className="mt-6 grid gap-6 md:grid-cols-2">
        <section>
          <h2 className="condensed text-xl font-bold">Visual style</h2>
          <p className="mt-1.5 max-w-prose">{analysis.summary}</p>
        </section>
        <section>
          <h2 className="condensed text-xl font-bold">Pacing</h2>
          <p className="mt-1.5 max-w-prose">{analysis.pacing}</p>
        </section>
      </div>

      <section className="mt-8">
        <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
          <h2 className="condensed text-2xl font-bold">{isVideo ? "Shot by shot" : "Shot breakdown"}</h2>
          {shots.length > 1 && <CopyButton text={allPrompts} label="Copy all prompts" />}
        </div>
        <ol className="divide-y divide-rule overflow-hidden rounded-lg border border-rule bg-sheet">
          {shots.map((shot) => (
            <ShotRow key={shot.index} shot={shot} isVideo={isVideo} active={active === shot.index} />
          ))}
        </ol>
        <p className="mt-3 text-sm text-graphite">
          Model {analysis.model_version}, processed in {seconds(analysis.processing_ms / 1000)}.
        </p>
      </section>
    </main>
  );
}
