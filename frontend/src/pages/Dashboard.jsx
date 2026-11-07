import { useEffect, useState } from "react";
import { api } from "../api";
import { useAuth } from "../auth";
import HistoryList from "../components/HistoryList";
import ModelCard from "../components/ModelCard";
import UploadPanel from "../components/UploadPanel";
import { ErrorNote, Sheet, Spinner } from "../components/ui";

const STEPS = [
  ["Find the cuts", "OpenCV compares colour and pixel changes between frames to split the video into shots."],
  ["Classify each shot", "A fine-tuned ResNet-18 labels the key frame's scale, from extreme close-up to extreme long shot."],
  ["Write the prompts", "An LLM looks at each frame and writes a text-to-video prompt that recreates the shot."],
];

export default function Dashboard({ model, config }) {
  const { token } = useAuth();
  const [analyses, setAnalyses] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    api("/api/analyses", { token })
      .then(setAnalyses)
      .catch((err) => setError(err.message));
  }, [token]);

  return (
    <main className="mx-auto grid max-w-6xl gap-6 px-4 py-8 sm:px-6 lg:grid-cols-[1fr_20rem]">
      <div className="min-w-0 space-y-8">
        <UploadPanel config={config} />
        <section>
          <h2 className="condensed mb-3 text-2xl font-bold">Your analyses</h2>
          <ErrorNote>{error}</ErrorNote>
          {analyses === null && !error && (
            <p className="flex items-center gap-2 text-graphite"><Spinner /> Loading</p>
          )}
          {analyses && <HistoryList analyses={analyses} />}
        </section>
      </div>
      <aside className="space-y-6">
        <ModelCard model={model} />
        <Sheet className="p-5">
          <h2 className="condensed text-xl font-bold">How it works</h2>
          <ol className="mt-3 space-y-3">
            {STEPS.map(([title, body], i) => (
              <li key={title} className="grid grid-cols-[1.5rem_1fr] gap-2">
                <span className="condensed text-lg leading-6 font-bold text-marker tnum">{i + 1}</span>
                <div>
                  <p className="font-semibold">{title}</p>
                  <p className="text-sm text-graphite">{body}</p>
                </div>
              </li>
            ))}
          </ol>
          {config && !config.llm_enabled && (
            <p className="mt-4 border-t border-rule pt-3 text-sm text-graphite">
              No LLM key is set on the server, so prompts come from built-in templates.
            </p>
          )}
        </Sheet>
      </aside>
    </main>
  );
}
