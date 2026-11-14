import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

/**
 * Unit tests for the studio gateway client (change: add-scene-data-gateway
 * §4.3). The api module reads import.meta.env at import time, so tests
 * re-import it with fresh env via vi.resetModules.
 */

async function loadApi(env: Record<string, string>) {
  vi.resetModules();
  vi.stubEnv("VITE_GEOMIND_API", env["VITE_GEOMIND_API"] ?? "");
  vi.stubEnv("VITE_GEOMIND_DEMO", env["VITE_GEOMIND_DEMO"] ?? "");
  return import("./api");
}

beforeEach(() => {
  vi.unstubAllEnvs();
});

afterEach(() => {
  vi.unstubAllEnvs();
  vi.restoreAllMocks();
});

describe("ringToPolygon", () => {
  it("closes an open ring into a GeoJSON Polygon", async () => {
    const { ringToPolygon } = await loadApi({});
    const poly = ringToPolygon([[0, 0], [1, 0], [1, 1]]);
    expect(poly?.type).toBe("Polygon");
    const ring = poly!.coordinates[0];
    expect(ring[0]).toEqual(ring[ring.length - 1]);
  });

  it("returns null for degenerate rings", async () => {
    const { ringToPolygon } = await loadApi({});
    expect(ringToPolygon(null)).toBeNull();
    expect(ringToPolygon([[0, 0], [1, 1]])).toBeNull();
  });
});

describe("sensorKey", () => {
  it("maps display names to gateway sensor keys", async () => {
    const { sensorKey } = await loadApi({});
    expect(sensorKey("Landsat 9 OLI-2/TIRS-2")).toBe("landsat");
    expect(sensorKey("Sentinel-2 MSI (S2A/S2B)")).toBe("sentinel");
    expect(sensorKey("S2B Something")).toBe("sentinel");
    expect(sensorKey("Landsat 8 OLI/TIRS")).toBe("landsat");
  });
});

describe("tileUrlFor", () => {
  it("is undefined without an API base", async () => {
    const { tileUrlFor } = await loadApi({});
    expect(tileUrlFor("data/scenes/x/blue.tif")).toBeUndefined();
  });

  it("builds a MapLibre tile template pointing at the gateway route", async () => {
    const { tileUrlFor } = await loadApi({ VITE_GEOMIND_API: "http://localhost:8000" });
    const url = tileUrlFor("data/scenes/x/blue.tif", "3,2,1");
    expect(url).toContain("http://localhost:8000/api/v1/data/tiles/{z}/{x}/{y}.png");
    expect(url).toContain(encodeURIComponent("data/scenes/x/blue.tif"));
    expect(url).toContain("bands=3%2C2%2C1");
  });
});

describe("demo gating (no silent fakes)", () => {
  it("searchScenes rejects when gateway is down and demo is off", async () => {
    const { searchScenes } = await loadApi({});
    await expect(
      searchScenes({ roi: null, sensor: "Landsat 9", from: "2024-07-01", to: "2024-07-31", maxCloud: 30 }),
    ).rejects.toThrow(/gateway offline/i);
  });

  it("searchScenes serves generated data only in demo mode", async () => {
    const { searchScenes } = await loadApi({ VITE_GEOMIND_DEMO: "1" });
    const scenes = await searchScenes({ roi: null, sensor: "Landsat 9", from: "2024-07-01", to: "2024-07-31", maxCloud: 30 });
    expect(Array.isArray(scenes)).toBe(true);
    expect(scenes.length).toBeGreaterThan(0);
    expect(scenes[0].id).toBeTruthy();
  });

  it("requestDownload rejects without gateway or demo", async () => {
    const { requestDownload } = await loadApi({});
    await expect(
      requestDownload("LC08_X", null, { sensor: "Landsat 9", from: "2024-07-01", to: "2024-07-31" }),
    ).rejects.toThrow(/gateway offline/i);
  });

  it("groundedAsk abstains with a clear reason when offline (no demo)", async () => {
    const { groundedAsk } = await loadApi({});
    const res = await groundedAsk("why is the north pivot stressed?", "hybrid", 0.6);
    expect(res.abstained).toBe(true);
    expect(res.caveats.join(" ")).toMatch(/gateway offline/i);
  });

  it("hybridSearch returns [] (not fake data) when offline without demo", async () => {
    const warn = vi.spyOn(console, "warn").mockImplementation(() => {});
    const { hybridSearch } = await loadApi({});
    expect(await hybridSearch("ndvi stress")).toEqual([]);
    expect(warn).toHaveBeenCalled();
  });
});

describe("subscribeJob", () => {
  it("is a no-op subscription without a gateway", async () => {
    const { subscribeJob } = await loadApi({});
    let called = false;
    const unsub = subscribeJob("job-1", () => {
      called = true;
    });
    expect(typeof unsub).toBe("function");
    unsub();
    expect(called).toBe(false);
  });
});
