import { X } from 'lucide-react'

export interface DetailNeighbor {
  id: string
  label: string
  color?: string
  relation?: string
}

interface EntityDetailPanelProps {
  kind: string
  kindLabel: string
  color: string
  name: string
  aliases?: string[]
  summary?: string
  state: Record<string, unknown>
  fields: { key: string; label: string }[]
  metas?: { label: string; value: string }[]
  neighbors: DetailNeighbor[]
  onNeighborClick?: (id: string) => void
  onClose?: () => void
}

function fmt(v: unknown): string {
  if (v === null || v === undefined || v === '') return ''
  if (Array.isArray(v)) return (v as unknown[]).map(x => String(x)).join('、')
  if (typeof v === 'object') return JSON.stringify(v)
  return String(v)
}

/** 实体/角色详情卡片：图谱、地图、知识库通用 */
export function EntityDetailPanel({
  kindLabel,
  color,
  name,
  aliases,
  summary,
  state,
  fields,
  metas = [],
  neighbors,
  onNeighborClick,
  onClose,
}: EntityDetailPanelProps) {
  return (
    <div className="w-80 max-w-full bg-white dark:bg-gray-800 rounded-xl shadow-xl border border-gray-200 dark:border-gray-700 overflow-hidden">
      <div className="p-4 border-b border-gray-100 dark:border-gray-700 flex items-start justify-between gap-2">
        <div className="min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <span
              className="px-2 py-0.5 rounded-full text-xs font-medium text-white"
              style={{ background: color }}
            >
              {kindLabel}
            </span>
            <h3 className="font-bold text-gray-900 dark:text-white truncate">{name}</h3>
          </div>
          {aliases && aliases.length > 0 && (
            <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
              别名：{aliases.join('、')}
            </p>
          )}
        </div>
        {onClose && (
          <button
            onClick={onClose}
            className="p-1 text-gray-400 hover:text-gray-600 dark:hover:text-gray-200 shrink-0"
          >
            <X className="h-4 w-4" />
          </button>
        )}
      </div>

      <div className="p-4 space-y-3 max-h-[60vh] overflow-y-auto">
        {summary && (
          <p className="text-sm text-gray-600 dark:text-gray-300 leading-relaxed">{summary}</p>
        )}

        {metas.length > 0 && (
          <div className="flex flex-wrap gap-2">
            {metas.map(m => (
              <span
                key={m.label}
                className="text-xs px-2 py-1 rounded-md bg-gray-100 dark:bg-gray-700/60 text-gray-600 dark:text-gray-300"
              >
                {m.label}：{m.value}
              </span>
            ))}
          </div>
        )}

        {fields.filter(f => fmt(state[f.key])).length > 0 && (
          <div className="space-y-2 pt-1">
            {fields.map(f => {
              const v = fmt(state[f.key])
              if (!v) return null
              const isList = Array.isArray(state[f.key])
              return (
                <div key={f.key} className="text-sm">
                  <span className="text-gray-500 dark:text-gray-400">{f.label}</span>
                  {isList ? (
                    <div className="flex flex-wrap gap-1 mt-1">
                      {(state[f.key] as unknown[]).map((item, i) => (
                        <span
                          key={i}
                          className="px-2 py-0.5 rounded bg-gray-100 dark:bg-gray-700/60 text-xs text-gray-700 dark:text-gray-200"
                        >
                          {String(item)}
                        </span>
                      ))}
                    </div>
                  ) : (
                    <p className="text-gray-800 dark:text-gray-100 leading-relaxed">{v}</p>
                  )}
                </div>
              )
            })}
          </div>
        )}

        {neighbors.length > 0 && (
          <div className="pt-2 border-t border-gray-100 dark:border-gray-700">
            <p className="text-xs font-medium text-gray-500 dark:text-gray-400 mb-2">
              关联 · {neighbors.length}
            </p>
            <div className="flex flex-wrap gap-1.5">
              {neighbors.map(n => (
                <button
                  key={n.id}
                  onClick={() => onNeighborClick?.(n.id)}
                  className="inline-flex items-center gap-1 px-2 py-1 rounded-full border border-gray-200 dark:border-gray-600 text-xs text-gray-700 dark:text-gray-200 hover:border-primary-500 hover:text-primary-600 dark:hover:text-primary-300 transition-colors"
                >
                  <span className="w-2 h-2 rounded-full" style={{ background: n.color || '#9ca3af' }} />
                  {n.label}
                  {n.relation && <span className="text-gray-400 dark:text-gray-500">· {n.relation}</span>}
                </button>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}