// @vitest-environment jsdom
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({
  listProviders: vi.fn(),
  registerProvider: vi.fn(),
  connectProvider: vi.fn(),
  discoverModels: vi.fn(),
  updateWorkspaceSettings: vi.fn(),
  refreshLive: vi.fn(),
  updateSettings: vi.fn(),
  store: {} as Record<string, unknown>,
}));

vi.mock("@/lib/api", () => ({
  listProviders: mocks.listProviders,
  registerProvider: mocks.registerProvider,
  connectProvider: mocks.connectProvider,
  discoverModels: mocks.discoverModels,
  updateWorkspaceSettings: mocks.updateWorkspaceSettings,
  basemapTileUrl: (p: string) => `/api/v1/data/maps/tiles/${p}/{z}/{x}/{y}.png`,
  mapGlyphsUrl: () => "/api/v1/data/maps/glyphs/{fontstack}/{range}.pbf",
  previewUrlFor: (id: string, href: string) =>
    href ? `/api/v1/data/scenes/${id}/preview?url=${encodeURIComponent(href)}` : undefined,
  isDemo: () => false,
  isGatewayUp: () => true,
}));

vi.mock("@/lib/store", () => ({
  useStore: () => mocks.store,
}));

import { ProviderPicker } from "@/components/ProviderPicker";
import { Modal } from "@/components/Modal";
import { ScenePreview } from "@/views/AcquireView";

function setStore(overrides: Record<string, unknown> = {}) {
  Object.assign(mocks.store, {
    lang: "en",
    t: (k: string) => k,
    settings: {},
    updateSettings: mocks.updateSettings,
    refreshLive: mocks.refreshLive,
    ...overrides,
  });
}

beforeEach(() => {
  vi.clearAllMocks();
  localStorage.clear();
  mocks.listProviders.mockResolvedValue([
    { name: "OpenAI", base: "https://api.openai.com/v1", keyEnv: "K", configured: false },
  ]);
  mocks.discoverModels.mockResolvedValue(["gpt-4o"]);
  mocks.updateWorkspaceSettings.mockResolvedValue({});
  mocks.refreshLive.mockResolvedValue(undefined);
  setStore();
});

describe("ProviderPicker (T-078)", () => {
  it("registers a provider by name and HTTPS base", async () => {
    mocks.registerProvider.mockResolvedValue({
      name: "Acme", base: "https://llm.acme.test/v1", keyEnv: "K2",
    });
    render(<ProviderPicker />);
    await screen.findByText("OpenAI");

    fireEvent.click(screen.getByText("providerAdd"));
    fireEvent.change(screen.getByPlaceholderText("Acme Research"), {
      target: { value: "Acme" },
    });
    fireEvent.change(screen.getByPlaceholderText("https://provider.example/v1"), {
      target: { value: "https://llm.acme.test/v1" },
    });
    fireEvent.click(screen.getByText("providerRegister"));

    await waitFor(() =>
      expect(mocks.registerProvider).toHaveBeenCalledWith("Acme", "https://llm.acme.test/v1"),
    );
  });

  it("uses a password field and never writes the API key to localStorage", async () => {
    render(<ProviderPicker />);
    await screen.findByText("OpenAI");

    const key = screen.getByLabelText("providerKeyLabel") as HTMLInputElement;
    expect(key.type).toBe("password");
    expect(key.autocomplete).toBe("off");
    fireEvent.change(key, { target: { value: "sk-secret" } });

    fireEvent.click(screen.getByText("providerFetchModels"));
    const check = await screen.findByRole("checkbox");
    fireEvent.click(check);
    fireEvent.click(screen.getByRole("button", { name: /providerUse/ }));

    await waitFor(() => expect(mocks.updateWorkspaceSettings).toHaveBeenCalled());
    const patch = mocks.updateWorkspaceSettings.mock.calls[0][0] as Record<string, string>;
    expect(patch.llm_api_key).toBe("sk-secret");
    expect(patch.llm_provider).toBe("custom");
    const saved = localStorage.getItem("gm.provider-library.v1") ?? "{}";
    expect(saved).not.toContain("sk-secret");
  });
});

describe("ScenePreview (T-080)", () => {
  it("renders an <img> pointing at the gateway-proxied preview", () => {
    render(
      <ScenePreview
        sc={{
          id: "LC08_x", sensor: "landsat", acquired: "", cloud: 5, sunElev: null,
          path: "", row: "", thumbSeed: 1,
          previewUrl: "https://example.blob.core.windows.net/p.png",
        }}
      />,
    );
    const img = screen.getByRole("img") as HTMLImageElement;
    expect(img.getAttribute("src")).toContain("/api/v1/data/scenes/LC08_x/preview?url=");
    expect(img.getAttribute("src")).toContain(encodeURIComponent("https://example.blob.core.windows.net/p.png"));
  });

  it("falls back to a labelled placeholder when no preview exists", () => {
    render(
      <ScenePreview
        sc={{
          id: "LC08_y", sensor: "landsat", acquired: "", cloud: 5, sunElev: null,
          path: "", row: "", thumbSeed: 1,
        }}
      />,
    );
    expect(screen.queryByRole("img")).toBeNull();
    expect(screen.getByText("previewUnavailable")).toBeTruthy();
  });

  it("falls back on image load error", () => {
    render(
      <ScenePreview
        sc={{
          id: "LC08_z", sensor: "landsat", acquired: "", cloud: 5, sunElev: null,
          path: "", row: "", thumbSeed: 1, previewUrl: "https://x.test/p.png",
        }}
      />,
    );
    fireEvent.error(screen.getByRole("img"));
    expect(screen.queryByRole("img")).toBeNull();
    expect(screen.getByText("previewUnavailable")).toBeTruthy();
  });
});

describe("Modal accessibility (CORRECT-09)", () => {
  it("closes on Escape and traps focus between first and last control", () => {
    const onClose = vi.fn();
    render(
      <Modal open onClose={onClose} label="Test dialog">
        <button>First</button>
        <button>Last</button>
      </Modal>,
    );
    const dialog = screen.getByRole("dialog");
    expect(dialog.getAttribute("aria-modal")).toBe("true");

    const first = screen.getByText("First");
    const last = screen.getByText("Last");
    // jsdom does not move focus on Tab, so assert the explicit wrap that the
    // trap enforces at the boundaries.
    last.focus();
    fireEvent.keyDown(document, { key: "Tab" });
    expect(document.activeElement).toBe(first);
    first.focus();
    fireEvent.keyDown(document, { key: "Tab", shiftKey: true });
    expect(document.activeElement).toBe(last);

    fireEvent.keyDown(document, { key: "Escape" });
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("restores focus to the trigger on unmount", () => {
    const trigger = document.createElement("button");
    document.body.appendChild(trigger);
    trigger.focus();
    const { unmount } = render(
      <Modal open label="Test dialog">
        <button>Inside</button>
      </Modal>,
    );
    unmount();
    expect(document.activeElement).toBe(trigger);
    trigger.remove();
  });
});
