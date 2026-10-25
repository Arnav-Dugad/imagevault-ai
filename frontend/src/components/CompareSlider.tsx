import { useRef, useState, type KeyboardEvent, type PointerEvent } from "react";
import { ChevronsLeftRight, X } from "lucide-react";
import { formatBytes } from "../lib/utils";
import type { MatchKind, Photo } from "../types";
import { MatchBadge, Modal } from "./ui";

/** Two photos on top of each other with a divider you drag to compare them. */
export function CompareSlider({ left, right, leftKind, kind, similarity, onClose }: {
  left: Photo; right: Photo; leftKind: MatchKind | "keep"; kind: MatchKind | "keep"; similarity: number; onClose: () => void;
}) {
  const [position, setPosition] = useState(50);
  const [dragging, setDragging] = useState(false);
  const area = useRef<HTMLDivElement>(null);

  function moveTo(clientX: number) {
    const box = area.current?.getBoundingClientRect();
    if (box) setPosition(Math.min(100, Math.max(0, ((clientX - box.left) / box.width) * 100)));
  }
  function onPointerDown(event: PointerEvent) {
    (event.target as Element).setPointerCapture(event.pointerId);
    setDragging(true);
    moveTo(event.clientX);
  }
  function onKeyDown(event: KeyboardEvent) {
    if (event.key === "ArrowLeft") setPosition((p) => Math.max(0, p - 5));
    if (event.key === "ArrowRight") setPosition((p) => Math.min(100, p + 5));
  }

  // Both photos are shown at the same size, in the shape of the first photo.
  const ratio = `${left.width} / ${left.height}`;
  return (
    <Modal onClose={onClose} className="max-w-5xl p-4 sm:p-5">
      <div className="mb-3 flex items-start justify-between gap-3">
        <div>
          <h2 className="text-lg font-semibold">Compare</h2>
          <p className="text-sm text-muted">Drag the divider (or use ← →) to see how the two photos differ.</p>
        </div>
        <button onClick={onClose} aria-label="Close" className="focus-ring rounded-lg p-1.5 text-muted hover:bg-white/5 hover:text-ink"><X className="h-5 w-5" /></button>
      </div>

      <div ref={area} role="slider" tabIndex={0} aria-label="Comparison divider" aria-valuemin={0} aria-valuemax={100} aria-valuenow={Math.round(position)}
        onPointerDown={onPointerDown} onPointerMove={(e) => dragging && moveTo(e.clientX)} onPointerUp={() => setDragging(false)} onKeyDown={onKeyDown}
        className="focus-ring relative mx-auto max-h-[70vh] w-full cursor-ew-resize touch-none select-none overflow-hidden rounded-xl bg-black"
        style={{ aspectRatio: ratio, maxWidth: `calc(70vh * ${left.width / left.height})` }}>
        <img src={right.file_url} alt={right.filename} draggable={false} className="absolute inset-0 h-full w-full object-contain" />
        <div className="absolute inset-0" style={{ clipPath: `inset(0 ${100 - position}% 0 0)` }}>
          <img src={left.file_url} alt={left.filename} draggable={false} className="absolute inset-0 h-full w-full object-contain" />
        </div>
        <div className="pointer-events-none absolute inset-y-0" style={{ left: `${position}%` }}>
          <div className="absolute inset-y-0 -ml-px w-0.5 bg-white shadow-[0_0_12px_rgba(0,0,0,.6)]" />
          <div className={`absolute top-1/2 -ml-5 -mt-5 grid h-10 w-10 place-items-center rounded-full border-2 border-white bg-canvas/80 shadow-xl backdrop-blur transition-transform ${dragging ? "scale-110" : ""}`}>
            <ChevronsLeftRight className="h-5 w-5" />
          </div>
        </div>
        <span className="pointer-events-none absolute left-3 top-3"><MatchBadge kind={leftKind} /></span>
        <span className="pointer-events-none absolute right-3 top-3"><MatchBadge kind={kind} similarity={similarity} /></span>
      </div>

      <div className="mt-3 grid grid-cols-2 gap-3 text-sm">
        <p className="min-w-0"><span className="block truncate font-medium">{left.filename}</span><span className="text-xs text-muted">{left.width} × {left.height} · {formatBytes(left.size)}</span></p>
        <p className="min-w-0 text-right"><span className="block truncate font-medium">{right.filename}</span><span className="text-xs text-muted">{right.width} × {right.height} · {formatBytes(right.size)}</span></p>
      </div>
    </Modal>
  );
}
