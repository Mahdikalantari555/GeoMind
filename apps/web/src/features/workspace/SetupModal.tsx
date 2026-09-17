import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useCreateWorkspace, useOpenWorkspace, useUpdateSettings } from './hooks'
import { environmentApi } from '@/api/environment'

const DEFAULT_KILO_BASE_URL = 'https://api.kilo.ai/api/gateway/v1'
const DEFAULT_LLM_MODEL_ID = 'kilo-auto/free'
const DEFAULT_ONNX_MODEL = 'Xenova/all-MiniLM-L6-v2'
const DEFAULT_HF_ENDPOINT = 'https://huggingface.co'
const DEFAULT_EMBEDDING_ROOT = '~/.cache/huggingface'

const EMBEDDING_BACKENDS = ['hashing', 'llama-cpp', 'sentence-transformers', 'onnx'] as const
const LLM_PROVIDERS = ['api', 'llamacpp'] as const

export function SetupModal() {
  const { t } = useTranslation()
  const create = useCreateWorkspace()
  const open = useOpenWorkspace()
  const updateSettings = useUpdateSettings()
  const [tab, setTab] = useState<'create' | 'open'>('create')
  const [name, setName] = useState('')
  const [path, setPath] = useState('')
  const [offline, setOffline] = useState(false)
  const [llmProvider, setLlmProvider] = useState<'api' | 'llamacpp'>('api')
  const [llmBaseUrl, setLlmBaseUrl] = useState(DEFAULT_KILO_BASE_URL)
  const [llmModelId, setLlmModelId] = useState(DEFAULT_LLM_MODEL_ID)
  const [llmModelPath, setLlmModelPath] = useState('')
  const [llmApiKey, setLlmApiKey] = useState('')
  const [embeddingBackend, setEmbeddingBackend] = useState<'hashing' | 'llama-cpp' | 'sentence-transformers' | 'onnx'>('onnx')
  const [onnxModelName, setOnnxModelName] = useState(DEFAULT_ONNX_MODEL)
  const [hfEndpoint, setHfEndpoint] = useState(DEFAULT_HF_ENDPOINT)
  const [embeddingRoot, setEmbeddingRoot] = useState(DEFAULT_EMBEDDING_ROOT)
  const [error, setError] = useState<string | null>(null)

  const inputCls =
    'w-full rounded-md border border-gf-border bg-gf-bg px-3 py-2 text-sm outline-none focus:border-gf-accent'

  async function applyComputeConfig() {
    const env: Record<string, string> = {}
    if (hfEndpoint.trim()) env.HF_ENDPOINT = hfEndpoint.trim()
    if (embeddingRoot.trim()) env.GEOMEMORY_EMBEDDING_ROOT = embeddingRoot.trim()
    if (Object.keys(env).length > 0) {
      try {
        await environmentApi.setOverrides(env)
      } catch {
        // Best effort: downloads still work with server defaults.
      }
    }
  }

  async function submitCreate() {
    if (!name.trim()) return
    setError(null)
    try {
      await applyComputeConfig()
      const resp = await create.mutateAsync({
        path: path.trim(),
        name: name.trim(),
        offline,
      })
      void resp
      const settings: Record<string, unknown> = {
        llm_provider: llmProvider,
        llm_api_base_url: llmProvider === 'api' ? llmBaseUrl.trim() : null,
        llm_model_id: llmModelId.trim() || DEFAULT_LLM_MODEL_ID,
        model_path: llmProvider === 'llamacpp' ? llmModelPath.trim() || null : null,
        embedding_backend: embeddingBackend,
        onnx_model_name: onnxModelName.trim() || DEFAULT_ONNX_MODEL,
      }
      if (llmApiKey.trim()) {
        settings.llm_api_key = llmApiKey.trim()
      }
      await updateSettings.mutateAsync(settings)
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    }
  }

  async function submitOpen() {
    if (!path.trim()) return
    setError(null)
    try {
      await applyComputeConfig()
      await open.mutateAsync({ path: path.trim() })
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-gf-bg/80 p-4" data-testid="setup-modal">
      <div className="max-h-[90vh] w-full max-w-2xl overflow-y-auto rounded-lg border border-gf-border bg-gf-panel p-6 shadow-xl">
        <h1 className="text-xl font-semibold">{t('setup.title')}</h1>
        <p className="mt-1 text-sm text-gf-muted">{t('setup.hint')}</p>

        <div className="mt-4 flex gap-2 border-b border-gf-border">
          <button
            type="button"
            onClick={() => setTab('create')}
            className={`border-b-2 px-3 py-2 text-sm ${tab === 'create' ? 'border-gf-accent text-gf-text' : 'border-transparent text-gf-muted'}`}
          >
            {t('setup.createTab')}
          </button>
          <button
            type="button"
            onClick={() => setTab('open')}
            className={`border-b-2 px-3 py-2 text-sm ${tab === 'open' ? 'border-gf-accent text-gf-text' : 'border-transparent text-gf-muted'}`}
          >
            {t('setup.openTab')}
          </button>
        </div>

        {tab === 'create' ? (
          <div className="mt-4 space-y-4">
            <label className="block text-sm">
              {t('setup.workspaceName')}
              <input className={inputCls} value={name} onChange={(e) => setName(e.target.value)} placeholder={t('workspace.namePlaceholder')} />
            </label>
            <label className="block text-sm">
              {t('setup.workspacePath')}
              <input className={inputCls} value={path} onChange={(e) => setPath(e.target.value)} placeholder={t('setup.pathPlaceholder')} />
            </label>
          </div>
        ) : (
          <div className="mt-4">
            <label className="block text-sm">
              {t('setup.workspacePath')}
              <input className={inputCls} value={path} onChange={(e) => setPath(e.target.value)} placeholder={t('setup.pathPlaceholder')} />
            </label>
          </div>
        )}

        <div className="mt-4 flex items-center gap-2 text-sm">
          <input
            type="checkbox"
            checked={offline}
            onChange={(e) => setOffline(e.target.checked)}
          />
          {t('setup.offline')}
        </div>

        <div className="mt-4 grid grid-cols-2 gap-3">
          <label className="block text-sm">
            {t('setup.llmProvider')}
            <select className={inputCls} value={llmProvider} onChange={(e) => setLlmProvider(e.target.value as 'api' | 'llamacpp')}>
              {LLM_PROVIDERS.map((p) => <option key={p} value={p}>{p}</option>)}
            </select>
          </label>
          {llmProvider === 'api' ? (
            <label className="block text-sm">
              {t('setup.llmBaseUrl')}
              <input className={inputCls} value={llmBaseUrl} onChange={(e) => setLlmBaseUrl(e.target.value)} />
            </label>
          ) : (
            <label className="block text-sm">
              {t('setup.llmModelPath')}
              <input className={inputCls} value={llmModelPath} onChange={(e) => setLlmModelPath(e.target.value)} />
            </label>
          )}
          <label className="block text-sm">
            {t('setup.llmModelId')}
            <input className={inputCls} value={llmModelId} onChange={(e) => setLlmModelId(e.target.value)} />
          </label>
          <label className="block text-sm">
            {t('setup.llmApiKey')}
            <input className={inputCls} type="password" value={llmApiKey} onChange={(e) => setLlmApiKey(e.target.value)} autoComplete="off" />
          </label>
          <label className="block text-sm">
            {t('setup.embeddingBackend')}
            <select className={inputCls} value={embeddingBackend} onChange={(e) => setEmbeddingBackend(e.target.value as typeof embeddingBackend)}>
              {EMBEDDING_BACKENDS.map((b) => <option key={b} value={b}>{b}</option>)}
            </select>
          </label>
          {embeddingBackend === 'onnx' && (
            <label className="block text-sm">
              {t('setup.onnxModelName')}
              <input className={inputCls} value={onnxModelName} onChange={(e) => setOnnxModelName(e.target.value)} />
            </label>
          )}
          <label className="block text-sm">
            {t('setup.hfEndpoint')}
            <input className={inputCls} value={hfEndpoint} onChange={(e) => setHfEndpoint(e.target.value)} />
          </label>
          <label className="block text-sm">
            {t('setup.embeddingRoot')}
            <input className={inputCls} value={embeddingRoot} onChange={(e) => setEmbeddingRoot(e.target.value)} />
          </label>
        </div>

        {error && <p className="mt-3 text-sm text-gf-err" role="alert">{error}</p>}

        <div className="mt-5 flex justify-end gap-2">
          <button
            type="button"
            onClick={tab === 'create' ? submitCreate : submitOpen}
            disabled={create.isPending || open.isPending || (tab === 'create' && !name.trim()) || (tab === 'open' && !path.trim())}
            className="rounded-md bg-gf-accent px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
          >
            {tab === 'create' ? t('common.create') : t('common.open')}
          </button>
        </div>
      </div>
    </div>
  )
}
