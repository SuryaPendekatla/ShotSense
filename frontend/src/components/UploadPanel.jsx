import { useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { uploadAnalysis } from "../api";
import { useAuth } from "../auth";
import { fileSize } from "../format";
import { Button, ErrorNote, Field, Sheet, Spinner, inputClass } from "./ui";

const ACCEPT = ".mp4,.mov,.m4v,.webm,.mkv,.avi,.jpg,.jpeg,.png,.webp";

export default function UploadPanel({ config }) {
  const { token } = useAuth();
  const navigate = useNavigate();
  const inputRef = useRef(null);
  const [file, setFile] = useState(null);
  const [title, setTitle] = useState("");
  const [notes, setNotes] = useState("");
  const [dragging, setDragging] = useState(false);
  const [progress, setProgress] = useState(null); // null | 0..1 uploading | "processing"
  const [error, setError] = useState("");

  const maxMb = config?.max_upload_mb ?? 200;
  const maxMin = Math.round((config?.max_video_seconds ?? 600) / 60);
  const busy = progress !== null;

  function choose(f) {
    if (!f) return;
    setError("");
    if (f.size > maxMb * 1024 * 1024) {
      setError(`That file is ${fileSize(f.size)}. The limit is ${maxMb} MB.`);
      return;
    }
    setFile(f);
  }

  async function submit(e) {
    e.preventDefault();
    if (!file) {
      setError("Choose a video or image first.");
      return;
    }
    setError("");
    setProgress(0);
    try {
      const analysis = await uploadAnalysis({
        file,
        title,
        notes,
        token,
        onUploadProgress: (p) => setProgress(p >= 1 ? "processing" : p),
      });
      navigate(`/analyses/${analysis.id}`);
    } catch (err) {
      setError(err.message);
      setProgress(null);
    }
  }

  return (
    <Sheet className="p-5 sm:p-6">
      <h2 className="condensed text-2xl font-bold">Analyze a clip</h2>
      <p className="mt-1 max-w-prose text-graphite">
        Upload a video up to {maxMin} minutes or a single frame. ShotSense finds each cut, labels the framing and writes a
        prompt to recreate every shot.
      </p>

      <form onSubmit={submit} className="mt-5 space-y-4">
        <div
          onDragOver={(e) => {
            e.preventDefault();
            setDragging(true);
          }}
          onDragLeave={() => setDragging(false)}
          onDrop={(e) => {
            e.preventDefault();
            setDragging(false);
            choose(e.dataTransfer.files?.[0]);
          }}
          className={`flex flex-col items-center justify-center gap-3 rounded-md border-2 border-dashed px-4 py-8 text-center transition-colors ${
            dragging ? "border-marker bg-marker/5" : "border-rule bg-table/60"
          }`}
        >
          {file ? (
            <div>
              <p className="font-semibold break-all">{file.name}</p>
              <p className="text-sm text-graphite tnum">{fileSize(file.size)}</p>
            </div>
          ) : (
            <p className="text-graphite">Drop a video or image here</p>
          )}
          <Button type="button" variant="secondary" onClick={() => inputRef.current?.click()} disabled={busy}>
            {file ? "Choose a different file" : "Choose file"}
          </Button>
          <input
            ref={inputRef}
            type="file"
            accept={ACCEPT}
            className="sr-only"
            onChange={(e) => choose(e.target.files?.[0])}
            aria-label="Video or image file"
          />
          <p className="text-xs text-graphite">MP4, MOV, WebM, MKV, AVI, JPG, PNG or WebP, up to {maxMb} MB</p>
        </div>

        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Title" hint="Defaults to the file name.">
            <input className={inputClass} value={title} onChange={(e) => setTitle(e.target.value)} maxLength={200}
              placeholder="Opening sequence" disabled={busy} />
          </Field>
          <Field label="Project notes" hint="Optional. Steers the style of the prompts.">
            <input className={inputClass} value={notes} onChange={(e) => setNotes(e.target.value)} maxLength={1000}
              placeholder="Neo-noir thriller, rainy neon city" disabled={busy} />
          </Field>
        </div>

        <ErrorNote>{error}</ErrorNote>

        <div className="flex flex-wrap items-center gap-4">
          <Button type="submit" disabled={busy}>
            {busy && <Spinner />}
            {busy ? "Analyzing" : "Analyze clip"}
          </Button>
          {busy && (
            <p className="text-sm text-graphite" aria-live="polite">
              {progress === "processing"
                ? "Finding cuts, classifying shots and writing prompts. Longer clips take up to a minute."
                : `Uploading ${Math.round(progress * 100)}%`}
            </p>
          )}
        </div>
      </form>
    </Sheet>
  );
}
