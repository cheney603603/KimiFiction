import { useState, useEffect } from 'react'
import { BookOpen, Play, BarChart3, CheckCircle, XCircle, Clock, FileText, RefreshCw } from 'lucide-react'

// Types
interface ReferenceNovel {
  filename: string
  name: string
  author: string
  size_kb: number
  char_count: number
  word_count: number
}

interface DimResult {
  id: string
  name: string
  weight: number
  weight_pct: number
  total_rules: number
  passed: number
  failed: number
  score: number
  bar: string
  judgments: { rule_id: string; name: string; answer: string; reason: string }[]
}

interface EvalResult {
  success: boolean
  eval_type: string
  genre: string
  timestamp: string
  total_score: number
  rank: string
  api_calls: number
  dims: DimResult[]
  total_rules: number
  error?: string
}

interface EvalHistory {
  filename: string
  timestamp: string
  eval_type: string
  total_score: number
  rank: string
  api_calls: number
  genre: string
}

const RANK_COLORS: Record<string, string> = {
  S: 'bg-yellow-100 text-yellow-800 border-yellow-300',
  A: 'bg-green-100 text-green-800 border-green-300',
  B: 'bg-blue-100 text-blue-800 border-blue-300',
  C: 'bg-gray-100 text-gray-800 border-gray-300',
  D: 'bg-orange-100 text-orange-800 border-orange-300',
  F: 'bg-red-100 text-red-800 border-red-300',
}

const RANK_SCORES: Record<string, number> = {
  S: 90, A: 80, B: 70, C: 60, D: 50, F: 0,
}

export function Evaluation() {
  const [references, setReferences] = useState<ReferenceNovel[]>([])
  const [history, setHistory] = useState<EvalHistory[]>([])
  const [selectedFile, setSelectedFile] = useState<string>('')
  const [textContent, setTextContent] = useState<string>('')
  const [evalType, setEvalType] = useState<'llm' | 'keyword'>('llm')
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState<EvalResult | null>(null)
  const [tab, setTab] = useState<'reference' | 'history'>('reference')
  const [expandedDim, setExpandedDim] = useState<string | null>(null)
  const [apiError, setApiError] = useState<string>('')

  const apiBase = '/api/v1'

  // Load references
  const loadReferences = async () => {
    try {
      const res = await fetch(`${apiBase}/training/evaluation/references`, {
        headers: { Authorization: `Bearer ${localStorage.getItem('access_token') || ''}` },
      })
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const data = await res.json()
      setReferences(data.files || [])
    } catch (e: any) {
      setApiError(`加载参考小说失败: ${e.message}`)
    }
  }

  // Load history
  const loadHistory = async () => {
    try {
      const res = await fetch(`${apiBase}/training/evaluation/results?limit=20`, {
        headers: { Authorization: `Bearer ${localStorage.getItem('access_token') || ''}` },
      })
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const data = await res.json()
      setHistory(data.results || [])
    } catch (e: any) {
      setApiError(`加载历史失败: ${e.message}`)
    }
  }

  useEffect(() => {
    loadReferences()
    loadHistory()
  }, [])

  // Select a reference novel and load its content
  const selectReference = async (file: ReferenceNovel) => {
    setSelectedFile(file.filename)
    setApiError('')
    // Load text content from reference dir
    try {
      const res = await fetch(`${apiBase}/export/reference/${file.filename}`, {
        headers: { Authorization: `Bearer ${localStorage.getItem('access_token') || ''}` },
      })
      if (res.ok) {
        const blob = await res.blob()
        const text = await blob.text()
        setTextContent(text.slice(0, 50000))
      } else {
        // Try as plain text
        const res2 = await fetch(`/reference/${file.filename}`)
        if (res2.ok) {
          const text = await res2.text()
          setTextContent(text.slice(0, 50000))
        }
      }
    } catch {
      setApiError(`无法加载文件内容: ${file.filename}`)
    }
  }

  // Run evaluation
  const runEvaluation = async () => {
    if (!textContent.trim()) {
      setApiError('请先选择或输入小说文本')
      return
    }
    setLoading(true)
    setApiError('')
    setResult(null)
    try {
      const res = await fetch(`${apiBase}/training/evaluation/run`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${localStorage.getItem('access_token') || ''}`,
        },
        body: JSON.stringify({ text: textContent, eval_type: evalType }),
      })
      const data = await res.json()
      if (!data.success) throw new Error(data.error || '评测失败')
      setResult(data)
      loadHistory() // refresh history
    } catch (e: any) {
      setApiError(e.message)
    } finally {
      setLoading(false)
    }
  }

  // Rank badge
  const RankBadge = ({ rank, score }: { rank: string; score: number }) => (
    <span className={`inline-flex items-center gap-1 px-3 py-1 rounded-full border font-bold text-lg ${RANK_COLORS[rank] || ''}`}>
      {rank} <span className="text-sm font-normal">{score.toFixed(1)}</span>
    </span>
  )

  // Score bar
  const ScoreBar = ({ score, label, weight, passed, total }: { score: number; label: string; weight: number; passed: number; total: number }) => (
    <div className="mb-3">
      <div className="flex justify-between text-sm mb-1">
        <span className="font-medium">{label}</span>
        <span>
          <span className="font-bold text-lg">{score.toFixed(1)}</span>
          <span className="text-gray-400 text-xs"> /10</span>
          <span className="ml-2 text-gray-500 text-xs">({passed}/{total})</span>
          <span className="ml-2 text-gray-400 text-xs">{weight.toFixed(0)}%权重</span>
        </span>
      </div>
      <div className="h-3 bg-gray-200 dark:bg-gray-700 rounded-full overflow-hidden">
        <div
          className="h-full rounded-full transition-all duration-700"
          style={{
            width: `${score * 10}%`,
            background: score >= 8 ? '#22c55e' : score >= 6 ? '#3b82f6' : score >= 4 ? '#f59e0b' : '#ef4444',
          }}
        />
      </div>
    </div>
  )

  return (
    <div className="max-w-6xl mx-auto">
      {/* Header */}
      <div className="flex items-center gap-3 mb-6">
        <BarChart3 className="h-8 w-8 text-primary-600" />
        <div>
          <h1 className="text-2xl font-bold">八维 LLM Rubric 评测</h1>
          <p className="text-sm text-gray-500">基于 KimiFiction 8 维度 88 条规则的大模型评测系统</p>
        </div>
      </div>

      {/* Error */}
      {apiError && (
        <div className="mb-4 p-3 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg text-red-700 dark:text-red-300 text-sm">
          {apiError}
        </div>
      )}

      {/* Tabs */}
      <div className="flex gap-1 mb-4 bg-gray-100 dark:bg-gray-800 p-1 rounded-lg w-fit">
        <button
          onClick={() => setTab('reference')}
          className={`flex items-center gap-2 px-4 py-2 rounded-md text-sm font-medium transition-colors ${
            tab === 'reference' ? 'bg-white dark:bg-gray-700 shadow-sm' : 'hover:bg-gray-200 dark:hover:bg-gray-700'
          }`}
        >
          <BookOpen className="h-4 w-4" />
          选择小说
        </button>
        <button
          onClick={() => setTab('history')}
          className={`flex items-center gap-2 px-4 py-2 rounded-md text-sm font-medium transition-colors ${
            tab === 'history' ? 'bg-white dark:bg-gray-700 shadow-sm' : 'hover:bg-gray-200 dark:hover:bg-gray-700'
          }`}
        >
          <Clock className="h-4 w-4" />
          历史记录 ({history.length})
        </button>
      </div>

      {/* Reference Tab */}
      {tab === 'reference' && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Left: file list */}
          <div className="lg:col-span-1">
            <h3 className="text-sm font-semibold text-gray-500 uppercase mb-3">参考小说库</h3>
            <div className="space-y-2 max-h-[500px] overflow-y-auto">
              {references.length === 0 && (
                <p className="text-sm text-gray-400 py-4 text-center">暂无参考小说，请将 .txt 文件放入 reference 目录</p>
              )}
              {references.map((r) => (
                <button
                  key={r.filename}
                  onClick={() => selectReference(r)}
                  className={`w-full text-left p-3 rounded-lg border transition-colors ${
                    selectedFile === r.filename
                      ? 'border-primary-500 bg-primary-50 dark:bg-primary-900/20'
                      : 'border-gray-200 dark:border-gray-700 hover:border-primary-300 hover:bg-gray-50 dark:hover:bg-gray-800'
                  }`}
                >
                  <div className="font-medium text-sm truncate">{r.name}</div>
                  <div className="text-xs text-gray-500 mt-1">
                    {r.author !== '?' ? `作者: ${r.author} · ` : ''}{r.size_kb}KB · {r.word_count}字
                  </div>
                </button>
              ))}
            </div>
          </div>

          {/* Middle: text + controls */}
          <div className="lg:col-span-2 space-y-4">
            {/* Controls */}
            <div className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 p-4">
              <div className="flex flex-wrap items-center gap-3 mb-4">
                <span className="text-sm font-medium text-gray-600 dark:text-gray-300">评测模式:</span>
                <label className="flex items-center gap-2 text-sm">
                  <input
                    type="radio"
                    checked={evalType === 'llm'}
                    onChange={() => setEvalType('llm')}
                    className="accent-primary-600"
                  />
                  LLM 评测（DeepSeek，逐条判断 Yes/No）
                </label>
                <label className="flex items-center gap-2 text-sm text-gray-400">
                  <input
                    type="radio"
                    checked={evalType === 'keyword'}
                    onChange={() => setEvalType('keyword')}
                    className="accent-gray-400"
                    disabled
                  />
                  关键词评测（开发中）
                </label>
              </div>

              {selectedFile && (
                <div className="text-sm text-gray-500 mb-3 flex items-center gap-2">
                  <FileText className="h-4 w-4" />
                  已选择: <span className="font-medium">{selectedFile}</span>
                  <span className="text-gray-400">({textContent.length} 字)</span>
                </div>
              )}

              <button
                onClick={runEvaluation}
                disabled={loading || !textContent.trim()}
                className="flex items-center gap-2 px-5 py-2.5 bg-primary-600 hover:bg-primary-700 disabled:bg-gray-300 disabled:cursor-not-allowed text-white rounded-lg font-medium transition-colors"
              >
                {loading ? (
                  <>
                    <RefreshCw className="h-4 w-4 animate-spin" />
                    评测中... (约需 2-5 分钟，88 条规则)
                  </>
                ) : (
                  <>
                    <Play className="h-4 w-4" />
                    开始评测
                  </>
                )}
              </button>
            </div>

            {/* Text preview */}
            {textContent && (
              <div className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 p-4">
                <h4 className="text-sm font-semibold text-gray-500 uppercase mb-2">文本预览</h4>
                <pre className="text-sm text-gray-600 dark:text-gray-300 whitespace-pre-wrap line-clamp-20 font-mono">
                  {textContent.slice(0, 2000)}...
                </pre>
                <p className="text-xs text-gray-400 mt-2">共 {textContent.length} 字，用于评测: {Math.min(textContent.length, 20000)} 字</p>
              </div>
            )}

            {/* Result */}
            {result && result.success && (
              <div className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 p-6">
                {/* Summary */}
                <div className="flex flex-wrap items-center gap-4 mb-6 pb-4 border-b border-gray-200 dark:border-gray-700">
                  <div className="text-4xl font-bold text-gray-900 dark:text-white">{result.total_score.toFixed(1)}</div>
                  <div className="text-gray-400">/ 100</div>
                  <RankBadge rank={result.rank} score={result.total_score} />
                  <div className="text-sm text-gray-500 ml-auto">
                    {result.api_calls > 0 && `API 调用: ${result.api_calls}次`}
                    {result.timestamp && ` · ${result.timestamp}`}
                  </div>
                </div>

                {/* Dimension bars */}
                <h3 className="text-sm font-semibold text-gray-500 uppercase mb-4">各维度得分</h3>
                {[...result.dims]
                  .sort((a, b) => b.weight - a.weight)
                  .forEach((dim) => (
                    <div key={dim.id} className="mb-4">
                      <ScoreBar
                        score={dim.score}
                        label={dim.name}
                        weight={dim.weight * 100}
                        passed={dim.passed}
                        total={dim.total_rules}
                      />
                      <button
                        onClick={() => setExpandedDim(expandedDim === dim.id ? null : dim.id)}
                        className="text-xs text-primary-600 hover:text-primary-700 ml-1"
                      >
                        {expandedDim === dim.id ? '收起规则' : `查看 ${dim.total_rules} 条规则`}
                      </button>
                      {expandedDim === dim.id && (
                        <div className="mt-2 space-y-1">
                          {dim.judgments.map((j) => (
                            <div key={j.rule_id} className="flex items-start gap-2 text-xs py-1 px-2 rounded bg-gray-50 dark:bg-gray-900">
                              {j.answer.toLowerCase() === 'yes' ? (
                                <CheckCircle className="h-3.5 w-3.5 text-green-500 mt-0.5 shrink-0" />
                              ) : (
                                <XCircle className="h-3.5 w-3.5 text-red-400 mt-0.5 shrink-0" />
                              )}
                              <div>
                                <span className="font-medium text-gray-700 dark:text-gray-300">{j.name}</span>
                                <span className="ml-2 text-gray-400">[{j.rule_id}]</span>
                                {j.reason && <div className="text-gray-400 mt-0.5">{j.reason}</div>}
                              </div>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  ))}
              </div>
            )}
          </div>
        </div>
      )}

      {/* History Tab */}
      {tab === 'history' && (
        <div>
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-sm font-semibold text-gray-500 uppercase">最近评测记录</h3>
            <button onClick={loadHistory} className="text-sm text-primary-600 hover:text-primary-700 flex items-center gap-1">
              <RefreshCw className="h-3.5 w-3.5" /> 刷新
            </button>
          </div>
          {history.length === 0 ? (
            <p className="text-sm text-gray-400 py-8 text-center">暂无评测记录</p>
          ) : (
            <div className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 overflow-hidden">
              <table className="w-full text-sm">
                <thead className="bg-gray-50 dark:bg-gray-900">
                  <tr>
                    <th className="text-left px-4 py-3 font-medium text-gray-500">时间</th>
                    <th className="text-left px-4 py-3 font-medium text-gray-500">模式</th>
                    <th className="text-left px-4 py-3 font-medium text-gray-500">类型</th>
                    <th className="text-center px-4 py-3 font-medium text-gray-500">总分</th>
                    <th className="text-center px-4 py-3 font-medium text-gray-500">等级</th>
                    <th className="text-center px-4 py-3 font-medium text-gray-500">API调用</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100 dark:divide-gray-700">
                  {history.map((h, i) => (
                    <tr key={i} className="hover:bg-gray-50 dark:hover:bg-gray-700/50">
                      <td className="px-4 py-3 text-gray-600 dark:text-gray-400 font-mono text-xs">{h.timestamp}</td>
                      <td className="px-4 py-3">
                        <span className={`px-2 py-0.5 rounded text-xs font-medium ${
                          h.eval_type === 'llm' ? 'bg-blue-100 text-blue-700' : 'bg-gray-100 text-gray-600'
                        }`}>{h.eval_type.toUpperCase()}</span>
                      </td>
                      <td className="px-4 py-3 text-gray-600 dark:text-gray-400">{h.genre || '-'}</td>
                      <td className="px-4 py-3 text-center font-bold">{h.total_score.toFixed(1)}</td>
                      <td className="px-4 py-3 text-center"><RankBadge rank={h.rank} score={h.total_score} /></td>
                      <td className="px-4 py-3 text-center text-gray-400">{h.api_calls}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
