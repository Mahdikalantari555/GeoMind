import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

/**
 * Unit tests for the studio gateway client (change: add-scene-data-gateway
 * §4.3). The api module reads import.meta.env at import time, so tests
 * re-import it with fresh env via vi.resetModules.
 */

async function loadApi(env: Record<string, string>) {
  vi.resetModules();
  vi.stubEnv("VITE_GEOMIND_API", env["VITE_GEOMIND_API"]);
  vi.stubEnv("VITE_GEOMIND_DEMO", env["VITE_GEOMIND_DEMO"] ?? "");
  return import("./api");
}

beforeEach(() => {
  vi.unstubAllEnvs();
});

afterEach(() => {
  vi.unstubAllEnvs();
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
  vi.useRealTimers();
});

describe("gateway base", () => {
  it("configures the same-origin base by default", async () => {
    const { API_BASE, gatewayConfigured } = await loadApi({});
    expect(API_BASE).toBe("");
    expect(gatewayConfigured).toBe(true);
  });

  it("probes through the relative dev proxy", async () => {
    const fetch = vi.fn().mockResolvedValue({ ok: true });
    vi.stubGlobal("fetch", fetch);
    const { probeGateway, tileUrlFor } = await loadApi({});
    await expect(probeGateway()).resolves.toBe(true);
    expect(fetch).toHaveBeenCalledWith("/api/v1/health", expect.anything());
    expect(tileUrlFor("band.tif")).toMatch(/^\/api\/v1\/data\/tiles\//);
  });
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
  it("maps the unified selector ids to gateway sensor keys", async () => {
    const { sensorKey } = await loadApi({});
    expect(sensorKey("landsat")).toBe("landsat");
    expect(sensorKey("sentinel")).toBe("sentinel");
  });

  it("still accepts legacy display names", async () => {
    const { sensorKey } = await loadApi({});
    expect(sensorKey("Landsat 9 OLI-2/TIRS-2")).toBe("landsat");
    expect(sensorKey("Sentinel-2 MSI (S2A/S2B)")).toBe("sentinel");
    expect(sensorKey("S2B Something")).toBe("sentinel");
    expect(sensorKey("Landsat 8 OLI/TIRS")).toBe("landsat");
  });
});

describe("tileUrlFor", () => {
  it("is undefined when the gateway is down", async () => {
    const { tileUrlFor } = await loadApi({});
    expect(tileUrlFor("data/scenes/x/blue.tif")).toBeUndefined();
  });

  it("builds a MapLibre tile template pointing at the gateway route", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: true }));
    const { tileUrlFor, probeGateway, gatewayConfigured } = await loadApi({ VITE_GEOMIND_API: "http://localhost:8000/" });
    expect(gatewayConfigured).toBe(true);
    await probeGateway();
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
      searchScenes({ roi: null, sensor: "landsat", from: "2024-07-01", to: "2024-07-31", maxCloud: 30 }),
    ).rejects.toThrow(/gateway offline/i);
  });

  it("searchScenes serves generated data only in demo mode", async () => {
    const { searchScenes } = await loadApi({ VITE_GEOMIND_DEMO: "1" });
    const scenes = await searchScenes({ roi: null, sensor: "landsat", from: "2024-07-01", to: "2024-07-31", maxCloud: 30 });
    expect(Array.isArray(scenes)).toBe(true);
    expect(scenes.length).toBeGreaterThan(0);
    expect(scenes[0].id).toBeTruthy();
  });

  it("requestDownload rejects without gateway or demo", async () => {
    const { requestDownload } = await loadApi({});
    await expect(
      requestDownload("LC08_X", null, { sensor: "landsat", from: "2024-07-01", to: "2024-07-31" }),
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

describe("online ingest", () => {
  it("posts the actual file and selected collection ID as multipart", async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(new Response("{}"))
      .mockResolvedValueOnce(Response.json({ job_id: "server-job" }, { status: 202 }));
    vi.stubGlobal("fetch", fetchMock);
    const { probeGateway, ingestFile } = await loadApi({});
    await probeGateway();
    const file = new File(["workspace evidence"], "note.txt", { type: "text/plain" });
    await expect(ingestFile(file, "")).rejects.toThrow(/select an upload collection/i);
    expect(fetchMock).toHaveBeenCalledTimes(1);
    await expect(ingestFile(file, "col-from-picker")).resolves.toEqual({ job_id: "server-job" });
    const [url, options] = fetchMock.mock.calls[1];
    expect(url).toBe("/api/v1/ingest");
    expect(options.method).toBe("POST");
    expect(options.headers).toBeUndefined(); // the browser generates the multipart boundary
    const fields = options.body as FormData;
    expect(fields.get("collection_id")).toBe("col-from-picker");
    expect(fields.get("index_after")).toBe("true");
    const upload = fields.get("file") as File;
    expect(upload.name).toBe("note.txt");
    expect(await upload.text()).toBe("workspace evidence");
  });

  it("lists active collections and surfaces real gateway upload errors", async () => {
    vi.stubGlobal("fetch", vi.fn()
      .mockResolvedValueOnce(new Response("{}"))
      .mockResolvedValueOnce(Response.json([
        { id: "live", name: "Documents", archived: false },
        { id: "old", name: "Archived", archived: true },
      ]))
      .mockResolvedValueOnce(Response.json({ error: { message: "Invalid filename" } }, { status: 422 })));
    const { probeGateway, listUploadCollections, ingestFile } = await loadApi({});
    await probeGateway();
    await expect(listUploadCollections()).resolves.toEqual([{ id: "live", name: "Documents", archived: false }]);
    await expect(ingestFile(new File([""], "note.txt"), "live")).rejects.toThrow("Invalid filename");
  });
});

class FakeEventSource extends EventTarget {
  static current: FakeEventSource;
  static CLOSED = 2;
  readyState = 0;
  onopen?: () => void;
  onerror?: () => void;
  close = vi.fn();

  constructor(public url: string) {
    super();
    FakeEventSource.current = this;
  }

  progress(id: string, status: string, percent: number) {
    this.dispatchEvent(new MessageEvent("job.progress", {
      data: JSON.stringify({ id, status, percent }),
    }));
  }
}

describe("online job tracking", () => {
  async function onlineApi() {
    vi.stubGlobal("EventSource", FakeEventSource);
    const fetchMock = vi.fn().mockResolvedValueOnce(new Response("{}"));
    vi.stubGlobal("fetch", fetchMock);
    const api = await loadApi({});
    await api.probeGateway();
    return { ...api, fetchMock };
  }

  it.each(["error", "failed", "cancelled", "completed"])("closes on %s but not on a transport error", async (status) => {
    const { subscribeJob } = await onlineApi();
    const onEvent = vi.fn();
    const unsubscribe = subscribeJob("j", onEvent);
    const stream = FakeEventSource.current;
    expect(stream.url).toBe("/api/v1/events");
    stream.progress("different-job", "completed", 100);
    expect(onEvent).not.toHaveBeenCalled();
    stream.onerror?.();
    expect(onEvent).toHaveBeenLastCalledWith({ status: "reconnecting", progress: 0 });
    expect(stream.close).not.toHaveBeenCalled();
    stream.progress("j", "running", 45);
    stream.progress("j", status, 50);
    expect(stream.close).toHaveBeenCalledTimes(1);
    expect(onEvent).toHaveBeenLastCalledWith(expect.objectContaining({ status: status === "completed" ? "complete" : status }));
    unsubscribe();
    expect(stream.close).toHaveBeenCalledTimes(1);
  });

  it("opens a new stream when a failed handshake prevents native retries", async () => {
    const { subscribeJob } = await onlineApi();
    vi.useFakeTimers();
    const unsubscribe = subscribeJob("j", vi.fn());
    const first = FakeEventSource.current;
    first.readyState = FakeEventSource.CLOSED;
    first.onerror?.();
    await vi.advanceTimersByTimeAsync(2500);
    const second = FakeEventSource.current;
    expect(second).not.toBe(first);
    second.readyState = FakeEventSource.CLOSED;
    second.onerror?.();
    unsubscribe();
    await vi.advanceTimersByTimeAsync(2500);
    expect(FakeEventSource.current).toBe(second);
  });

  it("recovers a job that finished before SSE connected", async () => {
    const { subscribeJob, fetchMock } = await onlineApi();
    fetchMock.mockResolvedValueOnce(Response.json({
      id: "fast-job", status: "completed", percent: 100, result: { asset_id: "asset-123" },
    }));
    const onEvent = vi.fn();
    subscribeJob("fast-job", onEvent);
    FakeEventSource.current.onopen?.();
    await vi.waitFor(() => expect(onEvent).toHaveBeenCalledWith(expect.objectContaining({
      status: "complete", progress: 100, result: { asset_id: "asset-123" },
    })));
    expect(fetchMock).toHaveBeenLastCalledWith("/api/v1/jobs/fast-job", expect.anything());
    expect(FakeEventSource.current.close).toHaveBeenCalledOnce();
  });
});
