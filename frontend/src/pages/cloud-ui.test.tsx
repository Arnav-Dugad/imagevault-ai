import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { MemoryRouter } from "react-router-dom";
import { api } from "../lib/api";
import { useAuth } from "../providers/AuthProvider";
import { AuthPage } from "./AuthPage";
import { SystemPage } from "./SystemPage";
import { AppLayout } from "../components/AppLayout";

vi.mock("../lib/api", () => ({ api: vi.fn(), ApiError: class extends Error {} }));
vi.mock("../providers/AuthProvider", () => ({ useAuth: vi.fn() }));
afterEach(() => { cleanup(); vi.resetAllMocks(); });

describe("cloud signup", () => {
  it("collects the invitation code and passes it when registering", async () => {
    const register = vi.fn().mockResolvedValue(undefined);
    vi.mocked(useAuth).mockReturnValue({ user: null, loading: false, register, login: vi.fn(), logout: vi.fn() });
    vi.mocked(api).mockResolvedValue({ registration_enabled: true, registration_requires_code: true });
    render(<MemoryRouter initialEntries={["/register"]}><AuthPage /></MemoryRouter>);
    fireEvent.change(await screen.findByLabelText("Invitation code"), { target: { value: "test-invitation" } });
    fireEvent.change(screen.getByLabelText("Display name"), { target: { value: "Test User" } });
    fireEvent.change(screen.getByLabelText("Email address"), { target: { value: "test@example.com" } });
    fireEvent.change(screen.getByLabelText("Password"), { target: { value: "strong-password" } });
    fireEvent.click(screen.getByRole("button", { name: "Create account" }));
    await waitFor(() => expect(register).toHaveBeenCalledWith("test@example.com", "Test User", "strong-password", "test-invitation"));
  });

  it("explains closed signup and disables account creation", async () => {
    vi.mocked(useAuth).mockReturnValue({ user: null, loading: false, register: vi.fn(), login: vi.fn(), logout: vi.fn() });
    vi.mocked(api).mockResolvedValue({ registration_enabled: false, registration_requires_code: false });
    render(<MemoryRouter initialEntries={["/register"]}><AuthPage /></MemoryRouter>);
    expect(await screen.findByText(/New accounts are closed/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Create account" })).toBeDisabled();
    expect(screen.queryByLabelText("Invitation code")).not.toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Sign in" })).toBeInTheDocument();
  });
});

describe("cloud service status", () => {
  it("reports degraded services and hides monitoring that is not configured", async () => {
    vi.mocked(api).mockResolvedValue({
      status: "degraded", version: "1.1.0", environment: "azure", storage_backend: "azure",
      max_user_storage_bytes: 2147483648, pending_jobs: 2, queue_size: 2,
      api: { status: "healthy", detail: "API responding" },
      database: { status: "healthy", detail: "Connected" },
      object_storage: { status: "healthy", detail: "Azure storage available" },
      worker: { status: "degraded", detail: "No recent heartbeat" },
      embedding_model: { status: "idle", detail: "Loads on first job" },
      grafana_url: null, prometheus_url: "javascript:alert(1)",
    });
    render(<SystemPage />);
    expect(await screen.findByText("Azure Blob Storage")).toBeInTheDocument();
    expect(screen.getByText("Some services need attention")).toBeInTheDocument();
    expect(screen.queryByText("All services ready")).not.toBeInTheDocument();
    expect(screen.queryByText("Monitoring")).not.toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Download ImageVault/ })).toHaveAttribute("href", "https://github.com/Arnav-Dugad/imagevault-ai/releases/latest");
  });
});


describe("simple classroom navigation", () => {
  it("keeps four main links and expands advanced tools when visited", () => {
    vi.mocked(useAuth).mockReturnValue({ user: { id: "user", email: "test@example.com", display_name: "Test User", created_at: "2026-01-01T00:00:00Z" }, loading: false, register: vi.fn(), login: vi.fn(), logout: vi.fn() });
    const view = render(<MemoryRouter initialEntries={["/gallery"]}><AppLayout><p>Gallery content</p></AppLayout></MemoryRouter>);
    const details = screen.getByText("Advanced").closest("details");
    expect(details).not.toHaveAttribute("open");
    expect(screen.getByRole("link", { name: "Upload" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Dashboard" })).toBeInTheDocument();
    view.unmount();
    render(<MemoryRouter initialEntries={["/system"]}><AppLayout><p>System content</p></AppLayout></MemoryRouter>);
    expect(screen.getByText("Advanced").closest("details")).toHaveAttribute("open");
    expect(screen.getByRole("link", { name: "System status" })).toBeInTheDocument();
  });
});
