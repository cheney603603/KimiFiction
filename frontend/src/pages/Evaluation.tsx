import { useState, useRef, useEffect } from 'react'
import { evaluationApi } from '../services/api'

// ─── 类型定义 ───────────────────────────────────────────────
interface RuleDetail {
  rule_id: string
  name: string
  desc: string
  answer: 'Yes' | 'No'
  reason: string
}

interface DimScore {
  id: string
  name: string
  weight: number
  weight_pct: number
  score: number
  passed: number
  failed: number
  total_rules: number
  rules: RuleDetail[]
}

interface BlockResult {
  block_index: number
  original_index: number
  total_blocks: number
  text_preview: string
  text_length: number
  score: number
  dims: DimScore[]
}

interface DimSummary {
  id: string
  name: string
  weight: number
  weight_pct: number
  avg_score: number
  bar: string
}

interface SampledResult {
  success: boolean
  error?: string
  total_score: number
  rank: string
  api_calls: number
  timestamp: string
  sampling: {
    total_blocks_in_text: number
    sampled_blocks: number
    max_bytes_per_block: number
  }
  dims: DimSummary[]
  blocks: BlockResult[]
  total_rules: number
  history_id?: number
}

interface ReferenceNovel {
  filename: string
  size: number
  size_kb: number
}

// 历史记录类型
interface HistoryItem {
  id: number
  source_type: string
  source_name: string | null
  genre: string
  total_score: number
  rank: string
  num_blocks: number
  sampled_blocks: number
  api_calls: number
  created_at: string
}

interface HistoryResponse {
  success: boolean
  total: number
  page: number
  page_size: number
  total_pages: number
  data: HistoryItem[]
}

// ─── 本地存储键名 ───────────────────────────────────────────
const STORAGE_KEY = 'kimi_evaluation_state'

interface SavedState {
  result: SampledResult | null
  params: {
    inputMode: 'file' | 'text'
    selectedFile: string
    customText: string
    numBlocks: number
    maxBytesPerBlock: number
    genre: string
  }
  timestamp: number
}

// 保存状态到本地存储
const saveState = (state: SavedState) => {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(state))
  } catch (e) {
    console.error('保存状态失败:', e)
  }
}

// 从本地存储加载状态
const loadState = (): SavedState | null => {
  try {
    const saved = localStorage.getItem(STORAGE_KEY)
    if (saved) {
      return JSON.parse(saved)
    }
  } catch (e) {
    console.error('加载状态失败:', e)
  }
  return null
}

// 清除本地存储
const clearState = () => {
  try {
    localStorage.removeItem(STORAGE_KEY)
  } catch (e) {
    console.error('清除状态失败:', e)
  }
}

// ─── 工具函数 ───────────────────────────────────────────────
const rankColor: Record<string, string> = {
  S: 'text-yellow-400',
  A: 'text-green-400',
  B: 'text-blue-400',
  C: 'text-orange-400',
  D: 'text-red-400',
  F: 'text-gray-400',
}

const scoreColor = (score: number) => {
  if (score >= 8) return 'text-green-400'
  if (score >= 6) return 'text-blue-400'
  if (score >= 4) return 'text-orange-400'
  return 'text-red-400'
}

const ScoreBar = ({ score, max = 10 }: { score: number; max?: number }) => {
  const pct = Math.round((score / max) * 100)
  const color =
    score >= 8 ? 'bg-green-500' : score >= 6 ? 'bg-blue-500' : score >= 4 ? 'bg-orange-500' : 'bg-red-500'
  return (
    <div className="flex items-center gap-2">
      <div className="flex-1 h-2 bg-gray-700 rounded-full overflow-hidden">
        <div className={`h-full rounded-full transition-all ${color}`} style={{ width: `${pct}%` }} />
      </div>
      <span className={`text-sm font-mono w-8 text-right ${scoreColor(score)}`}>{score}</span>
    </div>
  )
}

// ─── 主组件 ─────────────────────────────────────────────────
export function Evaluation() {
  // 参考小说列表
  const [novels, setNovels] = useState<ReferenceNovel[]>([])
  const [novelsLoaded, setNovelsLoaded] = useState(false)

  // 从本地存储恢复状态
  const savedState = loadState()

  // 运行状态
  const [running, setRunning] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [result, setResult] = useState<SampledResult | null>(savedState?.result || null)

  // 流式进度状态
  const [progress, setProgress] = useState<{
    currentBlock: number
    totalBlocks: number
    apiCalls: number
    status: string
  } | null>(null)

  // 使用 ref 保持运行状态，避免闭包问题
  const abortControllerRef = useRef<AbortController | null>(null)

  // 展开状态
  const [expandedBlock, setExpandedBlock] = useState<number | null>(null)
  const [expandedDim, setExpandedDim] = useState<Record<string, boolean>>({})

  // 恢复保存的参数
  const [inputMode, setInputMode] = useState<'file' | 'text'>(savedState?.params?.inputMode || 'file')
  const [selectedFile, setSelectedFile] = useState<string>(savedState?.params?.selectedFile || '')
  const [customText, setCustomText] = useState<string>(savedState?.params?.customText || '')
  const [numBlocks, setNumBlocks] = useState(savedState?.params?.numBlocks || 5)
  const [maxBytesPerBlock, setMaxBytesPerBlock] = useState(savedState?.params?.maxBytesPerBlock || 10000)
  const [genre, setGenre] = useState(savedState?.params?.genre || '玄幻')

  // 历史记录状态
  const [history, setHistory] = useState<HistoryItem[]>([])
  const [historyPage, setHistoryPage] = useState(1)
  const [historyTotalPages, setHistoryTotalPages] = useState(1)
  const [historyLoading, setHistoryLoading] = useState(false)
  const [expandedHistory, setExpandedHistory] = useState<number | null>(null)
  const [historyDetail, setHistoryDetail] = useState<SampledResult | null>(null)
  const [historyDetailLoading, setHistoryDetailLoading] = useState(false)

  // 加载参考小说列表
  const loadNovels = async () => {
    if (novelsLoaded) return
    try {
      const res = await evaluationApi.getReferences()
      setNovels(res.files || [])
      setNovelsLoaded(true)
    } catch (e: any) {
      setError('加载参考小说失败：' + (e?.response?.data?.detail || e.message))
    }
  }

  // 加载历史记录
  const loadHistory = async (page: number = 1) => {
    setHistoryLoading(true)
    try {
      const res: HistoryResponse = await evaluationApi.getHistory(page, 15)
      if (res.success) {
        setHistory(res.data)
        setHistoryPage(res.page)
        setHistoryTotalPages(res.total_pages)
      }
    } catch (e: any) {
      console.error('加载历史记录失败:', e)
    } finally {
      setHistoryLoading(false)
    }
  }

  // 加载历史记录详情
  const loadHistoryDetail = async (historyId: number) => {
    if (expandedHistory === historyId) {
      setExpandedHistory(null)
      setHistoryDetail(null)
      return
    }
    setHistoryDetailLoading(true)
    setExpandedHistory(historyId)
    try {
      const res = await evaluationApi.getHistoryDetail(historyId)
      if (res.success && res.data?.result_data) {
        setHistoryDetail(res.data.result_data)
      }
    } catch (e: any) {
      console.error('加载历史记录详情失败:', e)
    } finally {
      setHistoryDetailLoading(false)
    }
  }

  // 组件挂载时加载历史记录
  useEffect(() => {
    loadHistory(1)
  }, [])

  // 获取评测文本
  const getEvalText = async (): Promise<string | null> => {
    if (inputMode === 'text') {
      if (!customText.trim()) {
        setError('请输入要评测的文本')
        return null
      }
      return customText.trim()
    }
    if (!selectedFile) {
      setError('请选择一个参考小说文件')
      return null
    }
    try {
      const data = await evaluationApi.getReferenceContent(selectedFile)
      return data.content
    } catch (e: any) {
      setError('读取文件失败：' + e.message)
      return null
    }
  }

  // 清理函数
  useEffect(() => {
    return () => {
      if (abortControllerRef.current) {
        abortControllerRef.current.abort()
      }
    }
  }, [])

  // 当结果或参数变化时保存到本地存储
  useEffect(() => {
    saveState({
      result,
      params: {
        inputMode,
        selectedFile,
        customText,
        numBlocks,
        maxBytesPerBlock,
        genre,
      },
      timestamp: Date.now(),
    })
  }, [result, inputMode, selectedFile, customText, numBlocks, maxBytesPerBlock, genre])

  // 清除历史结果
  const handleClearResult = () => {
    setResult(null)
    clearState()
  }

  // 开始评测（流式）
  const handleRun = async () => {
    setError(null)
    setResult(null)
    setProgress(null)
    setExpandedBlock(null)
    setExpandedDim({})

    const text = await getEvalText()
    if (!text) return

    setRunning(true)
    abortControllerRef.current = new AbortController()

    try {
      const token = localStorage.getItem('access_token')
      const response = await fetch('/api/v1/training/evaluation/run-sampled', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': token ? `Bearer ${token}` : '',
        },
        body: JSON.stringify({
          text,
          num_blocks: numBlocks,
          max_bytes_per_block: maxBytesPerBlock,
          eval_type: 'llm',
          genre,
          stream: true,
        }),
        signal: abortControllerRef.current.signal,
      })

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}))
        throw new Error(errorData.detail || `HTTP ${response.status}`)
      }

      const reader = response.body?.getReader()
      if (!reader) {
        throw new Error('无法读取响应流')
      }

      const decoder = new TextDecoder()
      let buffer = ''
      let finalResult: SampledResult | null = null

      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop() || ''

        for (const line of lines) {
          if (!line.trim()) continue
          try {
            const event = JSON.parse(line)
            switch (event.type) {
              case 'init':
                setProgress({
                  currentBlock: 0,
                  totalBlocks: event.total_blocks || numBlocks,
                  apiCalls: 0,
                  status: '初始化完成，开始评测...',
                })
                break
              case 'progress':
                setProgress({
                  currentBlock: event.current_block || 0,
                  totalBlocks: event.total_blocks || numBlocks,
                  apiCalls: event.api_calls || 0,
                  status: event.message || `正在评测第 ${event.current_block} 块...`,
                })
                break
              case 'result':
                finalResult = event.data
                setProgress(prev => prev ? { ...prev, status: '评测完成！' } : null)
                break
              case 'error':
                throw new Error(event.error || '评测过程中出错')
            }
          } catch (e) {
            console.error('解析事件失败:', line, e)
          }
        }
      }

      if (finalResult) {
        setResult(finalResult)
        // 结果已自动保存到 localStorage
        // 刷新历史记录列表
        loadHistory(1)
      } else {
        setError('评测未完成，未收到结果')
      }
    } catch (e: any) {
      if (e.name === 'AbortError') {
        setError('评测已取消')
      } else {
        setError(e.message || '请求失败')
      }
    } finally {
      setRunning(false)
      setProgress(null)
      abortControllerRef.current = null
    }
  }

  // 取消评测
  const handleCancel = () => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort()
    }
  }

  const toggleDim = (key: string) =>
    setExpandedDim(prev => ({ ...prev, [key]: !prev[key] }))

  // ─── 渲染 ────────────────────────────────────────────────
  return (
    <div className="min-h-screen bg-gray-950 text-gray-100 p-6">
      <div className="max-w-5xl mx-auto space-y-6">

        {/* 标题 */}
        <div className="flex items-start justify-between">
          <div>
            <h1 className="text-2xl font-bold text-white">📊 小说质量评测</h1>
            <p className="text-gray-400 text-sm mt-1">
              从小说中均匀采样文本块，逐块进行八维 LLM Rubric 评测
            </p>
          </div>
          <a
            href="/evaluation/optimizer"
            className="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 text-white rounded-lg text-sm flex items-center gap-2"
          >
            <span>✨</span>
            规则优化
          </a>
        </div>

        {/* ── 输入区 ── */}
        <div className="bg-gray-900 rounded-xl border border-gray-800 p-5 space-y-4">
          <h2 className="text-sm font-semibold text-gray-300 uppercase tracking-wider">评测文本来源</h2>

          {/* 模式切换 */}
          <div className="flex gap-2">
            {(['file', 'text'] as const).map(mode => (
              <button
                key={mode}
                onClick={() => setInputMode(mode)}
                className={`px-4 py-1.5 rounded-lg text-sm font-medium transition-colors ${
                  inputMode === mode
                    ? 'bg-indigo-600 text-white'
                    : 'bg-gray-800 text-gray-400 hover:bg-gray-700'
                }`}
              >
                {mode === 'file' ? '📁 参考小说' : '✏️ 粘贴文本'}
              </button>
            ))}
          </div>

          {inputMode === 'file' ? (
            <div className="space-y-2">
              <button
                onClick={loadNovels}
                className="text-xs text-indigo-400 hover:text-indigo-300 underline"
              >
                {novelsLoaded ? `已加载 ${novels.length} 部小说` : '点击加载参考小说列表'}
              </button>
              {novels.length > 0 && (
                <select
                  value={selectedFile}
                  onChange={e => setSelectedFile(e.target.value)}
                  className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-gray-200 focus:outline-none focus:border-indigo-500"
                >
                  <option value="">— 选择小说文件 —</option>
                  {novels.map(n => (
                    <option key={n.filename} value={n.filename}>
                      {n.filename}（{n.size_kb} KB）
                    </option>
                  ))}
                </select>
              )}
            </div>
          ) : (
            <textarea
              value={customText}
              onChange={e => setCustomText(e.target.value)}
              placeholder="粘贴小说文本（建议 5 万字以上效果更好）..."
              rows={8}
              className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-gray-200 focus:outline-none focus:border-indigo-500 resize-y font-mono"
            />
          )}
        </div>

        {/* ── 采样参数 ── */}
        <div className="bg-gray-900 rounded-xl border border-gray-800 p-5 space-y-5">
          <h2 className="text-sm font-semibold text-gray-300 uppercase tracking-wider">采样参数</h2>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            {/* 采样块数 */}
            <div className="space-y-2">
              <div className="flex justify-between text-sm">
                <label className="text-gray-400">采样块数</label>
                <span className="text-indigo-400 font-mono font-bold">{numBlocks}</span>
              </div>
              <input
                type="range"
                min={1}
                max={20}
                value={numBlocks}
                onChange={e => setNumBlocks(Number(e.target.value))}
                className="w-full accent-indigo-500"
              />
              <div className="flex justify-between text-xs text-gray-600">
                <span>1（快速）</span>
                <span>20（精细）</span>
              </div>
              <p className="text-xs text-gray-500">从全文均匀抽取 {numBlocks} 个文本块进行评测</p>
            </div>

            {/* 每块最大字节 */}
            <div className="space-y-2">
              <div className="flex justify-between text-sm">
                <label className="text-gray-400">每块最大字节</label>
                <span className="text-indigo-400 font-mono font-bold">
                  {maxBytesPerBlock >= 1000 ? `${(maxBytesPerBlock / 1000).toFixed(0)}K` : maxBytesPerBlock}
                </span>
              </div>
              <input
                type="range"
                min={3000}
                max={30000}
                step={1000}
                value={maxBytesPerBlock}
                onChange={e => setMaxBytesPerBlock(Number(e.target.value))}
                className="w-full accent-indigo-500"
              />
              <div className="flex justify-between text-xs text-gray-600">
                <span>3K（精准）</span>
                <span>30K（宽泛）</span>
              </div>
              <p className="text-xs text-gray-500">约 {Math.round(maxBytesPerBlock / 3)} 汉字，以句号为边界截断</p>
            </div>

            {/* 题材 */}
            <div className="space-y-2">
              <label className="text-sm text-gray-400">小说题材</label>
              <select
                value={genre}
                onChange={e => setGenre(e.target.value)}
                className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-gray-200 focus:outline-none focus:border-indigo-500"
              >
                {['玄幻', '仙侠', '都市', '历史', '科幻', '悬疑', '言情', '武侠'].map(g => (
                  <option key={g} value={g}>{g}</option>
                ))}
              </select>
              <p className="text-xs text-gray-500">影响评测规则的侧重方向</p>
            </div>
          </div>
        </div>

        {/* ── 运行按钮 ── */}
        <div className="flex items-center gap-4">
          <button
            onClick={handleRun}
            disabled={running}
            className={`px-8 py-3 rounded-xl font-semibold text-base transition-all ${
              running
                ? 'bg-gray-700 text-gray-500 cursor-not-allowed'
                : 'bg-indigo-600 hover:bg-indigo-500 text-white shadow-lg shadow-indigo-900/40'
            }`}
          >
            {running ? '⏳ 评测中...' : result ? '🔄 重新评测' : '🚀 开始评测'}
          </button>
          {running && (
            <button
              onClick={handleCancel}
              className="px-4 py-2 rounded-lg text-sm bg-red-900/50 text-red-400 hover:bg-red-900/70 transition-colors"
            >
              取消
            </button>
          )}
          {result && !running && (
            <button
              onClick={handleClearResult}
              className="px-4 py-2 rounded-lg text-sm bg-gray-800 text-gray-400 hover:bg-gray-700 transition-colors"
            >
              清除结果
            </button>
          )}
        </div>

        {/* ── 历史结果提示 ── */}
        {result && !running && (
          <div className="bg-green-950/30 border border-green-800/50 rounded-lg p-3">
            <div className="flex items-center gap-2 text-sm text-green-400">
              <span>✓</span>
              <span>
                显示上次评测结果（{new Date(savedState?.timestamp || Date.now()).toLocaleString()}）
              </span>
            </div>
          </div>
        )}

        {/* ── 进度显示 ── */}
        {running && progress && (
          <div className="bg-indigo-950/30 border border-indigo-800/50 rounded-xl p-4 space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-sm text-indigo-300">{progress.status}</span>
              <span className="text-xs text-indigo-400 font-mono">
                API 调用: {progress.apiCalls}
              </span>
            </div>
            {progress.totalBlocks > 0 && (
              <div className="space-y-1">
                <div className="flex justify-between text-xs text-gray-500">
                  <span>进度</span>
                  <span>{progress.currentBlock} / {progress.totalBlocks} 块</span>
                </div>
                <div className="h-2 bg-gray-800 rounded-full overflow-hidden">
                  <div
                    className="h-full bg-indigo-500 rounded-full transition-all duration-300"
                    style={{
                      width: `${Math.round((progress.currentBlock / progress.totalBlocks) * 100)}%`
                    }}
                  />
                </div>
              </div>
            )}
          </div>
        )}

        {/* ── 错误提示 ── */}
        {error && (
          <div className="bg-red-950 border border-red-800 rounded-xl p-4 text-red-300 text-sm">
            ❌ {error}
          </div>
        )}

        {/* ── 结果区 ── */}
        {result && (
          <div className="space-y-6">

            {/* 总分卡片 */}
            <div className="bg-gray-900 rounded-xl border border-gray-800 p-6">
              <div className="flex items-start justify-between">
                <div>
                  <h2 className="text-lg font-bold text-white mb-1">评测结果</h2>
                  <p className="text-xs text-gray-500">
                    共 {result.sampling.total_blocks_in_text} 个文本块 · 采样 {result.sampling.sampled_blocks} 块 ·
                    每块最大 {(result.sampling.max_bytes_per_block / 1000).toFixed(0)}K 字节 ·
                    调用 API {result.api_calls} 次
                  </p>
                </div>
                <div className="text-right">
                  <div className={`text-6xl font-black ${rankColor[result.rank] || 'text-gray-400'}`}>
                    {result.rank}
                  </div>
                  <div className={`text-2xl font-bold mt-1 ${scoreColor(result.total_score / 10)}`}>
                    {result.total_score} <span className="text-sm text-gray-500">/ 10</span>
                  </div>
                </div>
              </div>

              {/* 各维度汇总 */}
              <div className="mt-5 grid grid-cols-1 md:grid-cols-2 gap-3">
                {result.dims.map(dim => (
                  <div key={dim.id} className="space-y-1">
                    <div className="flex justify-between text-xs text-gray-400">
                      <span>{dim.name}</span>
                      <span className="text-gray-500">{dim.weight_pct}%</span>
                    </div>
                    <ScoreBar score={dim.avg_score} />
                  </div>
                ))}
              </div>
            </div>

            {/* 逐块结果 */}
            <div className="space-y-3">
              <h2 className="text-sm font-semibold text-gray-300 uppercase tracking-wider">
                逐块详细结果（{result.blocks.length} 块）
              </h2>

              {result.blocks.map(block => (
                <div
                  key={block.block_index}
                  className="bg-gray-900 rounded-xl border border-gray-800 overflow-hidden"
                >
                  {/* 块头部 */}
                  <button
                    onClick={() =>
                      setExpandedBlock(expandedBlock === block.block_index ? null : block.block_index)
                    }
                    className="w-full flex items-center justify-between p-4 hover:bg-gray-800/50 transition-colors text-left"
                  >
                    <div className="flex items-center gap-3">
                      <span className="text-xs bg-gray-800 text-gray-400 px-2 py-0.5 rounded font-mono">
                        块 {block.block_index}/{block.total_blocks}
                      </span>
                      <span className="text-xs text-gray-500">
                        原文第 {block.original_index + 1} 块 · {block.text_length} 字符
                      </span>
                    </div>
                    <div className="flex items-center gap-3">
                      <span className={`text-lg font-bold font-mono ${scoreColor(block.score / 10)}`}>
                        {block.score}
                      </span>
                      <span className="text-gray-600 text-sm">
                        {expandedBlock === block.block_index ? '▲' : '▼'}
                      </span>
                    </div>
                  </button>

                  {/* 块详情 */}
                  {expandedBlock === block.block_index && (
                    <div className="border-t border-gray-800 p-4 space-y-4">
                      {/* 文本预览 */}
                      <div className="bg-gray-950 rounded-lg p-3">
                        <p className="text-xs text-gray-500 mb-2">文本预览</p>
                        <p className="text-sm text-gray-300 leading-relaxed font-serif whitespace-pre-wrap">
                          {block.text_preview}
                        </p>
                      </div>

                      {/* 各维度得分 */}
                      <div className="space-y-2">
                        {block.dims.map(dim => {
                          const dimKey = `${block.block_index}-${dim.id}`
                          return (
                            <div key={dim.id} className="border border-gray-800 rounded-lg overflow-hidden">
                              {/* 维度头 */}
                              <button
                                onClick={() => toggleDim(dimKey)}
                                className="w-full flex items-center justify-between px-4 py-2.5 hover:bg-gray-800/40 transition-colors text-left"
                              >
                                <div className="flex items-center gap-3 flex-1">
                                  <span className="text-sm text-gray-300 font-medium w-24">{dim.name}</span>
                                  <div className="flex-1 max-w-xs">
                                    <ScoreBar score={dim.score} />
                                  </div>
                                </div>
                                <div className="flex items-center gap-3 ml-4">
                                  <span className="text-xs text-gray-500">
                                    {dim.passed}/{dim.total_rules} 通过
                                  </span>
                                  <span className="text-gray-600 text-xs">
                                    {expandedDim[dimKey] ? '▲' : '▼'}
                                  </span>
                                </div>
                              </button>

                              {/* 规则详情 */}
                              {expandedDim[dimKey] && (
                                <div className="border-t border-gray-800 divide-y divide-gray-800/50">
                                  {dim.rules.map(rule => (
                                    <div key={rule.rule_id} className="px-4 py-2.5 flex gap-3">
                                      <span
                                        className={`text-xs font-bold mt-0.5 w-8 shrink-0 ${
                                          rule.answer === 'Yes' ? 'text-green-400' : 'text-red-400'
                                        }`}
                                      >
                                        {rule.answer === 'Yes' ? '✓' : '✗'}
                                      </span>
                                      <div className="flex-1 min-w-0">
                                        <div className="flex items-center gap-2">
                                          <span className="text-xs text-gray-500 font-mono">{rule.rule_id}</span>
                                          <span className="text-sm text-gray-300">{rule.name}</span>
                                        </div>
                                        {rule.reason && (
                                          <p className="text-xs text-gray-500 mt-0.5 leading-relaxed">
                                            {rule.reason}
                                          </p>
                                        )}
                                      </div>
                                    </div>
                                  ))}
                                </div>
                              )}
                            </div>
                          )
                        })}
                      </div>
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}

        {/* ── 历史记录区 ── */}
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-bold text-white">📚 评测历史</h2>
            <button
              onClick={() => loadHistory(historyPage)}
              disabled={historyLoading}
              className="text-xs text-indigo-400 hover:text-indigo-300 disabled:text-gray-600"
            >
              {historyLoading ? '加载中...' : '刷新'}
            </button>
          </div>

          {history.length === 0 && !historyLoading ? (
            <div className="text-center py-8 text-gray-500 text-sm">
              暂无评测历史记录
            </div>
          ) : (
            <>
              {/* 历史记录列表 */}
              <div className="space-y-3">
                {history.map((item) => (
                  <div
                    key={item.id}
                    className="bg-gray-900 rounded-xl border border-gray-800 overflow-hidden"
                  >
                    {/* 历史记录头部 */}
                    <button
                      onClick={() => loadHistoryDetail(item.id)}
                      className="w-full flex items-center justify-between p-4 hover:bg-gray-800/50 transition-colors text-left"
                    >
                      <div className="flex items-center gap-4 flex-1">
                        <span className={`text-2xl font-black ${rankColor[item.rank] || 'text-gray-400'}`}>
                          {item.rank}
                        </span>
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2">
                            <span className="text-sm text-gray-300 truncate">
                              {item.source_name || '未命名评测'}
                            </span>
                            <span className="text-xs bg-gray-800 text-gray-500 px-2 py-0.5 rounded">
                              {item.genre}
                            </span>
                          </div>
                          <div className="text-xs text-gray-500 mt-1">
                            {new Date(item.created_at).toLocaleString()} ·
                            采样 {item.sampled_blocks}/{item.num_blocks} 块 ·
                            API调用 {item.api_calls} 次
                          </div>
                        </div>
                      </div>
                      <div className="flex items-center gap-4">
                        <span className={`text-xl font-bold ${scoreColor(item.total_score / 10)}`}>
                          {item.total_score}
                        </span>
                        <span className="text-gray-600 text-sm">
                          {expandedHistory === item.id ? '▲' : '▼'}
                        </span>
                      </div>
                    </button>

                    {/* 历史记录详情 */}
                    {expandedHistory === item.id && (
                      <div className="border-t border-gray-800 p-4">
                        {historyDetailLoading ? (
                          <div className="text-center py-4 text-gray-500 text-sm">
                            加载详情中...
                          </div>
                        ) : historyDetail ? (
                          <div className="space-y-4">
                            {/* 维度得分 */}
                            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                              {historyDetail.dims?.map((dim: DimSummary) => (
                                <div key={dim.id} className="space-y-1">
                                  <div className="flex justify-between text-xs text-gray-400">
                                    <span>{dim.name}</span>
                                    <span className="text-gray-500">{dim.weight_pct}%</span>
                                  </div>
                                  <ScoreBar score={dim.avg_score} />
                                </div>
                              ))}
                            </div>

                            {/* 块结果摘要 */}
                            {historyDetail.blocks && historyDetail.blocks.length > 0 && (
                              <div className="mt-4">
                                <p className="text-xs text-gray-500 mb-2">
                                  共 {historyDetail.blocks.length} 个采样块
                                </p>
                                <div className="space-y-2">
                                  {historyDetail.blocks.map((block: BlockResult) => (
                                    <div
                                      key={block.block_index}
                                      className="bg-gray-950 rounded-lg p-3 text-sm"
                                    >
                                      <div className="flex items-center justify-between mb-2">
                                        <span className="text-xs text-gray-500">
                                          块 {block.block_index}/{block.total_blocks} · 原文第 {block.original_index + 1} 块
                                        </span>
                                        <span className={`font-bold ${scoreColor(block.score / 10)}`}>
                                          {block.score}
                                        </span>
                                      </div>
                                      <p className="text-xs text-gray-400 line-clamp-2">
                                        {block.text_preview}
                                      </p>
                                    </div>
                                  ))}
                                </div>
                              </div>
                            )}
                          </div>
                        ) : (
                          <div className="text-center py-4 text-gray-500 text-sm">
                            无法加载详情
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                ))}
              </div>

              {/* 分页控件 */}
              {historyTotalPages > 1 && (
                <div className="flex items-center justify-center gap-2 pt-4">
                  <button
                    onClick={() => loadHistory(historyPage - 1)}
                    disabled={historyPage <= 1 || historyLoading}
                    className="px-3 py-1.5 rounded-lg text-sm bg-gray-800 text-gray-300 hover:bg-gray-700 disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    上一页
                  </button>
                  <span className="text-sm text-gray-400">
                    {historyPage} / {historyTotalPages}
                  </span>
                  <button
                    onClick={() => loadHistory(historyPage + 1)}
                    disabled={historyPage >= historyTotalPages || historyLoading}
                    className="px-3 py-1.5 rounded-lg text-sm bg-gray-800 text-gray-300 hover:bg-gray-700 disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    下一页
                  </button>
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  )
}
