import { useCallback, useEffect, useRef, useState, type MouseEvent } from "react";

/** Selecting photos: click to toggle, Shift+click for a range, Ctrl+A for all, Esc to clear. */
export function useSelection(order: string[]) {
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const last = useRef<string | null>(null);

  const toggle = useCallback((id: string, event?: MouseEvent) => {
    setSelected((current) => {
      const next = new Set(current);
      if (event?.shiftKey && last.current && order.includes(last.current)) {
        const [a, b] = [order.indexOf(last.current), order.indexOf(id)].sort((x, y) => x - y);
        order.slice(a, b + 1).forEach((photoId) => next.add(photoId));
      } else if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
    last.current = id;
  }, [order]);

  const clear = useCallback(() => { setSelected(new Set()); last.current = null; }, []);
  const selectAll = useCallback(() => setSelected(new Set(order)), [order]);

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if ((event.target as HTMLElement).closest("input, textarea, [role=dialog]")) return;
      if (event.key === "Escape" && selected.size) clear();
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "a" && selected.size) {
        event.preventDefault();
        selectAll();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [selected, clear, selectAll]);

  // Forget photos that are no longer listed (for example after deleting them).
  useEffect(() => {
    setSelected((current) => {
      const still = [...current].filter((id) => order.includes(id));
      return still.length === current.size ? current : new Set(still);
    });
  }, [order]);

  return { selected, toggle, clear, selectAll };
}
