import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) { return twMerge(clsx(inputs)); }

export function formatBytes(bytes: number): string {
  if (!bytes) return "0 B";
  const units = ["B", "KB", "MB", "GB", "TB"];
  const index = Math.min(Math.floor(Math.log(bytes) / Math.log(1024)), units.length - 1);
  const value = bytes / 1024 ** index;
  return `${value >= 10 || index === 0 ? value.toFixed(0) : value.toFixed(1)} ${units[index]}`;
}

/** Rupees, with tiny amounts shown as "under ₹0.01" instead of ₹0.00. */
export function rupees(amount: number, tiny = false): string {
  const format = (n: number) => new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR", minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(n);
  return tiny && amount > 0 && amount < 0.01 ? `under ${format(0.01)}` : format(amount);
}

/** Lowercase without spaces or punctuation, like the server compares text in photos. */
export const squeeze = (value: string) => value.toLowerCase().replace(/[\s\-_.,:;!?'"()/]+/g, "");

/** Does a word read from a photo match one of the words searched for? */
export function wordMatches(word: string, search: string): boolean {
  const target = squeeze(word);
  return search.split(/\s+/).map(squeeze).filter((w) => w.length >= 3).some((w) => target.includes(w) || (target.length >= 3 && w.includes(target)));
}

export function formatDate(value: string): string {
  return new Intl.DateTimeFormat("en", { day: "numeric", month: "short", year: "numeric", hour: "numeric", minute: "2-digit" }).format(new Date(value));
}

// Round down, so a near-identical photo shows 99% rather than a misleading 100%.
export function percent(value: number): string { return `${Math.floor(value * 100)}%`; }
