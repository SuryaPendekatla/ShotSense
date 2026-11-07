import { Link } from "react-router-dom";
import { date, seconds } from "../format";
import ScaleBar from "./ScaleBar";

export default function HistoryList({ analyses }) {
  if (analyses.length === 0) {
    return (
      <p className="rounded-lg border border-dashed border-rule px-5 py-8 text-center text-graphite">
        No analyses yet. Upload a clip above to see its shot breakdown here.
      </p>
    );
  }
  return (
    <ul className="divide-y divide-rule overflow-hidden rounded-lg border border-rule bg-sheet">
      {analyses.map((a) => (
        <li key={a.id}>
          <Link to={`/analyses/${a.id}`} className="flex items-center gap-4 p-3 hover:bg-table/50 sm:p-4">
            <div className="aspect-video w-28 shrink-0 overflow-hidden rounded-[3px] bg-ink sm:w-36">
              {a.cover && <img src={a.cover} alt="" className="size-full object-contain" />}
            </div>
            <div className="min-w-0 flex-1">
              <p className="truncate font-semibold">{a.title}</p>
              <p className="mt-0.5 text-sm text-graphite tnum">
                {date(a.created_at)}
                <span className="mx-2 text-rule">|</span>
                {a.source_type === "image" ? "Still frame" : `${a.shot_count} shots in ${seconds(a.duration_sec)}`}
              </p>
              <ScaleBar counts={a.label_counts} className="mt-2.5 h-2 max-w-sm" />
            </div>
          </Link>
        </li>
      ))}
    </ul>
  );
}
