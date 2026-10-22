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
  storage: StorageKind;
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

export interface Settings {
  version: string;
  storage: StorageKind;
  azure_account: string | null;
  azure_container: string;
  azure_set_by_environment: boolean;
  data_folder: string;
}
