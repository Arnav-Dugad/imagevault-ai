import { describe, expect, it } from "vitest";
import { formatBytes, percent } from "./utils";

describe("formatters", () => {
  it("formats storage without misleading precision", () => {
    expect(formatBytes(0)).toBe("0 B");
    expect(formatBytes(1536)).toBe("1.5 KB");
  });
  it("formats similarity", () => expect(percent(0.964)).toBe("96.4%"));
});
