import { useEffect, useState } from "react";
import { Sparkles } from "lucide-react";
import { api } from "../lib/api";

/** Album names suggested from the photos: words written in them, what they show, and when they were taken. */
export function NameSuggestions({ ids, onPick }: { ids: string[]; onPick: (name: string) => void }) {
  const [names, setNames] = useState<string[]>([]);
  const key = ids.join(",");
  useEffect(() => {
    if (!key) return;
    api<{ names: string[] }>("/albums/suggest", { method: "POST", body: JSON.stringify({ ids: key.split(",") }) })
      .then((r) => setNames(r.names)).catch(() => setNames([]));
  }, [key]);
  if (!names.length) return null;
  return (
    <div className="flex flex-wrap items-center gap-1.5">
      <Sparkles className="h-3.5 w-3.5 text-sky-300" aria-label="Suggested names" />
      {names.map((name) => (
        <button key={name} type="button" onClick={() => onPick(name)}
          className="focus-ring rounded-full border border-sky-300/30 bg-sky-300/[.07] px-2.5 py-0.5 text-xs text-sky-200 transition hover:border-sky-300/60">
          {name}
        </button>
      ))}
    </div>
  );
}
