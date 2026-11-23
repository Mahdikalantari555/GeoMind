import { useCallback, useEffect, useState } from "react";
import {
  connectProvider,
  discoverModels,
  listProviders,
  registerProvider,
  updateWorkspaceSettings,
} from "@/lib/api";
import { useStore } from "@/lib/store";
import type { Provider } from "@/lib/types";
import { Button, inputCls } from "./ui";

type Saved = Record<string, string[]>;
const storage = "gm.provider-library.v1";

export function ProviderPicker() {
  const s = useStore();
  const [catalog, setCatalog] = useState<Provider[]>([]);
  const [name, select] = useState("");
  const [models, setModels] = useState<string[] | null>(null);
  const [filter, setFilter] = useState("");
  const [customBase, setCustomBase] = useState("");
  const [customName, setCustomName] = useState("");
  const [registerWizard, setRegisterWizard] = useState(false);
  const [connectWizard, setConnectWizard] = useState(false);
  // The API key is session state only: never written to localStorage, logs or
  // the workspace. It is sent once, in the settings PUT body.
  const [apiKey, setApiKey] = useState("");
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const [message, setMessage] = useState("");
  const [saved, save] = useState<Saved>(() => {
    try {
      const raw: unknown = JSON.parse(localStorage.getItem(storage) || "{}");
      if (!raw || typeof raw !== "object" || Array.isArray(raw)) return {};
      return Object.fromEntries(
        Object.entries(raw).filter(
          ([, ids]) => Array.isArray(ids) && ids.every((id) => typeof id === "string"),
        ),
      );
    } catch {
      return {};
    }
  });

  const load = useCallback(async (signal?: AbortSignal) => {
    setLoading(true);
    try {
      const list = await listProviders(signal);
      if (!Array.isArray(list)) throw new Error("Invalid provider catalog");
      setCatalog(list);
      select((current) => (list.some((p) => p.name === current) ? current : (list[0]?.name ?? "")));
      setModels(null);
    } catch (error) {
      if ((error as Error).name !== "AbortError") setMessage(String(error));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    void load(controller.signal);
    return () => controller.abort();
  }, [load]);

  const provider = catalog.find((p) => p.name === name);
  const selected = provider ? (saved[provider.base] ?? []) : [];

  async function run(action: () => Promise<void>) {
    setBusy(true);
    setMessage("");
    try {
      await action();
    } catch (error) {
      setMessage(String(error));
    } finally {
      setBusy(false);
    }
  }

  function rememberModel(id: string, checked: boolean) {
    if (!provider) return;
    const next = {
      ...saved,
      [provider.base]: checked ? [...selected, id] : selected.filter((m) => m !== id),
    };
    try {
      localStorage.setItem(storage, JSON.stringify(next));
      save(next);
    } catch {
      setMessage(s.t("providerStorageUnavailable"));
    }
  }

  function applyModel(id: string) {
    if (!provider) return;
    void run(async () => {
      const patch: Record<string, unknown> = {
        llm_provider: "custom",
        llm_model_id: id,
        llm_api_base_url: provider.base,
        llm_api_key_env: provider.keyEnv,
      };
      // A key typed here is passed once and then cleared. Never persisted.
      if (apiKey.trim()) patch.llm_api_key = apiKey.trim();
      await updateWorkspaceSettings(patch);
      setApiKey("");
      s.updateSettings({ llmUrl: provider.base, llmModel: id });
      setMessage(s.t("providerApplied"));
      await s.refreshLive();
    });
  }

  return (
    <fieldset disabled={busy} className="space-y-2 border-b border-line pb-3">
      <div className="flex gap-2">
        <Button onClick={() => setRegisterWizard((v) => !v)}>{s.t("providerAdd")}</Button>
        <Button onClick={() => setConnectWizard((v) => !v)}>{s.t("providerCustom")}</Button>
      </div>

      {registerWizard && (
        <div className="space-y-2">
          <label className="block">
            {s.t("providerName")}
            <input
              className={inputCls}
              value={customName}
              onChange={(e) => setCustomName(e.target.value)}
              placeholder="Acme Research"
            />
          </label>
          <label className="block">
            {s.t("providerBase")}
            <input
              type="url"
              dir="ltr"
              className={inputCls}
              value={customBase}
              onChange={(e) => setCustomBase(e.target.value)}
              placeholder="https://provider.example/v1"
            />
          </label>
          <Button
            disabled={!customName.trim() || !customBase.trim()}
            onClick={() =>
              run(async () => {
                const entry = await registerProvider(customName.trim(), customBase.trim());
                setCatalog((prev) => [...prev.filter((p) => p.name !== entry.name), entry]);
                select(entry.name);
                setModels(null);
                setFilter("");
                setRegisterWizard(false);
                setCustomName("");
                setCustomBase("");
                setMessage(s.t("providerRegistered"));
              })
            }
          >
            {s.t("providerRegister")}
          </Button>
        </div>
      )}

      {connectWizard && (
        <div className="space-y-2">
          <label className="block">
            {s.t("providerConnectHint")}
            <input
              type="url"
              dir="ltr"
              className={inputCls}
              value={customBase}
              onChange={(e) => setCustomBase(e.target.value)}
              placeholder="https://provider.example/v1"
            />
          </label>
          <Button
            disabled={!customBase.trim()}
            onClick={() =>
              run(async () => {
                const entry = await connectProvider(customBase.trim());
                setCatalog((prev) => [...prev.filter((p) => p.name !== entry.name), entry]);
                select(entry.name);
                setModels(null);
                setFilter("");
                setConnectWizard(false);
                setCustomBase("");
              })
            }
          >
            {s.t("providerConnect")}
          </Button>
        </div>
      )}

      {loading && <p role="status">{s.t("providerLoading")}</p>}
      {!loading && catalog.length === 0 && <p>{s.t("providerEmpty")}</p>}

      {provider && (
        <>
          <select
            aria-label={s.t("providerSelect")}
            className={inputCls}
            value={name}
            onChange={(e) => {
              select(e.target.value);
              setFilter("");
              setModels(null);
              setMessage("");
              setApiKey("");
            }}
          >
            {catalog.map((p) => (
              <option key={p.name} value={p.name}>
                {p.name}
              </option>
            ))}
          </select>
          <small dir="ltr" className="block text-muted">
            {provider.base} · {provider.keyEnv} ·{" "}
            {provider.configured ? s.t("providerConfigured") : s.t("providerKeyMissing")}
          </small>
          <label className="block">
            {s.t("providerKeyLabel")}
            <input
              type="password"
              autoComplete="off"
              className={inputCls}
              value={apiKey}
              onChange={(e) => setApiKey(e.target.value)}
            />
          </label>
          <Button
            onClick={() =>
              run(async () => {
                const controller = new AbortController();
                setModels(await discoverModels(provider.name, controller.signal));
              })
            }
          >
            {s.t("providerFetchModels")}
          </Button>
          {models?.length === 0 && <p>{s.t("providerNoModels")}</p>}
          {models && models.length > 0 && (
            <input
              className={inputCls}
              aria-label={s.t("providerFilterModels")}
              placeholder={s.t("providerFilterModels")}
              value={filter}
              onChange={(e) => setFilter(e.target.value)}
            />
          )}
          <div className="max-h-40 overflow-auto">
            {models
              ?.filter((id) => id.toLowerCase().includes(filter.trim().toLowerCase()))
              .map((id) => (
                <label key={id} className="flex gap-2">
                  <input
                    type="checkbox"
                    checked={selected.includes(id)}
                    onChange={(e) => rememberModel(id, e.target.checked)}
                  />
                  <span dir="ltr">{id}</span>
                </label>
              ))}
          </div>
          {selected
            .filter((id) => models && !models.includes(id))
            .map((id) => (
              <Button key={id} onClick={() => rememberModel(id, false)}>
                {s.t("providerRemoveUnavailable")}: {id}
              </Button>
            ))}
          {selected
            .filter((id) => models?.includes(id))
            .map((id) => (
              <Button key={id} onClick={() => applyModel(id)}>
                {s.t("providerUse")}: {id}
              </Button>
            ))}
        </>
      )}
      <p role="status">{busy ? s.t("providerConnecting") : message}</p>
    </fieldset>
  );
}
