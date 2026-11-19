import { ProviderPicker } from "@/components/ProviderPicker";
import { FolderOpen, Languages, Server, ShieldCheck } from "lucide-react";
import { useStore } from "@/lib/store";
import { API_BASE, gatewayConfigured } from "@/lib/api";
import { Badge, Button, Card, Field, Mono, PageHeader } from "@/components/ui";

export function SettingsView() {
  const s = useStore();
  const st = s.settings;
  const u = s.updateSettings;
  return (
    <div className="scroll-thin h-full overflow-y-auto p-5">
      <PageHeader title={s.t("settings")} subtitle={`${s.t("privacy")}: ${s.settings.llmUrl || "—"} · ${s.settings.llmModel || "—"}`} />
      <div className="grid max-w-5xl gap-4 lg:grid-cols-2">
        <Card title={<span className="flex items-center gap-2"><FolderOpen className="h-3.5 w-3.5" /> {s.t("paths")}</span>}>
          <div className="space-y-3 p-3">
            <Field label="Workspace root (gateway)"><Mono>{s.online ? s.workspace || '—' : 'Unavailable'}</Mono></Field>
          </div>
        </Card>

        <Card title={<span className="flex items-center gap-2"><Server className="h-3.5 w-3.5" /> {s.t("llm")}</span>}>
          <div className="space-y-3 p-3">
            <ProviderPicker />
            <Field label="Grounding threshold" hint="Answers with top retrieval score below this value abstain.">
              <div className="flex items-center gap-3">
                <input type="range" min={0.3} max={0.95} step={0.01} value={st.groundingThreshold} onChange={(e) => u({ groundingThreshold: +e.target.value })} className="flex-1" dir="ltr" />
                <Mono className="w-10 text-end">{st.groundingThreshold.toFixed(2)}</Mono>
              </div>
            </Field>
          </div>
        </Card>

        <Card title={<span className="flex items-center gap-2"><Languages className="h-3.5 w-3.5" /> {s.t("language")} · {s.t("density")}</span>}>
          <div className="space-y-3 p-3">
            <Field label={s.t("language")}>
              <div className="flex gap-2">
                <Button variant={s.lang === "en" ? "primary" : "secondary"} onClick={() => s.setLang("en")}>English · LTR</Button>
                <Button variant={s.lang === "fa" ? "primary" : "secondary"} onClick={() => s.setLang("fa")}>فارسی · RTL</Button>
              </div>
            </Field>
            <Field label={s.t("density")}>
              <div className="flex gap-2">
                <Button variant={st.density === "compact" ? "primary" : "secondary"} onClick={() => u({ density: "compact" })}>{s.t("compact")}</Button>
                <Button variant={st.density === "comfortable" ? "primary" : "secondary"} onClick={() => u({ density: "comfortable" })}>{s.t("comfortable")}</Button>
              </div>
            </Field>
            <p className="text-[11.5px] text-muted">
              {s.t("epsg")} · {s.fmt.date(Date.now(), { dateStyle: "full" })} · {s.fmt.num(1234567.89)}
            </p>
          </div>
        </Card>

        <Card title={<span className="flex items-center gap-2"><ShieldCheck className="h-3.5 w-3.5" /> {s.t("gateway")}</span>}>
          <div className="space-y-2 p-3 text-[12.5px]">
            <div className="flex items-center gap-2">
              <span className="text-muted">VITE_GEOMIND_API</span>
              <Mono>{API_BASE || "Same origin · /api/v1"}</Mono>
              <Badge tone={s.online ? "ok" : gatewayConfigured ? "bad" : "warn"} className="ms-auto">
                {s.online ? "connected" : gatewayConfigured ? "unreachable" : "offline sample mode"}
              </Badge>
            </div>
            <p className="text-muted">
              When connected, the UI and the agent consume only <Mono>/api/v1</Mono> and subscribe to <Mono>job.progress</Mono> SSE events. Sample data and simulated jobs require an explicit demo build.
            </p>
          </div>
        </Card>
      </div>
    </div>
  );
}
