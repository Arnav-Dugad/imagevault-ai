export type ProcessingStatus = "PENDING" | "PROCESSING" | "READY" | "EXACT_DUPLICATE" | "FAILED";
export type DuplicateType = "EXACT" | "PERCEPTUAL" | "VISUAL";

export interface User {
  id: string;
  email: string;
  display_name: string;
  created_at: string;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
  user: User;
}

export interface VaultImage {
  id: string;
  batch_id: string | null;
  original_filename: string;
  mime_type: string;
  file_size: number;
  width: number | null;
  height: number | null;
  sha256: string;
  perceptual_hash: string | null;
  status: ProcessingStatus;
  exact_duplicate_of_id: string | null;
  created_at: string;
  processed_at: string | null;
  thumbnail_url: string | null;
  original_url: string | null;
  best_similarity: number | null;
}

export interface SimilarImage {
  image: VaultImage;
  similarity_score: number;
  classification: string;
  match_type: DuplicateType;
  phash_distance: number | null;
  clip_score: number | null;
  perceptual_score: number | null;
  color_score: number | null;
  aspect_score: number | null;
  reasons: string[];
}

export interface ImageDetail extends VaultImage {
  object_key: string;
  thumbnail_key: string | null;
  error_message: string | null;
  exif_timestamp: string | null;
  camera_model: string | null;
  exact_duplicate_of: VaultImage | null;
  similar_images: SimilarImage[];
}

export interface ImageList {
  items: VaultImage[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
}

export interface DashboardData {
  total_images: number;
  unique_images: number;
  exact_duplicates: number;
  similar_images: number;
  storage_used: number;
  potential_savings: number;
  processing_images: number;
  uploads_over_time: { label: string; uploads: number; duplicates: number }[];
  format_distribution: { name: string; value: number }[];
  recent_images: VaultImage[];
}

export interface DuplicateGroup {
  group_id: string;
  original: VaultImage;
  candidates: {
    image: VaultImage;
    similarity_score: number;
    match_type: DuplicateType;
    classification: string;
    phash_distance: number | null;
    clip_score: number | null;
    perceptual_score: number | null;
    color_score: number | null;
    aspect_score: number | null;
    reasons: string[];
    same_batch: boolean;
  }[];
  recoverable_bytes: number;
  highest_similarity: number;
  all_same_batch: boolean;
}

export interface DuplicateReview {
  groups: DuplicateGroup[];
  batch_id: string | null;
  total_groups: number;
  exact_duplicates: number;
  similar_images: number;
  recoverable_bytes: number;
  processing_images: number;
  total_images_scanned: number;
}

export interface UploadResponse {
  batch_id: string;
  items: {
    image: VaultImage;
    exact_duplicate: boolean;
    matched_filename: string | null;
    message: string;
  }[];
}

export interface SystemStatus {
  status: string;
  version: string;
  api: ComponentStatus;
  database: ComponentStatus;
  object_storage: ComponentStatus;
  worker: ComponentStatus;
  embedding_model: ComponentStatus;
  pending_jobs: number;
  queue_size: number | null;
}

export interface ComponentStatus { status: string; detail: string | null }
