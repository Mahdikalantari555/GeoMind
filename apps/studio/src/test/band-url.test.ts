import { afterEach, describe, expect, it, vi } from "vitest";

/**
 * Band-selector → tile-URL contract (T-080). Uses the real api helpers (with a
 * probed gateway) plus AcquireView's buildTileUrl so the composite path order
 * is verified end to end, not against a mock.
 */
async function loadLive() {
  vi.resetModules();
  vi.stubEnv("VITE_GEOMIND_API", "http://localhost:8000");
  vi.stubEnv("VITE_GEOMIND_DEMO", "");
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue(new Response(JSON.stringify({ status: "ok" }), { status: 200 })),
  );
  const api = await import("@/lib/api");
  await api.probeGateway();
  const { buildTileUrl } = await import("@/views/AcquireView");
  return { api, buildTileUrl };
}

afterEach(() => {
  vi.unstubAllEnvs();
  vi.restoreAllMocks();
});

describe("RGB band selection", () => {
  it("builds a composite tile URL with the selected bands in R,G,B order", async () => {
    const { buildTileUrl } = await loadLive();
    const bandFiles = {
      red: "data/scenes/x/red.tif",
      green: "data/scenes/x/green.tif",
      blue: "data/scenes/x/blue.tif",
      nir08: "data/scenes/x/nir08.tif",
    };

    const natural = buildTileUrl(bandFiles, ["red", "green", "blue"]);
    expect(natural).toBeTruthy();
    expect(natural).toContain("/api/v1/data/tiles/composite/{z}/{x}/{y}.png");
    expect(decodeURIComponent(natural!)).toContain(
      "paths=data/scenes/x/red.tif,data/scenes/x/green.tif,data/scenes/x/blue.tif",
    );

    // Changing only the R channel to NIR must change the URL accordingly.
    const falseColor = buildTileUrl(bandFiles, ["nir08", "red", "green"]);
    expect(falseColor).not.toBe(natural);
    expect(decodeURIComponent(falseColor!)).toContain(
      "paths=data/scenes/x/nir08.tif,data/scenes/x/red.tif,data/scenes/x/green.tif",
    );
  });

  it("falls back to a single-band tile when no full RGB selection is available", async () => {
    const { buildTileUrl } = await loadLive();
    const url = buildTileUrl({ blue: "data/scenes/x/blue.tif" });
    expect(url).toContain("/api/v1/data/tiles/{z}/{x}/{y}.png");
    expect(url).toContain("blue.tif");
  });

  it("proxies scene previews instead of calling third-party hosts", async () => {
    const { api } = await loadLive();
    const url = api.previewUrlFor("S2B_x", "https://example.blob.core.windows.net/p.png");
    expect(url).toContain("/api/v1/data/scenes/S2B_x/preview?url=");
    expect(url).toContain(encodeURIComponent("https://example.blob.core.windows.net/p.png"));
  });
});
