// @vitest-environment jsdom
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

type StreamEvent = {
  event: string;
  text?: string;
  id?: string;
  tool?: string;
  status?: string;
  code?: string;
  message?: string;
  conversationId?: string;
  final?: boolean;
};

const mocks = vi.hoisted(() => ({
  streamAgentChat: vi.fn(),
  getConversation: vi.fn(),
  listPlaybooks: vi.fn(),
  savePlaybook: vi.fn(),
  runPlaybook: vi.fn(),
  setMessages: vi.fn(),
  setConversationId: vi.fn(),
  setAgentDraft: vi.fn(),
  toast: vi.fn(),
  store: {} as Record<string, unknown>,
  messages: [] as unknown[],
  rerender: () => {},
}));

vi.mock("@/lib/api", () => ({
  streamAgentChat: mocks.streamAgentChat,
  getConversation: mocks.getConversation,
  listPlaybooks: mocks.listPlaybooks,
  runPlaybook: mocks.runPlaybook,
  savePlaybook: mocks.savePlaybook,
  normalizeCitationMarkers: (t: string) => t.replace(/\[S(\d+)\]/g, (_m: string, n: string) => `[${n}]`),
  stripInvalidCitations: (t: string) => ({ text: t, invalid: [] }),
}));

vi.mock("@/lib/store", async () => {
  const React = await import("react");
  return {
    useStore: () => {
      const [, force] = React.useState(0);
      mocks.rerender = () => force((n: number) => n + 1);
      return { ...mocks.store, messages: mocks.messages };
    },
    uid: (p: string) => `${p}-test`,
  };
});

vi.mock("@/views/KnowledgeView", () => ({
  ProvenanceDrawer: () => null,
  renderWithChips: (t: string) => t,
}));

import { AgentRail } from "@/components/AgentRail";

function setStore(overrides: Record<string, unknown> = {}) {
  mocks.messages = [];
  mocks.setMessages.mockImplementation((fn: (m: unknown[]) => unknown[]) => {
    mocks.messages = fn(mocks.messages);
    mocks.rerender();
  });
  mocks.setAgentDraft.mockImplementation((v: string) => {
    mocks.store.agentDraft = v;
    mocks.rerender();
  });
  Object.assign(mocks.store, {
    online: true,
    llmReady: true,
    setMessages: mocks.setMessages,
    agentDraft: "",
    setAgentDraft: mocks.setAgentDraft,
    conversationId: undefined,
    setConversationId: mocks.setConversationId,
    settings: { llmModel: "gpt-4o", groundingThreshold: 0.62 },
    lang: "en",
    t: (k: string) => k,
    toast: mocks.toast,
    activeRoi: null,
    ...overrides,
  });
}

const sse = (e: StreamEvent) => e;

beforeEach(() => {
  vi.clearAllMocks();
  mocks.listPlaybooks.mockResolvedValue([]);
  mocks.getConversation.mockResolvedValue({ tool_runs: [] });
  mocks.streamAgentChat.mockResolvedValue(undefined);
  setStore();
});

describe("AgentRail live chat (F-095)", () => {
  it("renders SSE tokens, tool cards and the conversation id handoff", async () => {
    mocks.streamAgentChat.mockImplementation(
      async (_text: string, onEvent: (e: StreamEvent) => void) => {
        onEvent(sse({ event: "conversation", conversationId: "conv-1" }));
        onEvent(sse({ event: "tool_start", id: "tc-1", tool: "geo_search" }));
        onEvent(sse({ event: "tool_end", id: "tc-1", tool: "geo_search", status: "ok (2 citations)" }));
        onEvent(sse({ event: "message", text: "Grounded [S1] answer", final: true }));
        onEvent(sse({ event: "done" }));
      },
    );
    mocks.getConversation.mockResolvedValue({
      tool_runs: [{
        id: "tc-1", tool: "geo_search", args_json: '{"q":"et"}', status: "ok",
        latency_ms: 42, error: null, from_cache: false,
      }],
    });

    render(<AgentRail />);
    fireEvent.change(screen.getByPlaceholderText("typeMessage"), { target: { value: "What is ET?" } });
    fireEvent.click(screen.getByRole("button", { name: /Send message/ }));

    await waitFor(() => expect(mocks.streamAgentChat).toHaveBeenCalledTimes(1));
    expect(mocks.setConversationId).toHaveBeenCalledWith("conv-1");
    expect(screen.getByText("Grounded [1] answer")).toBeTruthy();
    await waitFor(() => expect(screen.getByText("geo_search")).toBeTruthy());
    await waitFor(() => expect(mocks.getConversation).toHaveBeenCalledWith("conv-1"));
    await waitFor(() => expect(screen.getByText("42 ms")).toBeTruthy());
  });

  it("sets the degraded state when the gateway reports no LLM", async () => {
    mocks.streamAgentChat.mockImplementation(
      async (_text: string, onEvent: (e: StreamEvent) => void) => {
        onEvent(sse({ event: "error", code: "agent_not_ready", message: "Agent not initialized" }));
        onEvent(sse({ event: "done" }));
      },
    );
    render(<AgentRail />);
    fireEvent.change(screen.getByPlaceholderText("typeMessage"), { target: { value: "hello" } });
    fireEvent.click(screen.getByRole("button", { name: /Send message/ }));

    await waitFor(() => expect(screen.getByText("Agent not initialized")).toBeTruthy());
    expect(screen.getByText("configureLlm")).toBeTruthy();
  });

  it("never uses a scripted reply when the gateway is offline", async () => {
    setStore({ online: false });
    render(<AgentRail />);
    fireEvent.change(screen.getByPlaceholderText("typeMessage"), { target: { value: "hello" } });
    fireEvent.click(screen.getByRole("button", { name: /Send message/ }));
    expect(mocks.streamAgentChat).not.toHaveBeenCalled();
    expect(mocks.toast).toHaveBeenCalledWith("gatewayOfflineHint", "bad");
  });
});
