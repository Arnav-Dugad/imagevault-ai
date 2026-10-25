import { useEffect, useRef, type PointerEvent } from "react";
import { createPortal } from "react-dom";
import { ChevronLeft, ChevronRight, X } from "lucide-react";
import type { Photo } from "../types";

/** The photo filling the whole screen. Arrow keys or swiping move between photos; Esc closes. */
export function FullscreenPhoto({ photo, position, onPrev, onNext, onClose }: {
  photo: Photo; position: string | null; onPrev?: () => void; onNext?: () => void; onClose: () => void;
}) {
  const root = useRef<HTMLDivElement>(null);
  const swipeStart = useRef<number | null>(null);

  useEffect(() => {
    // Use the browser's real full-screen mode when it's available (not on every phone).
    root.current?.requestFullscreen?.().catch(() => {});
    const onExit = () => { if (!document.fullscreenElement) onClose(); };
    document.addEventListener("fullscreenchange", onExit);
    return () => {
      document.removeEventListener("fullscreenchange", onExit);
      if (document.fullscreenElement) document.exitFullscreen().catch(() => {});
    };
  }, [onClose]);

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      const action = { ArrowLeft: onPrev, ArrowRight: onNext, Escape: onClose }[event.key];
      if (!action) return;
      event.stopImmediatePropagation(); // the photo pop-up underneath must not react too
      action();
    };
    window.addEventListener("keydown", onKey, true);
    return () => window.removeEventListener("keydown", onKey, true);
  }, [onPrev, onNext, onClose]);

  function onPointerUp(event: PointerEvent) {
    if (swipeStart.current === null) return;
    const distance = event.clientX - swipeStart.current;
    swipeStart.current = null;
    if (distance > 60) onPrev?.();
    if (distance < -60) onNext?.();
  }

  const arrow = "focus-ring absolute top-1/2 grid h-12 w-12 -translate-y-1/2 place-items-center rounded-full bg-white/10 text-white backdrop-blur transition hover:bg-white/20 disabled:opacity-0";
  return createPortal(
    <div ref={root} className="fixed inset-0 z-[60] select-none bg-black" onPointerDown={(e) => { swipeStart.current = e.clientX; }} onPointerUp={onPointerUp}>
      <img key={photo.id} src={photo.file_url} alt={photo.filename} draggable={false} className="pop-in h-full w-full object-contain" />
      <div className="absolute inset-x-0 top-0 flex items-center justify-between gap-4 bg-gradient-to-b from-black/80 to-transparent px-5 py-4 text-sm text-white">
        <p className="truncate">{photo.filename}{position && <span className="ml-3 text-white/60">{position}</span>}</p>
        <button onClick={onClose} aria-label="Exit full screen" className="focus-ring rounded-full bg-white/10 p-2 hover:bg-white/20"><X className="h-5 w-5" /></button>
      </div>
      <button onClick={onPrev} disabled={!onPrev} aria-label="Previous photo" className={`${arrow} left-4`}><ChevronLeft className="h-6 w-6" /></button>
      <button onClick={onNext} disabled={!onNext} aria-label="Next photo" className={`${arrow} right-4`}><ChevronRight className="h-6 w-6" /></button>
      <p className="pointer-events-none absolute inset-x-0 bottom-4 text-center text-xs text-white/50">← → or swipe to browse · Esc to close</p>
    </div>,
    document.body,
  );
}
