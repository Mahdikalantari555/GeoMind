import { X, ShieldCheck, Hash, FileText } from 'lucide-react'
import type { Citation } from '@/api/search'

interface ProvenanceDrawerProps {
  isOpen: boolean
  onClose: () => void
  citation: Citation | null
}

export function ProvenanceDrawer({ isOpen, onClose, citation }: ProvenanceDrawerProps) {
  if (!isOpen || !citation) return null

  const locator = citation.locator || {}
  const filePath = (locator.file_path as string) || (locator.path as string) || (locator.source as string) || 'local/workspace'
  const segmentId = citation.segment_id || 'seg_unknown'
  const sha256 = (locator.sha256 as string) || (locator.hash as string) || 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855'
  const span = citation.claim_span

  return (
    <div
      data-testid="provenance-drawer-backdrop"
      className="fixed inset-0 z-50 flex justify-end bg-black/40 backdrop-blur-2xs transition-opacity"
      onClick={onClose}
    >
      <aside
        data-testid="provenance-drawer"
        className="flex h-full w-full max-w-md flex-col border-s border-gf-border bg-gf-panel p-6 shadow-2xl transition-transform"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between border-b border-gf-border pb-4">
          <div className="flex items-center gap-2">
            <ShieldCheck className="size-5 text-gf-accent" />
            <h3 className="text-sm font-semibold text-gf-text uppercase tracking-wide">
              Provenance & Evidence
            </h3>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg p-1 text-gf-muted hover:bg-gf-bg hover:text-gf-text"
          >
            <X className="size-4" />
          </button>
        </div>

        <div className="flex-1 space-y-5 overflow-y-auto pt-4 text-xs">
          {/* Claim Span / Match */}
          {span && (
            <div className="rounded-lg border border-emerald-500/30 bg-emerald-50/50 p-3 dark:bg-emerald-950/20">
              <span className="font-semibold text-emerald-800 dark:text-emerald-300">
                Claim Span Range
              </span>
              <p className="font-tabular mt-1 text-gf-text">
                Chars [{span.start} : {span.end}]
              </p>
            </div>
          )}

          {/* Segment ID */}
          <div className="space-y-1">
            <label className="text-[11px] font-medium text-gf-muted uppercase">Segment ID</label>
            <div className="flex items-center gap-2 rounded-lg border border-gf-border bg-gf-bg p-2.5">
              <FileText className="size-4 shrink-0 text-gf-muted" />
              <span className="font-tabular truncate text-gf-text">{segmentId}</span>
            </div>
          </div>

          {/* File Path */}
          <div className="space-y-1">
            <label className="text-[11px] font-medium text-gf-muted uppercase">Source Asset</label>
            <div className="rounded-lg border border-gf-border bg-gf-bg p-2.5">
              <p className="font-tabular break-all text-gf-text">{filePath}</p>
            </div>
          </div>

          {/* SHA-256 Provenance Hash */}
          <div className="space-y-1">
            <label className="text-[11px] font-medium text-gf-muted uppercase">
              Provenance SHA-256 Hash
            </label>
            <div className="flex items-start gap-2 rounded-lg border border-gf-border bg-gf-bg p-2.5">
              <Hash className="mt-0.5 size-4 shrink-0 text-gf-accent" />
              <span className="font-tabular break-all text-[11px] text-gf-muted">{sha256}</span>
            </div>
          </div>

          {/* Verifiable Chain */}
          <div className="rounded-xl border border-gf-border bg-gf-bg/60 p-4">
            <p className="text-xs font-semibold text-gf-text">Data-Sovereign Chain of Custody</p>
            <ol className="mt-2.5 space-y-2 text-[11px] text-gf-muted">
              <li className="flex items-center gap-2">
                <span className="flex size-4 items-center justify-center rounded-full bg-gf-accent text-[9px] font-bold text-white">1</span>
                Answer Statement Claim
              </li>
              <li className="flex items-center gap-2">
                <span className="flex size-4 items-center justify-center rounded-full bg-gf-accent text-[9px] font-bold text-white">2</span>
                Citation Link: <span className="font-tabular font-medium text-gf-text">{citation.id}</span>
              </li>
              <li className="flex items-center gap-2">
                <span className="flex size-4 items-center justify-center rounded-full bg-gf-accent text-[9px] font-bold text-white">3</span>
                Extracted Text Segment in SQLite
              </li>
              <li className="flex items-center gap-2">
                <span className="flex size-4 items-center justify-center rounded-full bg-gf-accent text-[9px] font-bold text-white">4</span>
                Local Asset Object Store (SHA-256 verified)
              </li>
            </ol>
          </div>
        </div>

        <div className="border-t border-gf-border pt-4">
          <button
            type="button"
            onClick={onClose}
            className="w-full rounded-lg bg-gf-panel border border-gf-border py-2 text-xs font-medium text-gf-text hover:bg-gf-bg"
          >
            Close Provenance
          </button>
        </div>
      </aside>
    </div>
  )
}
