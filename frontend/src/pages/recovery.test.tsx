import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes, useNavigate } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import { api } from "../lib/api";
import { GalleryPage } from "./GalleryPage";
import { ImageDetailPage } from "./ImageDetailPage";
import { DuplicatesPage } from "./DuplicatesPage";
import { UploadPage } from "./UploadPage";

vi.mock("../lib/api", () => ({ api: vi.fn(), uploadFiles: vi.fn(), ApiError: class extends Error {} }));
const image = (id: string) => ({ id, original_filename: `${id}.png`, status: "READY", mime_type: "image/png", file_size: 123,
  width: 32, height: 24, thumbnail_url: null, original_url: null, created_at: "2026-01-01T00:00:00Z", media_kind: "PHOTO",
  smart_labels: [], face_count: 0, frame_count: 1, quality_score: null, blur_score: null, exposure_score: null,
  resolution_score: null, screenshot_quality_score: null, similar_images: [], ocr_layout: [] });
const list = (id: string) => ({ items: [image(id)], total: 1, page: 1, pages: 1 });
afterEach(() => { cleanup(); vi.resetAllMocks(); vi.useRealTimers(); vi.unstubAllGlobals(); });

function NextImage() { const navigate = useNavigate(); return <button onClick={() => navigate("/images/new")}>Next image</button>; }

describe("navigation races", () => {
  it("ignores a gallery response from an older filter", async () => {
    let oldResponse!: (value: unknown) => void;
    vi.mocked(api).mockImplementationOnce(() => new Promise((resolve) => { oldResponse = resolve; })).mockResolvedValueOnce(list("new"));
    render(<MemoryRouter><GalleryPage /></MemoryRouter>);
    fireEvent.click(screen.getByRole("button", {name:"Originals"}));
    expect(await screen.findByText("new.png")).toBeInTheDocument();
    await act(async () => oldResponse(list("old")));
    expect(screen.queryByText("old.png")).not.toBeInTheDocument();
    expect(screen.getByText("new.png")).toBeInTheDocument();
  });
  it("clears selected files when the sort changes", async () => {
    vi.mocked(api).mockResolvedValue(list("photo"));
    render(<MemoryRouter><GalleryPage /></MemoryRouter>);
    await screen.findByText("photo.png");
    fireEvent.click(screen.getByRole("button", {name:"Select"}));
    fireEvent.click(screen.getByRole("button", {name:"Select page"}));
    expect(screen.getByText("1 selected")).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("Sort gallery"), {target:{value:"oldest"}});
    await waitFor(() => expect(screen.queryByText("1 selected")).not.toBeInTheDocument());
  });
  it("ignores old image details after a route change", async () => {
    let oldResponse!: (value: unknown) => void;
    vi.mocked(api).mockImplementationOnce(() => new Promise((resolve) => { oldResponse = resolve; })).mockResolvedValueOnce(image("new"));
    render(<MemoryRouter initialEntries={["/images/old"]}><NextImage /><Routes><Route path="/images/:id" element={<ImageDetailPage />} /></Routes></MemoryRouter>);
    fireEvent.click(screen.getByRole("button", {name:"Next image"}));
    await screen.findByText("new.png");
    await act(async () => oldResponse(image("old")));
    expect(screen.queryByText("old.png")).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", {name:/^Delete$/}));
    fireEvent.click(screen.getByRole("button", {name:"Delete permanently"}));
    await waitFor(() => expect(api).toHaveBeenCalledWith("/images/new?confirm=true", {method:"DELETE"}));
  });
});

describe("processing updates", () => {
  it("continues polling even while the processing count stays unchanged", async () => {
    vi.useFakeTimers();
    vi.mocked(api).mockImplementation(async () => ({groups:[], processing_images:1, total_images_scanned:1, exact_duplicates:0, similar_images:0, recoverable_bytes:0, total_groups:0}));
    render(<MemoryRouter><DuplicatesPage /></MemoryRouter>);
    await act(async () => { await Promise.resolve(); });
    await act(async () => { await vi.advanceTimersByTimeAsync(2500); });
    await act(async () => { await vi.advanceTimersByTimeAsync(2500); });
    expect(api).toHaveBeenCalledTimes(3);
  });
});

describe("server upload limits", () => {
  it("shows Azure limits and rejects an oversized batch without silently dropping files", async () => {
    vi.mocked(api).mockResolvedValue({max_batch_files:1, max_upload_bytes:15*1024*1024, max_video_upload_bytes:100*1024*1024, allowed_extensions:[".png"]});
    vi.stubGlobal("URL", { createObjectURL:vi.fn(() => "blob:test"), revokeObjectURL:vi.fn() });
    const {container} = render(<MemoryRouter><UploadPage /></MemoryRouter>);
    await screen.findByText(/100 MB RAW\/video/);
    fireEvent.change(container.querySelector('input[type="file"]')!, {target:{files:[new File(["a"],"a.png"),new File(["b"],"b.png")]}});
    expect(screen.getByRole("alert")).toHaveTextContent("at most 1");
    expect(screen.queryByText(/ready$/)).not.toBeInTheDocument();
  });
});
