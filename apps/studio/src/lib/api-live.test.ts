import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

/**
 * Unit tests for the live-gateway additions (change: add-studio-knowledge-agent
 * §4, add-studio-training-lab §2): citation stripping, cold-start/readiness
 * helpers, and offline behaviour of the new gateway calls.
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

describe("parseCitationRefs", () => {
  it("extracts [n] numbers in order", async () => {
    const { parseCitationRefs } = await loadApi({});
    expect(parseCitationRefs("ET is 5.8 mm/day [1]. Published 1,180 mm/yr [2].")).toEqual([1, 2]);
    expect(parseCitationRefs("no refs here")).toEqual([]);
  });
});

describe("stripInvalidCitations", () => {
  it("keeps valid refs and strips out-of-range ones", async () => {
    const { stripInvalidCitations } = await loadApi({});
    const { text, invalid } = stripInvalidCitations("ET is 5.8 [1] and [9] mm/day [2].", 2);
    expect(text).toContain("[1]");
    expect(text).toContain("[2]");
    expect(text).not.toContain("[9]");
    expect(invalid).toEqual([9]);
  });

  it("strips [0] and dedupes invalid numbers", async () => {
    const { stripInvalidCitations } = await loadApi({});
    const { invalid } = stripInvalidCitations("[0] then [7] then [7] again", 3);
    expect(invalid).toEqual([0, 7]);
  });

  it("keeps everything when all refs are valid", async () => {
    const { stripInvalidCitations } = await loadApi({});
    const { text, invalid } = stripInvalidCitations("A [1] B [2]", 2);
    expect(text).toBe("A [1] B [2]");
    expect(invalid).toEqual([]);
  });
});

describe("cold-start / readiness helpers", () => {
  it("samplesToGraduation counts down to 30", async () => {
    const { samplesToGraduation, isColdStart } = await loadApi({});
    expect(samplesToGraduation(0)).toBe(30);
    expect(samplesToGraduation(12)).toBe(18);
    expect(samplesToGraduation(30)).toBe(0);
    expect(samplesToGraduation(45)).toBe(0);
    expect(isColdStart(29)).toBe(true);
    expect(isColdStart(30)).toBe(false);
  });

  it("readinessByKey groups labelled vs pending", async () => {
    const { readinessByKey } = await loadApi({});
    const rows = readinessByKey([
      { id: "1", kind: "classification", subject: "a", prediction: "wheat", confidence: 0.9, status: "accepted", key: "wheat__khuzestan" },
      { id: "2", kind: "classification", subject: "b", prediction: "wheat", confidence: 0.9, status: "pending", key: "wheat__khuzestan" },
      { id: "3", kind: "qa", subject: "c", prediction: "1,900 mm", confidence: 0.9, status: "rejected" },
    ]);
    expect(rows).toEqual([
      { key: "wheat__khuzestan", labelled: 1, pending: 1 },
      { key: "1,900 mm", labelled: 1, pending: 0 },
    ]);
  });

  it("predictionAbstained compares against the threshold", async () => {
    const { predictionAbstained } = await loadApi({});
    expect(predictionAbstained(0.5, 0.62)).toBe(true);
    expect(predictionAbstained(0.62, 0.62)).toBe(false);
    expect(predictionAbstained(0.9, 0.62)).toBe(false);
  });
});

describe("groundingState (KnowledgeView)", () => {
  it("classifies cited / synthesis-informed / uncited", async () => {
    const { groundingState } = await import("../views/KnowledgeView");
    expect(groundingState(0.9, 0.62, true)).toBe("cited");
    expect(groundingState(0.4, 0.62, true)).toBe("synthesis-informed");
    expect(groundingState(0.9, 0.62, false)).toBe("uncited");
  });
});

describe("splitFiles (ResourcesView)", () => {
  it("rejects unsupported extensions with a reason", async () => {
    const { splitFiles } = await import("../views/ResourcesView");
    const mk = (name: string) => new File(["x"], name);
    const { accepted, rejected } = splitFiles([mk("a.pdf"), mk("b.docx"), mk("c.tif"), mk("d.txt")]);
    expect(accepted.map((f) => f.name)).toEqual(["a.pdf", "c.tif", "d.txt"]);
    expect(rejected.map((r) => r.name)).toEqual(["b.docx"]);
    expect(rejected[0].reason).toMatch(/unsupported extension/i);
  });
});

describe("live gateway helpers (offline behaviour)", () => {
  it("listCollections rejects when the gateway is offline", async () => {
    const { listCollections } = await loadApi({});
    await expect(listCollections()).rejects.toThrow(/gateway offline/i);
  });

  it("listRois rejects when the gateway is offline", async () => {
    const { listRois } = await loadApi({});
    await expect(listRois()).rejects.toThrow(/gateway offline/i);
  });

  it("streamAgentChat rejects when the gateway is offline", async () => {
    const { streamAgentChat } = await loadApi({});
    await expect(streamAgentChat("hello", () => {})).rejects.toThrow(/gateway offline/i);
  });

  it("ingestFile rejects when the gateway is offline", async () => {
    const { ingestFile } = await loadApi({});
    await expect(ingestFile(new File(["x"], "a.pdf"), "col-1")).rejects.toThrow(/gateway offline/i);
  });
});
