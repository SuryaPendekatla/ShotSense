import { percent } from "../format";
import { Sheet } from "./ui";

export default function ModelCard({ model }) {
  if (!model) return null;
  const m = model.metrics ?? {};
  const test = m.test;
  const baseline = m.baseline;
  return (
    <Sheet className="p-5">
      <h2 className="condensed text-xl font-bold">The model</h2>
      {!model.loaded && <p className="mt-2 text-sm text-marker-dark">No model is loaded on the server.</p>}
      {model.dummy && (
        <p className="mt-2 text-sm text-marker-dark">
          A placeholder model is loaded, so labels are random. Add the trained model from the notebook to get real
          predictions.
        </p>
      )}
      {test && (
        <>
          <p className="mt-2 text-sm text-graphite">
            ResNet-18 fine-tuned on film frames, scored on {m.dataset?.n_test ?? "held-out"} human-labelled frames it
            never saw in training.
          </p>
          <table className="mt-4 w-full text-sm tnum">
            <thead>
              <tr className="text-left text-graphite">
                <th className="pb-1.5 font-medium">Model</th>
                <th className="pb-1.5 text-right font-medium">Accuracy</th>
                <th className="pb-1.5 text-right font-medium">Macro-F1</th>
              </tr>
            </thead>
            <tbody>
              <tr className="border-t border-rule">
                <td className="py-1.5 font-semibold">ResNet-18</td>
                <td className="py-1.5 text-right font-semibold">{percent(test.accuracy)}</td>
                <td className="py-1.5 text-right font-semibold">{percent(test.macro_f1)}</td>
              </tr>
              {baseline && (
                <tr className="border-t border-rule text-graphite">
                  <td className="py-1.5">HOG baseline</td>
                  <td className="py-1.5 text-right">{percent(baseline.accuracy)}</td>
                  <td className="py-1.5 text-right">{percent(baseline.macro_f1)}</td>
                </tr>
              )}
            </tbody>
          </table>
        </>
      )}
      {model.version && <p className="mt-3 text-xs text-graphite">Version {model.version}</p>}
    </Sheet>
  );
}
