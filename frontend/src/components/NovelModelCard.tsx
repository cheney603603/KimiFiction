import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Cpu, X, Check, Loader2, RotateCcw } from 'lucide-react'
import { novelApi } from '../services/api'

const PROVIDERS = [
  { key: 'deepseek', label: 'DeepSeek', icon: '🔵', placeholder: 'deepseek-chat' },
  { key: 'openai', label: 'OpenAI', icon: '🟢', placeholder: 'gpt-4o-mini' },
  { key: 'kimi', label: 'Kimi', icon: '🔴', placeholder: 'kimi' },
  { key: 'yuanbao', label: '腾讯元宝', icon: '🟣', placeholder: 'yuanbao' },
]

interface Props {
  novelId: number
}

export function NovelModelCard({ novelId }: Props) {
  const queryClient = useQueryClient()
  const [open, setOpen] = useState(false)
  const [provider, setProvider] = useState('deepseek')
  const [model, setModel] = useState('')
  const [baseUrl, setBaseUrl] = useState('')

  const { data: eff } = useQuery({
    queryKey: ['novel-llm-config', novelId],
    queryFn: () => novelApi.llmConfigForNovel(novelId),
    enabled: !!novelId,
  })

  const { data: novel } = useQuery({
    queryKey: ['novel', novelId],
    queryFn: () => novelApi.get(novelId),
    enabled: !!novelId,
  })

  const saveMutation = useMutation({
    mutationFn: (data: { model_provider: string; model_name: string; model_base_url: string }) =>
      novelApi.update(novelId, data),
    onSuccess: () => {
      setOpen(false)
      queryClient.invalidateQueries({ queryKey: ['novel-llm-config', novelId] })
      queryClient.invalidateQueries({ queryKey: ['novel', novelId] })
    },
  })

  const clearMutation = useMutation({
    mutationFn: () =>
      novelApi.update(novelId, { model_provider: '', model_name: '', model_base_url: '' }),
    onSuccess: () => {
      setOpen(false)
      queryClient.invalidateQueries({ queryKey: ['novel-llm-config', novelId] })
      queryClient.invalidateQueries({ queryKey: ['novel', novelId] })
    },
  })

  const openEditor = () => {
    setProvider((novel as any)?.model_provider || eff?.provider || 'deepseek')
    setModel((novel as any)?.model_name || '')
    setBaseUrl((novel as any)?.model_base_url || '')
    setOpen(true)
  }

  const sourceBadge = () => {
    if (eff?.novel_override) return { text: '本书覆盖', cls: 'bg-indigo-100 text-indigo-700 dark:bg-indigo-900/40 dark:text-indigo-300' }
    if (eff?.uses_user_key) return { text: '我的Key', cls: 'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/40 dark:text-emerald-300' }
    return { text: '全局默认', cls: 'bg-gray-100 text-gray-600 dark:bg-gray-700 dark:text-gray-300' }
  }
  const badge = sourceBadge()

  return (
    <div className="bg-white dark:bg-gray-800 rounded-xl shadow-sm border border-gray-200 dark:border-gray-700">
      <div className="p-4 border-b border-gray-200 dark:border-gray-700 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="p-2 rounded-lg bg-slate-500/10">
            <Cpu className="h-5 w-5 text-slate-500" />
          </div>
          <div>
            <h2 className="font-semibold text-gray-900 dark:text-white">本书模型</h2>
            <p className="text-xs text-gray-500 dark:text-gray-400">
              优先级：本书覆盖 &gt; 我的Key &gt; 全局默认
            </p>
          </div>
        </div>
        <button
          onClick={openEditor}
          className="text-sm px-3 py-1.5 rounded-lg border border-gray-300 dark:border-gray-600 text-gray-700 dark:text-gray-300 hover:border-primary-600 hover:text-primary-600 transition-colors"
        >
          配置本书模型
        </button>
      </div>

      <div className="p-4 flex flex-wrap items-center gap-x-6 gap-y-2 text-sm">
        <div>
          <p className="text-xs text-gray-500 dark:text-gray-400">当前生效</p>
          <p className="font-medium text-gray-900 dark:text-white flex items-center gap-2">
            <span className="capitalize">{eff?.provider || '—'}</span>
            <span className="text-gray-400">/</span>
            <span>{eff?.model || '—'}</span>
          </p>
        </div>
        <div className="min-w-0 flex-1">
          <p className="text-xs text-gray-500 dark:text-gray-400">Base URL</p>
          <p className="text-gray-700 dark:text-gray-300 truncate max-w-[360px]" title={eff?.base_url}>
            {eff?.base_url || '—'}
          </p>
        </div>
        <span className={`px-2 py-0.5 rounded-full text-[11px] font-medium ${badge.cls}`}>
          {badge.text}
        </span>
        {!eff?.has_api_key && (
          <span className="px-2 py-0.5 rounded-full bg-amber-100 text-amber-700 dark:bg-amber-900/40 dark:text-amber-300 text-[11px] font-medium">
            无可用Key · 需在 API 配置 或本书配置中设置
          </span>
        )}
      </div>

      {open && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50" onClick={() => setOpen(false)}>
          <div className="bg-white dark:bg-gray-800 rounded-xl p-6 w-full max-w-md mx-4" onClick={(e) => e.stopPropagation()}>
            <div className="flex justify-between items-center mb-4">
              <h3 className="text-lg font-bold text-gray-900 dark:text-white">本书模型配置</h3>
              <button onClick={() => setOpen(false)} className="p-1 hover:bg-gray-100 dark:hover:bg-gray-700 rounded">
                <X className="h-5 w-5 text-gray-500" />
              </button>
            </div>

            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Provider</label>
                <select
                  value={provider}
                  onChange={(e) => setProvider(e.target.value)}
                  className="w-full px-3 py-2 bg-gray-50 dark:bg-gray-700 border border-gray-300 dark:border-gray-600 rounded-lg text-gray-900 dark:text-white"
                >
                  {PROVIDERS.map((p) => (
                    <option key={p.key} value={p.key}>{p.label}</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">模型名</label>
                <input
                  type="text"
                  value={model}
                  onChange={(e) => setModel(e.target.value)}
                  placeholder={PROVIDERS.find((p) => p.key === provider)?.placeholder}
                  className="w-full px-3 py-2 bg-gray-50 dark:bg-gray-700 border border-gray-300 dark:border-gray-600 rounded-lg text-gray-900 dark:text-white"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Base URL（可留空回落）</label>
                <input
                  type="text"
                  value={baseUrl}
                  onChange={(e) => setBaseUrl(e.target.value)}
                  placeholder="https://api.deepseek.com"
                  className="w-full px-3 py-2 bg-gray-50 dark:bg-gray-700 border border-gray-300 dark:border-gray-600 rounded-lg text-gray-900 dark:text-white"
                />
              </div>
              <p className="text-xs text-gray-500 dark:text-gray-400">
                留空的字段回落：我的Key（BYOK）→ 全局默认。切换 provider 后如需 Key，请在本页「API 配置」设置。
              </p>
            </div>

            <div className="mt-6 flex items-center gap-3">
              <button
                onClick={() => saveMutation.mutate({ model_provider: provider, model_name: model, model_base_url: baseUrl })}
                disabled={saveMutation.isPending}
                className="flex-1 py-2.5 bg-primary-600 text-white rounded-lg hover:bg-primary-700 disabled:opacity-50 flex items-center justify-center gap-2"
              >
                {saveMutation.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Check className="h-4 w-4" />}
                保存本书配置
              </button>
              {(novel as any)?.model_provider && (
                <button
                  onClick={() => clearMutation.mutate()}
                  disabled={clearMutation.isPending}
                  className="px-3 py-2.5 text-sm border border-gray-300 dark:border-gray-600 rounded-lg text-gray-600 dark:text-gray-400 hover:text-red-600 flex items-center gap-1.5"
                >
                  <RotateCcw className="h-4 w-4" />
                  清除覆盖
                </button>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
