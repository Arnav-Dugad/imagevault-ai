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
  items: { kind: "keep" | MatchKind; similarity: number; photo: Photo }[];
}

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
