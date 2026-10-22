export type MatchKind = "exact" | "similar";
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
  thumb_url: string;
  file_url: string;
  match?: MatchKind | null;
}

export interface PhotoDetails extends Photo {
  matches: { kind: MatchKind; similarity: number; photo: Photo }[];
}

export interface PhotoList { total: number; items: Photo[] }

export interface UploadResult {
  photo: Photo;
  match: { id: string; filename: string; kind: MatchKind; similarity: number } | null;
}

export interface Stats {
  photos: number;
  total_bytes: number;
  stored_bytes: number;
  saved_bytes: number;
  exact_copies: number;
  similar_pairs: number;
  storage: StorageKind;
  recent: Photo[];
}

export interface DuplicateGroup {
  id: string;
  extra_bytes: number;
  items: { kind: "keep" | MatchKind; similarity: number; photo: Photo }[];
}

export interface CloudService {
  id: "app-service" | "database" | "storage" | "monitoring";
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
  services: CloudService[];
}
