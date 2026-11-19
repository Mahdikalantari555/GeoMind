import { useState } from "react";
import { API_BASE } from "@/lib/api";
import { useStore } from "@/lib/store";
import { Button, inputCls } from "./ui";

type Provider = { name: string; base: string; keyEnv: string };
type Saved = Record<string, string[]>;
const storage = "gm.provider-library.v1";
async function request(path: string, init?: RequestInit) {
  const r = await fetch(`${API_BASE}/api/v1${path}`, init);
  const body = await r.json().catch(() => null);
  if (!r.ok) throw Error(body?.error?.message ?? `Gateway: HTTP ${r.status}`);
  return body;
}
export function ProviderPicker() {
  const s = useStore();
  const t = (en: string, fa: string) => (s.lang === "fa" ? fa : en);
  const [catalog, setCatalog] = useState<Provider[]>([]);
  const [name, select] = useState("");
  const [models, setModels] = useState<string[] | null>(null);
  const [filter,setFilter] = useState("");
  const [customBase,setCustomBase] = useState("");
  const [wizard,setWizard] = useState(false);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [saved, save] = useState<Saved>(() => {
    try {
      return JSON.parse(localStorage.getItem(storage) || "{}") || {};
    } catch {
      return {};
    }
  });
  const provider = catalog.find((p) => p.name === name);
  const selected = provider ? (saved[provider.base] ?? []) : [];
  async function run(fn: () => Promise<void>) {
    setBusy(true);
    setMessage("");
    try {
      await fn();
    } catch (e) {
      setMessage(String(e));
    } finally {
      setBusy(false);
    }
  }
  return (
    <fieldset disabled={busy} className="space-y-2 border-b border-line pb-3">
      <Button
        onClick={() =>
          run(async () => {
            const list: Provider[] = await request("/providers");
            setCatalog(list);
            select(list[0]?.name ?? "");
            setModels(null);
          })
        }
      >
        {t("Add provider", "افزودن ارائه‌دهنده")}
      </Button>
      <Button onClick={() => setWizard(!wizard)}>{t("Custom endpoint", "مقصد سفارشی")}</Button>
      {wizard && <div className="space-y-2"><label>{t("Operator-approved HTTPS base URL", "آدرس HTTPS تأییدشده توسط مدیر")}<input type="url" dir="ltr" className={inputCls} value={customBase} onChange={e => setCustomBase(e.target.value)} placeholder="https://provider.example/v1" /></label>
        <Button disabled={!customBase.trim()} onClick={() => run(async () => {
          const profile: Provider = await request('/providers/connect', {method:'POST', headers:{'Content-Type':'application/json'},body:JSON.stringify({base:customBase.trim()})});
          setCatalog(prev => [...prev.filter(p => p.name !== profile.name),profile]); select(profile.name); setModels(null); setFilter(''); setWizard(false);
          setMessage(t('Endpoint selected. Configure its dedicated gateway key, then fetch models.', 'مقصد انتخاب شد. کلید اختصاصی را روی سرور تنظیم کنید و فهرست مدل‌ها را بگیرید.'));
        })}>{t("Connect endpoint", "اتصال به مقصد")}</Button></div>}
      {provider && (
        <>
          <select
            aria-label={t("Provider", "ارائه‌دهنده")}
            className={inputCls}
            value={name}
            onChange={(e) => {
              select(e.target.value); setFilter("");
              setModels(null);
              setMessage("");
            }}
          >
            {catalog.map((p) => (
              <option key={p.name}>{p.name}</option>
            ))}
          </select>
          <small dir="ltr">
            {provider.base} · {provider.keyEnv}
          </small>
          <Button
            onClick={() =>
              run(async () =>
                setModels(
                  await request(
                    `/providers/${encodeURIComponent(name)}/models`,
                  ),
                ),
              )
            }
          >
            {t("Fetch models", "دریافت مدل‌ها")}
          </Button>
          {models?.length === 0 && (
            <p>{t("No models returned", "مدلی یافت نشد")}</p>
          )}
          {models && models.length > 0 && <input className={inputCls} aria-label={t("Filter models","فیلتر مدل‌ها")} placeholder={t("Filter models","فیلتر مدل‌ها")} value={filter} onChange={e => setFilter(e.target.value)}/>}
          <div className="max-h-40 overflow-auto">
            {models?.filter(id => id.toLowerCase().includes(filter.trim().toLowerCase())).map((id) => (
              <label key={id} className="flex gap-2">
                <input
                  type="checkbox"
                  checked={selected.includes(id)}
                  onChange={(e) => {
                    const next = {
                      ...saved,
                      [provider.base]: e.target.checked
                        ? [...selected, id]
                        : selected.filter((m) => m !== id),
                    };
                    try {
                      localStorage.setItem(storage, JSON.stringify(next));
                      save(next);
                    } catch {
                      setMessage(
                        t(
                          "Browser storage unavailable",
                          "ذخیره در مرورگر ممکن نیست",
                        ),
                      );
                    }
                  }}
                />
                <span dir="ltr">{id}</span>
              </label>
            ))}
          </div>
          {selected.filter(id=>models && !models.includes(id)).map(id=><Button key={id} onClick={()=>{const next={...saved,[provider.base]:selected.filter(m=>m!==id)};try{localStorage.setItem(storage,JSON.stringify(next));save(next);}catch{setMessage('Browser storage unavailable');}}}>{t('Remove unavailable model','حذف مدل ناموجود')}: {id}</Button>)}
          {selected.filter(id=>models?.includes(id)).map((id) => (
            <Button
              key={id}
              onClick={() =>
                run(async () => {
                  await request("/workspace/settings", {
                    method: "PUT",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({
                      llm_provider: "api",
                      llm_model_id: id,
                      llm_api_base_url: provider.base,
                      llm_api_key_env: provider.keyEnv,
                    }),
                  });
                  s.updateSettings({ llmUrl: provider.base, llmModel: id });
                  setMessage(t("Applied to workspace", "در فضای کار اعمال شد"));
                })
              }
            >
              {t("Use", "فعال کن")}: {id}
            </Button>
          ))}{" "}
        </>
      )}
      <p role="status">{busy ? t("Connecting…", "در حال اتصال…") : message}</p>
    </fieldset>
  );
}
