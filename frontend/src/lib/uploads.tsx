import { createContext, useCallback, useContext, useEffect, useRef, useState, type ReactNode } from "react";
import type { UploadResult } from "../types";
import { uploadPhoto } from "./api";

export interface UploadItem {
  key: string;
  file: File;
  state: "waiting" | "uploading" | "done" | "failed";
  progress: number;
  result?: UploadResult;
  error?: string;
}

interface Uploads {
  items: UploadItem[];
  busy: boolean;
  add: (files: File[]) => void;
  retryFailed: () => void;
  clearFinished: () => void;
}

const UploadContext = createContext<Uploads>({ items: [], busy: false, add: () => {}, retryFailed: () => {}, clearFinished: () => {} });
const IMAGE_TYPES = /^image\/(jpeg|png|webp|gif|bmp)$/;

/** Uploads run here, outside any page, so they keep going while you look around the site. */
export function UploadProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<UploadItem[]>([]);
  const [busy, setBusy] = useState(false);
  const running = useRef(false);

  const update = (key: string, change: Partial<UploadItem>) =>
    setItems((all) => all.map((item) => (item.key === key ? { ...item, ...change } : item)));

  const work = useCallback(async (queue: UploadItem[]) => {
    // One at a time, so each photo is compared with the ones uploaded before it.
    for (const item of queue) {
      update(item.key, { state: "uploading", progress: 0, error: undefined });
      try {
        const result = await uploadPhoto(item.file, (progress) => update(item.key, { progress }));
        update(item.key, { state: "done", result });
      } catch (e) {
        update(item.key, { state: "failed", error: (e as Error).message });
      }
    }
  }, []);

  const pending = useRef<UploadItem[]>([]);
  const pump = useCallback(async () => {
    if (running.current) return;
    running.current = true;
    setBusy(true);
    while (pending.current.length) {
      const batch = pending.current.splice(0);
      await work(batch);
    }
    running.current = false;
    setBusy(false);
  }, [work]);

  const add = useCallback((files: File[]) => {
    const photos = files.filter((f) => IMAGE_TYPES.test(f.type) || /\.(jpe?g|png|webp|gif|bmp)$/i.test(f.name));
    const others = files.filter((f) => !photos.includes(f));
    const added = [...photos, ...others].map((file, i) => ({ key: `${Date.now()}-${i}-${file.name}`, file, state: "waiting" as const, progress: 0 }));
    setItems((all) => [...added, ...all]);
    pending.current.push(...added);
    void pump();
  }, [pump]);

  const retryFailed = useCallback(() => {
    const failed = items.filter((i) => i.state === "failed");
    failed.forEach((i) => update(i.key, { state: "waiting", error: undefined }));
    pending.current.push(...failed);
    void pump();
  }, [items, pump]);

  const clearFinished = useCallback(() => setItems((all) => all.filter((i) => i.state === "waiting" || i.state === "uploading")), []);

  // Paste a photo (Ctrl+V) anywhere to upload it.
  useEffect(() => {
    const onPaste = (event: ClipboardEvent) => {
      if ((event.target as HTMLElement)?.closest?.("input, textarea")) return;
      const files = Array.from(event.clipboardData?.files ?? []);
      if (files.length) add(files);
    };
    window.addEventListener("paste", onPaste);
    return () => window.removeEventListener("paste", onPaste);
  }, [add]);

  return <UploadContext.Provider value={{ items, busy, add, retryFailed, clearFinished }}>{children}</UploadContext.Provider>;
}

export const useUploads = () => useContext(UploadContext);
