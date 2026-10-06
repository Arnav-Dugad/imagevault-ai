import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { api, getToken, setToken, uploadFiles } from "./api";

class FakeXHR {
  static latest: FakeXHR;
  status = 202;
  responseText = "{}";
  upload = { onprogress: null };
  onload?: () => void;
  onerror?: () => void;
  onabort?: () => void;
  ontimeout?: () => void;
  open = vi.fn(); setRequestHeader = vi.fn(); send = vi.fn();
  abort = vi.fn(() => this.onabort?.());
  constructor() { FakeXHR.latest = this; }
}
beforeEach(() => { localStorage.clear(); vi.stubGlobal("XMLHttpRequest", FakeXHR); });
afterEach(() => { vi.unstubAllGlobals(); vi.restoreAllMocks(); });

describe("upload transport recovery", () => {
  it("rejects invalid success JSON instead of leaving the request hanging", async () => {
    const promise = uploadFiles([], vi.fn());
    FakeXHR.latest.responseText = "bad gateway";
    FakeXHR.latest.onload?.();
    await expect(promise).rejects.toThrow(/invalid response/i);
  });
  it("does not send an already cancelled upload", async () => {
    const controller = new AbortController(); controller.abort();
    await expect(uploadFiles([], vi.fn(), controller.signal)).rejects.toThrow(/cancel/i);
    expect(FakeXHR.latest?.send).not.toHaveBeenCalled();
  });
  it("expires the current session on upload 401", async () => {
    setToken("expired");
    const event = vi.fn(); window.addEventListener("imagevault:unauthorized", event);
    try {
      const promise = uploadFiles([], vi.fn());
      FakeXHR.latest.status = 401; FakeXHR.latest.responseText = '{"detail":"Expired"}';
      FakeXHR.latest.onload?.();
      await expect(promise).rejects.toThrow("Expired");
      expect(getToken()).toBeNull(); expect(event).toHaveBeenCalledOnce();
    } finally { window.removeEventListener("imagevault:unauthorized", event); }
  });
  it("removes the abort listener after success", async () => {
    const controller = new AbortController();
    const remove = vi.spyOn(controller.signal, "removeEventListener");
    const promise = uploadFiles([], vi.fn(), controller.signal);
    const xhr = FakeXHR.latest; xhr.onload?.(); await promise;
    expect(remove).toHaveBeenCalledWith("abort", expect.any(Function));
    controller.abort(); expect(xhr.abort).not.toHaveBeenCalled();
  });
});
describe("request errors", () => {
  it("renders validation errors as readable text", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify({detail:[{loc:["body","display_name"],msg:"Too short"}]}), {status:422})));
    await expect(api("/auth/register")).rejects.toThrow("display_name: Too short");
  });
  it("does not log out a newer session when an old request returns 401", async () => {
    let finish!: (response: Response) => void;
    vi.stubGlobal("fetch", vi.fn(() => new Promise<Response>((resolve) => { finish = resolve; })));
    setToken("old"); const promise = api("/auth/me"); setToken("new");
    finish(new Response('{"detail":"Expired"}', {status:401}));
    await expect(promise).rejects.toThrow("Expired"); expect(getToken()).toBe("new");
  });
});
