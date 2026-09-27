import { useTranslation } from 'react-i18next'
import { cn } from '@/lib/utils'
import type { SearchModality } from '@/api/search'

const MODALITIES: SearchModality[] = ['text', 'image', 'both']

interface SearchModalityToggleProps {
  modalities: SearchModality
  onChange: (modalities: SearchModality) => void
}

export function SearchModalityToggle({ modalities, onChange }: SearchModalityToggleProps) {
  const { t } = useTranslation()

  return (
    <div className="flex rounded-md border border-gf-border p-0.5" role="tablist" aria-label={t('search.modalities.label')}>
      {MODALITIES.map((m) => (
        <button
          key={m}
          type="button"
          role="tab"
          aria-selected={modalities === m}
          onClick={() => onChange(m)}
          className={cn(
            'rounded px-3 py-1 text-xs font-medium capitalize transition-colors',
            modalities === m ? 'bg-gf-accent text-white' : 'text-gf-muted hover:text-gf-text'
          )}
          data-testid={`modality-${m}`}
        >
          {t(`search.modalities.${m}`)}
        </button>
      ))}
    </div>
  )
}
