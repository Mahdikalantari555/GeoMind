import { afterEach, describe, expect, it, vi } from "vitest";
import { listModelVersions, rollbackModel, probeGateway } from "./api";
import { formatLat, formatLon, makeFormatters } from "./i18n";

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

async function connect(response: Response) {
  const mock = vi
    .fn()
    .mockResolvedValueOnce(Response.json({}))
    .mockResolvedValueOnce(response);
  vi.stubGlobal("fetch", mock);
  await probeGateway();
  return mock;
}

describe("fourth audit counterexamples (studio)", () => {
  it("keeps the full sub-region key for rollback", async () => {
    await connect(
      Response.json({
        versions: [
          { key: ["crop", "r1", "north"], timestamp: "2026-01-01T00:00:00Z", version: 3, active: true },
        ],
      }),
    );
    const [version] = await listModelVersions();
    // Truncating to two segments rolls back a different model on the gateway.
    expect(version.key).toEqual(["crop", "r1", "north"]);
  });

  it("sends every key segment in the rollback body", async () => {
    const mock = await connect(Response.json({ rolled_back: true }));
    const fetchMock = vi.fn().mockResolvedValue(Response.json({ rolled_back: true }));
    vi.stubGlobal("fetch", fetchMock);
    await rollbackModel(["crop", "r1", "north"], 3);
    const body = JSON.parse(String((fetchMock.mock.calls[0][1] as RequestInit).body));
    expect(body.key).toEqual(["crop", "r1", "north"]);
    expect(mock).toBeDefined();
  });

  it("distinguishes two sub-regions that share a version number", async () => {
    await connect(
      Response.json({
        versions: [
          { key: ["crop", "r1", "north"], timestamp: "2026-01-01T00:00:00Z", version: 1 },
          { key: ["crop", "r1", "south"], timestamp: "2026-01-01T00:00:00Z", version: 1 },
        ],
      }),
    );
    const versions = await listModelVersions();
    expect(new Set(versions.map((v) => v.id)).size).toBe(2);
  });

  it("never labels a southern latitude as north", () => {
    // Buenos Aires (-34.6, -58.4) used to render as "34.6000°N 58.4000°E".
    expect(formatLat(-34.6)).toBe("34.6000°S");
    expect(formatLon(-58.4)).toBe("58.4000°W");
    expect(formatLat(31.6)).toBe("31.6000°N");
    expect(formatLon(48.3)).toBe("48.3000°E");
  });

  it("does not render a NaN date for an unparsable timestamp", () => {
    expect(makeFormatters("en").date("2026-13-45")).toBe("—");
  });
});
