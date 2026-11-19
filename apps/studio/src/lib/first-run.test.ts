import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

/**
 * Unit tests for the Studio workspace lifecycle client
 * (change: add-studio-first-run-workspace §1.2 / §4.1).
 */

type FetchHandler = (url: string, init?: RequestInit) => unknown;

/** Route-style fetch stub: handler result becomes the Response payload. */
function stubFetch(handler: FetchHandler) {
  const fetch = vi.fn().mockImplementation((url: string, init?: RequestInit) => {
    const body = handler(String(url), init);
    const ok = !(body as { error?: unknown }).error;
    return Promise.resolve({
      ok,
      status: ok ? 200 : 400,
      statusText: ok ? "OK" : "Error",
      json: () => Promise.resolve(body),
    });
  });
  vi.stubGlobal("fetch", fetch);
  return fetch;
}

async function loadApi(env: Record<string, string> = {}) {
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
  vi.unstubAllGlobals();
});

describe("workspace lifecycle client", () => {
  it("creates a workspace with name only (path defaults to the platform root)", async () => {
    const fetch = stubFetch((url, init) => {
      if (url.endsWith("/health")) return { status: "ok" };
      if (url.endsWith("/workspace/create")) {
        expect(JSON.parse(init?.body as string)).toEqual({ name: "karkheh", path: "" });
        return { status: "open", path: "D:/workspaces/karkheh", settings: { name: "karkheh" } };
      }
      throw new Error("unexpected fetch " + url);
    });
    const { createWorkspace, probeGateway } = await loadApi();
    await probeGateway();
    await expect(createWorkspace("karkheh")).resolves.toMatchObject({ status: "open", name: "karkheh" });
    expect(fetch).toHaveBeenCalledTimes(2);
  });

  it("surfaces the gateway error code on 409 workspace_exists", async () => {
    stubFetch((url) => {
      if (url.endsWith("/health")) return { status: "ok" };
      return { error: { code: "workspace_exists", message: "already exists" } };
    });
    const { createWorkspace, isWorkspaceRequiredError, probeGateway } = await loadApi();
    await probeGateway();
    const err = (await createWorkspace("karkheh").then(
      () => null,
      (e: unknown) => e,
    )) as unknown as { code?: string; message: string } | null;
    expect(err?.code).toBe("workspace_exists");
    expect(err?.message).toContain("already exists");
    expect(isWorkspaceRequiredError(err)).toBe(false);
  });

  it("surfaces workspace_not_found on a failed open", async () => {
    stubFetch((url) => {
      if (url.endsWith("/health")) return { status: "ok" };
      return { error: { code: "workspace_not_found", message: "No workspace found at X." } };
    });
    const { openWorkspace, probeGateway } = await loadApi();
    await probeGateway();
    const err = (await openWorkspace("D:/nowhere").then(
      () => null,
      (e: unknown) => e,
    )) as unknown as { code?: string } | null;
    expect(err?.code).toBe("workspace_not_found");
  });

  it("maps workspace_not_open to the actionable-error predicate", async () => {
    const { isWorkspaceRequiredError } = await loadApi();
    expect(isWorkspaceRequiredError(Object.assign(new Error("x"), { code: "workspace_not_open" }))).toBe(true);
    expect(isWorkspaceRequiredError(Object.assign(new Error("x"), { code: "invalid_request" }))).toBe(false);
    expect(isWorkspaceRequiredError(new Error("plain"))).toBe(false);
    expect(isWorkspaceRequiredError(undefined)).toBe(false);
  });

  it("reads workspace status and name", async () => {
    stubFetch((url) => {
      if (url.endsWith("/health")) return { status: "ok" };
      if (url.endsWith("/workspace/suggestions")) return { suggestions: [] };
      if (url.endsWith("/workspace")) return { status: "closed", path: null, settings: null };
      throw new Error("unexpected fetch " + url);
    });
    const { getWorkspace, probeGateway } = await loadApi();
    await probeGateway();
    await expect(getWorkspace()).resolves.toMatchObject({ status: "closed", path: null, name: null });
  });

  it("normalizes workspace suggestions", async () => {
    stubFetch((url) => {
      if (url.endsWith("/health")) return { status: "ok" };
      if (url.endsWith("/workspace/suggestions")) {
        return { suggestions: [{ path: "D:/workspaces/karkheh" }, { path: "D:/workshops", name: "" }] };
      }
      throw new Error("unexpected fetch " + url);
    });
    const { fetchWorkspaceSuggestions, probeGateway } = await loadApi();
    await probeGateway();
    const list = await fetchWorkspaceSuggestions();
    expect(list[0]).toEqual({ path: "D:/workspaces/karkheh", name: "karkheh" });
    expect(list[1].name).toBe("workshops");
  });
});
