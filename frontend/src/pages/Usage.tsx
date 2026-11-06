import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import {
  PieChart, Pie, Cell, Tooltip, Legend, ResponsiveContainer,
  BarChart, Bar, XAxis, YAxis, CartesianGrid,
} from 'recharts'
import { Loader2, Gauge, RefreshCw } from 'lucide-react'
import { novelApi, usageApi } from '../services/api'

const COLORS = ['#38bdf8', '#f472b6', '#a78bfa', '#fbbf24', '#34d399', '#fb7185']

interface UsageSummary {
  total_calls: number
  total_tokens: number
  total_tokens_in: number
  total_tokens_out: number
  total_retries: number
  total_errors: number
  by_model: Record<string, { calls: number; tokens_in: number; tokens_out: number; retries: number; errors: number }>
}

interface NovelUsage {
  novel_id: number
  total_calls: number
  total_tokens: number
  total_tokens_in: number
  total_tokens_out: number
  total_retries: number
  error_calls: number
  by_phase: Record<string, { calls: number; tokens_in: number; tokens_out: number; retries: number; errors: number }>
  by_chapter: Record<string, { calls: number; tokens_in: number; tokens_out: number; retries: number; errors: number }>
}

function fmt(n: number): string {
  return (n ?? 0).toLocaleString()
}

export function Usage() {
  const [novelId, setNovelId] = useState<number | null>(null)

  const novelsQuery = useQuery({ queryKey: ['novels'], queryFn: () => novelApi.list() })
  const modelsQuery = useQuery({ queryKey: ['usage-models'], queryFn: () => usageApi.models() })
  const novelQuery = useQuery({
    queryKey: ['usage-novel', novelId],
    queryFn: () => usageApi.novelUsage(novelId as number),
    enabled: novelId !== null,
  })

  if (modelsQuery.isLoading) {
    return (
      <div className="flex justify-center items-center h-64">
        <Loader2 className="h-8 w-8 animate-spin text-primary-600" />
      </div>
    )
  }

  const models = (modelsQuery.data as UsageSummary | undefined)
  const novels = (novelsQuery.data as { items?: { id: number; title: string }[] } | undefined)?.items || []
  const nv = novelQuery.data as NovelUsage | undefined

  const kpis = [
    ['总调用', models ? fmt(models.total_calls) : '-'],
    ['总 Token', models ? fmt(models.total_tokens) : '-'],
    ['输入', models ? fmt(models.total_tokens_in) : '-'],
    ['输出', models ? fmt(models.total_tokens_out) : '-'],
    ['重试次数', models ? fmt(models.total_retries) : '-'],
    ['失败', models ? fmt(models.total_errors) : '-'],
  ]

  const modelData = Object.entries(models?.by_model || {}).map(([name, m]) => ({
    name,
    value: m.tokens_in + m.tokens_out,
    calls: m.calls,
    retries: m.retries,
  }))

  const phaseData = Object.entries(nv?.by_phase || {}).map(([name, m]) => ({
    name,
    tokens: m.tokens_in + m.tokens_out,
    retries: m.retries,
  }))

  const chapterData = Object.entries(nv?.by_chapter || {}).map(([name, m]) => ({
    name,
    tokens: m.tokens_in + m.tokens_out,
    retries: m.retries,
  }))

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 dark:text-white">LLM 用量看板</h1>
          <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
            每次调用的 token 精确统计（stream_options.include_usage）：按模型 / 阶段 / 章节
          </p>
        </div>
        <button
          onClick={() => { modelsQuery.refetch(); novelQuery.refetch() }}
          className="flex items-center gap-2 px-3 py-2 text-sm font-medium bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-700"
        >
          <RefreshCw className="h-4 w-4" /> 刷新
        </button>
      </div>

      {/* KPI 卡 */}
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
        {kpis.map(([k, v]) => (
          <div key={k} className="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 p-4">
            <div className="text-2xl font-bold text-gray-900 dark:text-white">{v}</div>
            <div className="text-xs text-gray-500 dark:text-gray-400 mt-1 flex items-center gap-1">
              <Gauge className="h-3 w-3" /> {k}
            </div>
          </div>
        ))}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* 按模型 */}
        <div className="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 p-5">
          <h2 className="text-base font-semibold text-gray-900 dark:text-white mb-3">按模型 Token（全局）</h2>
          <ResponsiveContainer width="100%" height={260}>
            <PieChart>
              <Pie data={modelData} dataKey="value" nameKey="name" outerRadius={90} label>
                {modelData.map((_, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
              </Pie>
              <Tooltip formatter={(v: any) => fmt(Number(v))} />
              <Legend />
            </PieChart>
          </ResponsiveContainer>
          {modelData.length === 0 && (
            <p className="text-sm text-gray-400 mt-2">暂无用量数据——生成过章节后这里会显示按模型分布</p>
          )}
        </div>

        {/* 小说选择 + 按章节 */}
        <div className="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 p-5">
          <div className="flex items-center justify-between mb-3">
            <h2 className="text-base font-semibold text-gray-900 dark:text-white">按章节 Token（单本书）</h2>
            <select
              value={novelId ?? ''}
              onChange={(e) => setNovelId(e.target.value ? Number(e.target.value) : null)}
              className="px-3 py-1.5 text-sm bg-gray-50 dark:bg-gray-700 border border-gray-200 dark:border-gray-600 rounded-lg text-gray-900 dark:text-white"
            >
              <option value="">选择一本书…</option>
              {novels.map((n) => (
                <option key={n.id} value={n.id}>{n.title}</option>
              ))}
            </select>
          </div>
          {novelId === null ? (
            <p className="text-sm text-gray-400 py-10 text-center">选择一本书后展示其按章节的 token 与重试分布</p>
          ) : novelQuery.isLoading ? (
            <div className="flex justify-center items-center h-48"><Loader2 className="h-6 w-6 animate-spin text-primary-600" /></div>
          ) : (
            <ResponsiveContainer width="100%" height={260}>
              <BarChart data={chapterData}>
                <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
                <XAxis dataKey="name" tick={{ fill: '#94a3b8', fontSize: 12 }} />
                <YAxis tick={{ fill: '#94a3b8' }} />
                <Tooltip cursor={{ fill: 'rgba(51,65,85,.4)' }} />
                <Bar dataKey="tokens" name="tokens" fill="#a78bfa" radius={[4, 4, 0, 0]} />
                <Bar dataKey="retries" name="重试" fill="#fbbf24" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          )}
        </div>
      </div>

      {/* 按阶段 */}
      <div className="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 p-5">
        <h2 className="text-base font-semibold text-gray-900 dark:text-white mb-1">按阶段 Token</h2>
        <p className="text-xs text-gray-400 mb-3">
          {novelId ? `当前展示 ${novels.find((n) => n.id === novelId)?.title || '该书'} 的阶段分布；未选书时展示全局按模型汇总。` : '选择一本书后展示 writer/reader/review 等阶段分布'}
        </p>
        {novelId !== null && nv && Object.keys(nv.by_phase).length > 0 ? (
          <ResponsiveContainer width="100%" height={240}>
            <BarChart data={phaseData} layout="vertical" margin={{ left: 110 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
              <XAxis type="number" tick={{ fill: '#94a3b8' }} />
              <YAxis type="category" dataKey="name" width={100} tick={{ fill: '#cbd5e1', fontSize: 12 }} />
              <Tooltip cursor={{ fill: 'rgba(51,65,85,.4)' }} />
              <Bar dataKey="tokens" fill="#34d399" radius={[0, 4, 4, 0]} />
            </BarChart>
          </ResponsiveContainer>
        ) : (
          <p className="text-sm text-gray-400 py-8 text-center">
            所选书本暂无阶段分布（历史批次的 phase 未归属，新生成章节会带 writer/reader/review 阶段）
          </p>
        )}
      </div>
    </div>
  )
}
