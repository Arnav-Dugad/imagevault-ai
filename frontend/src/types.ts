export type CopyKind = "exact" | "similar";
export type MatchKind = CopyKind | "subject";
export type StorageKind = "local" | "azure";

export interface Photo {
  id: string;
  filename: string;
  content_type: string;
  size: number;
  width: number;
  height: number;
  sha256: string;
  uploaded_at: string;
  ai_status: "processing" | "done" | "failed" | null;
  taken_at: string | null;
  sharpness: number | null;
  favorite: boolean | null;
  thumb_url: string;
  file_url: string;
  match?: CopyKind | null;
}

export interface FaceInPhoto {
  id: string;
  person_id: string | null;
  name: string | null;
  photos: number;
  x: number;
  y: number;
  w: number;
  h: number;
  image_url: string;
}

export interface PhotoDetails extends Photo {
  matches: { kind: MatchKind; similarity: number; photo: Photo }[];
  people: FaceInPhoto[];
  albums: { id: string; name: string }[];
}

export interface PhotoList { total: number; items: Photo[] }

export interface UploadResult {
  photo: Photo;
  match: { id: string; filename: string; kind: CopyKind; similarity: number } | null;
}

export interface AiStatus {
  enabled: boolean;
  ready: boolean;
  message: string;
  analysed: number;
  waiting: number;
  failed: number;
}

export interface Stats {
  photos: number;
  total_bytes: number;
  stored_bytes: number;
  saved_bytes: number;
  exact_copies: number;
  similar_pairs: number;
  people: number;
  storage: StorageKind;
  ai: AiStatus;
  recent: Photo[];
}

export interface DuplicateGroup {
  id: string;
  extra_bytes: number;
  sharpest_id: string | null;
  items: { kind: "keep" | MatchKind | "burst"; similarity: number; photo: Photo }[];
}

export interface Album {
  id: string;            // an album id, or "auto:<key>" for albums made by the AI
  name: string;
  count: number;
  cover_url: string | null;
}

export type SortKey = "newest" | "oldest" | "taken_new" | "taken_old" | "largest" | "smallest" | "name";

export interface Person {
  id: string;
  name: string | null;
  photos: number;
  image_url: string | null;
}

export interface PersonDetails {
  id: string;
  name: string | null;
  image_url: string | null;
  photos: Photo[];
  faces: { id: string; photo_id: string; image_url: string }[];
}

export interface CostReport {
  configured: boolean;
  budget: number | null;
  amount?: number;
  currency?: string;
  services?: { name: string; amount: number }[];
  updated_at?: string;
  error?: string | null;
}

export interface CloudService {
  id: "app-service" | "database" | "storage" | "monitoring" | "ai";
  name: string;
  role: string;
  active: boolean;
  healthy: boolean;
  latency_ms: number | null;
  detail: string;
  error: string | null;
}

export interface SystemStatus {
  version: string;
  environment: "Azure" | "Local";
  build: { commit: string; deployed_at: string; run_url: string; repository: string } | null;
  ai_runs_on: "laptop" | "cloud";
  services: CloudService[];
}
