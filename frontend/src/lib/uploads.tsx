import { createContext, useCallback, useContext, useEffect, useRef, useState, type ReactNode } from "react";
import type { UploadResult } from "../types";
import { ApiError, api, uploadPhoto } from "./api";

export interface UploadItem {
  key: string;
  file: File;
  state: "checking" | "stored" | "waiting" | "uploading" | "done" | "failed";
  progress: number;
  existing?: string; // with "stored": the name it already has in ImageVault
  result?: UploadResult;
  error?: string;
  final?: boolean; // failed for a reason trying again can't fix: not a photo, or too big
  retried?: boolean; // uploaded again with Retry
}

interface Uploads {
  items: UploadItem[];
  busy: boolean;
  add: (files: File[]) => Promise<{ queued: number; stored: number }>;
  uploadStored: () => void;
  skipStored: () => void;
  retryFailed: () => void;
  clearFinished: () => void;
}

const UploadContext = createContext<Uploads>({
  items: [], busy: false, add: async () => ({ queued: 0, stored: 0 }), uploadStored: () => {}, skipStored: () => {},
  retryFailed: () => {}, clearFinished: () => {},
});
const IMAGE_TYPES = /^image\/(jpeg|png|webp|gif|bmp)$/;

/** The file's SHA-256 fingerprint, the same one ImageVault uses to spot identical photos. */
async function fingerprint(file: File): Promise<string | null> {
  if (!crypto?.subtle) return null; // only available on https or localhost
  const digest = await crypto.subtle.digest("SHA-256", await file.arrayBuffer());
  return Array.from(new Uint8Array(digest), (b) => b.toString(16).padStart(2, "0")).join("");
}

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
        update(item.key, { state: "failed", error: (e as Error).message, final: e instanceof ApiError && (e.status === 413 || e.status === 415) });
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

  const add = useCallback(async (files: File[]) => {
    const photos = files.filter((f) => IMAGE_TYPES.test(f.type) || /\.(jpe?g|png|webp|gif|bmp)$/i.test(f.name));
    const others = files.filter((f) => !photos.includes(f));
    const added: UploadItem[] = [...photos, ...others].map((file, i) => ({ key: `${Date.now()}-${i}-${file.name}`, file, state: "checking", progress: 0 }));
    setItems((all) => [...added, ...all]);

    // Before uploading, ask which of these files are already stored, so nothing is uploaded twice by accident.
    const hashes = await Promise.all(added.map((item) => fingerprint(item.file).catch(() => null)));
    let found: Record<string, string> = {};
    const known = hashes.filter((h): h is string => !!h);
    if (known.length) {
      found = await api<{ found: Record<string, string> }>("/photos/check", { method: "POST", body: JSON.stringify({ sha256: known }) })
        .then((r) => r.found).catch(() => ({}));
    }
    const seen = new Set<string>();
    const queue: UploadItem[] = [];
    let stored = 0;
    added.forEach((item, i) => {
      const hash = hashes[i];
      const existing = hash ? found[hash] ?? (seen.has(hash) ? "another photo you picked" : undefined) : undefined;
      if (hash) seen.add(hash);
      if (existing) {
        stored += 1;
        update(item.key, { state: "stored", existing });
      } else {
        update(item.key, { state: "waiting" });
        queue.push(item);
      }
    });
    pending.current.push(...queue);
    void pump();
    return { queued: queue.length, stored };
  }, [pump]);

  const uploadStored = useCallback(() => {
    const stored = items.filter((i) => i.state === "stored");
    stored.forEach((i) => update(i.key, { state: "waiting", existing: undefined }));
    pending.current.push(...stored);
    void pump();
  }, [items, pump]);

  const skipStored = useCallback(() => setItems((all) => all.filter((i) => i.state !== "stored")), []);

  const retryFailed = useCallback(() => {
    const failed = items.filter((i) => i.state === "failed" && !i.final);
    failed.forEach((i) => update(i.key, { state: "waiting", error: undefined, retried: true }));
    pending.current.push(...failed);
    void pump();
  }, [items, pump]);

  const clearFinished = useCallback(() => setItems((all) => all.filter((i) => i.state === "waiting" || i.state === "uploading" || i.state === "checking")), []);

  // Paste a photo anywhere to upload it.
  useEffect(() => {
    const onPaste = (event: ClipboardEvent) => {
      if ((event.target as HTMLElement)?.closest?.("input, textarea")) return;
      const files = Array.from(event.clipboardData?.files ?? []);
      if (files.length) void add(files);
    };
    window.addEventListener("paste", onPaste);
    return () => window.removeEventListener("paste", onPaste);
  }, [add]);

  return <UploadContext.Provider value={{ items, busy, add, uploadStored, skipStored, retryFailed, clearFinished }}>{children}</UploadContext.Provider>;
}

export const useUploads = () => useContext(UploadContext);
