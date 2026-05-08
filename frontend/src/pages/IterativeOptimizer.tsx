import { useState, useEffect, useRef } from 'react'
import { evaluationOptimizerApi } from '../services/api'

// ─── 类型定义 ───────────────────────────────────────────────

interface IterationRecord {
  iteration: number
  timestamp: string
  metrics: {
    avg_discrimination: number
    min_discrimination: number
    max_discrimination: number
    consistency_score: number
    rules_count: number
  }
  rule_changes: RuleChange[]
  changes_count: number
  converged: boolean
  termination_reason: string
}

interface RuleChange {
  rule_id: string
  name: string
  action: 'modify' | 'delete' | 'merge' | 'add'
  old_value: any
  new_value: any
  reason: string
  dimension: string
}

interface OptimizationConfig {
  max_iterations: number
  discrimination_threshold: number
  convergence_window: number
  convergence_threshold: number
}

// ─── 折线图组件 ───────────────────────────────────────────────

function MetricsChart({ history }: { history: IterationRecord[] }) {
  if (history.length < 2) return null

  const width = 600
  const height = 200
  const padding = 40

  const maxDisc = Math.max(...history.map(h => h.metrics.max_discrimination), 1)
  const minDisc = Math.min(...history.map(h => h.metrics.min_discrimination), 0)

  const xScale = (i: number) => padding + (i / (history.length - 1)) * (width - 2 * padding)
  const yScale = (v: number) => height - padding - ((v - minDisc) / (maxDisc - minDisc)) * (height - 2 * padding)

  const avgPath = history.map((h, i) => `${i === 0 ? 'M' : 'L'} ${xScale(i)} ${yScale(h.metrics.avg_discrimination)}`).join(' ')
  const minPath = history.map((h, i) => `${i === 0 ? 'M' : 'L'} ${xScale(i)} ${yScale(h.metrics.min_discrimination)}`).join(' ')
  const maxPath = history.map((h, i) => `${i === 0 ? 'M' : 'L'} ${xScale(i)} ${yScale(h.metrics.max_discrimination)}`).join(' ')

  return (
    <div className="bg-gray-900 rounded-lg p-4">
      <h3 className="text-sm font-medium text-gray-300 mb-3">区分度变化趋势</h3>
      <svg viewBox={`0 0 ${width} ${height}`} className="w-full" style={{ maxWidth: width }}>
        {/* 网格线 */}
        {[0, 0.25, 0.5, 0.75, 1].map(tick => {
          const y = height - padding - tick * (height - 2 * padding)
          return (
            <g key={tick}>
              <line x1={padding} y1={y} x2={width - padding} y2={y} stroke="#374151" strokeDasharray="4" />
              <text x={padding - 5} y={y + 4} textAnchor="end" fill="#6B7280" fontSize="10">
                {(minDisc + tick * (maxDisc - minDisc)).toFixed(2)}
              </text>
            </g>
          )
        })}

        {/* 平均线 */}
        <path d={avgPath} fill="none" stroke="#3B82F6" strokeWidth="2" />
        {/* 最小值线 */}
        <path d={minPath} fill="none" stroke="#EF4444" strokeWidth="1.5" strokeDasharray="4" />
        {/* 最大值线 */}
        <path d={maxPath} fill="none" stroke="#10B981" strokeWidth="1.5" strokeDasharray="4" />

        {/* 数据点 */}
        {history.map((h, i) => (
          <g key={i}>
            <circle cx={xScale(i)} cy={yScale(h.metrics.avg_discrimination)} r="4" fill="#3B82F6" />
            <text x={xScale(i)} y={yScale(h.metrics.avg_discrimination) - 10} textAnchor="middle" fill="#3B82F6" fontSize="10">
              {h.metrics.avg_discrimination.toFixed(2)}
            </text>
          </g>
        ))}

        {/* X轴标签 */}
        {history.map((h, i) => (
          <text key={i} x={xScale(i)} y={height - 10} textAnchor="middle" fill="#6B7280" fontSize="10">
            迭代{h.iteration}
          </text>
        ))}

        {/* 图例 */}
        <g transform={`translate(${width - padding - 120}, 20)`}>
          <line x1="0" y1="0" x2="20" y2="0" stroke="#3B82F6" strokeWidth="2" />
          <text x="25" y="4" fill="#9CA3AF" fontSize="10">平均</text>
          <line x1="0" y1="15" x2="20" y2="15" stroke="#EF4444" strokeWidth="1.5" strokeDasharray="4" />
          <text x="25" y="19" fill="#9CA3AF" fontSize="10">最小</text>
          <line x1="0" y1="30" x2="20" y2="30" stroke="#10B981" strokeWidth="1.5" strokeDasharray="4" />
          <text x="25" y="34" fill="#9CA3AF" fontSize="10">最大</text>
        </g>
      </svg>
    </div>
  )
}

// ─── 规则变更确认组件 ───────────────────────────────────────────────

function RuleChangesConfirm({
  changes,
  onConfirm,
  onReject,
  readOnly = false,
}: {
  changes: RuleChange[]
  onConfirm?: (ruleId: string) => void
  onReject?: (ruleId: string) => void
  readOnly?: boolean
}) {
  const [confirmed, setConfirmed] = useState<Set<string>>(new Set())
  const [rejected, setRejected] = useState<Set<string>>(new Set())

  const handleConfirm = (ruleId: string) => {
    setConfirmed(prev => new Set([...prev, ruleId]))
    setRejected(prev => {
      const next = new Set(prev)
      next.delete(ruleId)
      return next
    })
    onConfirm?.(ruleId)
  }

  const handleReject = (ruleId: string) => {
    setRejected(prev => new Set([...prev, ruleId]))
    setConfirmed(prev => {
      const next = new Set(prev)
      next.delete(ruleId)
      return next
    })
    onReject?.(ruleId)
  }

  const actionConfig = {
    modify: { label: '修改权重', color: 'bg-yellow-900/50 text-yellow-400', icon: '📝' },
    delete: { label: '删除', color: 'bg-red-900/50 text-red-400', icon: '❌' },
    merge: { label: '合并', color: 'bg-blue-900/50 text-blue-400', icon: '🔗' },
    add: { label: '新增', color: 'bg-green-900/50 text-green-400', icon: '✨' },
  }

  if (changes.length === 0) {
    return <div className="text-gray-500 text-sm">本次迭代无规则变更</div>
  }

  return (
    <div className="space-y-2">
      {changes.map(change => {
        const config = actionConfig[change.action] || actionConfig.modify
        const isConfirmed = confirmed.has(change.rule_id)
        const isRejected = rejected.has(change.rule_id)

        return (
          <div
            key={change.rule_id}
            className={`p-3 rounded-lg border transition-colors ${
              isConfirmed
                ? 'border-green-700 bg-green-900/20'
                : isRejected
                ? 'border-red-700 bg-red-900/20 opacity-50'
                : 'border-gray-700 bg-gray-800/50'
            }`}
          >
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <span className="text-lg">{config.icon}</span>
                <span className={`text-xs px-2 py-0.5 rounded ${config.color}`}>
                  {config.label}
                </span>
                <span className="font-medium text-gray-200">{change.name}</span>
                <span className="text-xs text-gray-500">({change.rule_id})</span>
              </div>
              {!readOnly && (
                <div className="flex gap-2">
                  <button
                    onClick={() => handleConfirm(change.rule_id)}
                    className={`px-3 py-1 rounded text-xs transition-colors ${
                      isConfirmed
                        ? 'bg-green-700 text-white'
                        : 'bg-gray-700 text-gray-300 hover:bg-green-800'
                    }`}
                  >
                    ✓ 确认
                  </button>
                  <button
                    onClick={() => handleReject(change.rule_id)}
                    className={`px-3 py-1 rounded text-xs transition-colors ${
                      isRejected
                        ? 'bg-red-700 text-white'
                        : 'bg-gray-700 text-gray-300 hover:bg-red-800'
                    }`}
                  >
                    ✗ 拒绝
                  </button>
                </div>
              )}
            </div>
            <div className="mt-2 text-sm text-gray-400">
              {change.action === 'modify' && (
                <span>
                  权重: <span className="text-red-400">{change.old_value}</span> →{' '}
                  <span className="text-green-400">{change.new_value}</span>
                </span>
              )}
              {change.action === 'delete' && (
                <span className="text-red-400">删除规则</span>
              )}
              {change.action === 'merge' && (
                <span>
                  合并到: <span className="text-blue-400">{change.new_value}</span>
                </span>
              )}
            </div>
            <div className="mt-1 text-xs text-gray-500">{change.reason}</div>
          </div>
        )
      })}
    </div>
  )
}

// ─── 主组件 ───────────────────────────────────────────────

export default function IterativeOptimizer() {
  // 配置状态
  const [config, setConfig] = useState<OptimizationConfig>({
    max_iterations: 5,
    discrimination_threshold: 0.6,
    convergence_window: 3,
    convergence_threshold: 0.01,
  })

  // 小说选择
  const [referenceNovels, setReferenceNovels] = useState<string[]>([])
  const [selectedGood, setSelectedGood] = useState<string[]>([])
  const [selectedBad, setSelectedBad] = useState<string[]>([])
  const [blocksPerNovel, setBlocksPerNovel] = useState(5)
  const [maxBytesPerBlock, setMaxBytesPerBlock] = useState(8000)
  const [genre, setGenre] = useState('玄幻')

  // 迭代状态
  const [isRunning, setIsRunning] = useState(false)
  const [currentIteration, setCurrentIteration] = useState(0)
  const [progress, setProgress] = useState('')
  const [history, setHistory] = useState<IterationRecord[]>([])
  const [logs, setLogs] = useState<string[]>([])

  // 结果确认
  const [showConfirm, setShowConfirm] = useState(false)
  const [sessionId, setSessionId] = useState('')
  const [allChanges, setAllChanges] = useState<RuleChange[]>([])
  const [confirmedChanges, setConfirmedChanges] = useState<Set<string>>(new Set())
  const [rejectedChanges, setRejectedChanges] = useState<Set<string>>(new Set())

  // 加载参考小说
  useEffect(() => {
    loadReferenceNovels()
  }, [])

  const loadReferenceNovels = async () => {
    try {
      const res = await evaluationOptimizerApi.listReferenceNovels()
      setReferenceNovels(res.files || [])
    } catch (e) {
      console.error('加载参考小说失败:', e)
    }
  }

  const addLog = (msg: string) => {
    setLogs(prev => [...prev, `[${new Date().toLocaleTimeString()}] ${msg}`])
  }

  // 开始迭代优化
  const handleStartOptimization = async () => {
    if (selectedGood.length === 0 || selectedBad.length === 0) {
      alert('请至少选择一本好小说和一本坏小说')
      return
    }

    setIsRunning(true)
    setCurrentIteration(0)
    setProgress('')
    setHistory([])
    setLogs([])
    setShowConfirm(false)
    setAllChanges([])
    setConfirmedChanges(new Set())
    setRejectedChanges(new Set())

    try {
      addLog('启动迭代优化...')
      addLog(`配置: 最大迭代=${config.max_iterations}, 区分度阈值=${config.discrimination_threshold}`)

      await evaluationOptimizerApi.optimizeRulesIterative(
        {
          good_novel_files: selectedGood,
          bad_novel_files: selectedBad,
          blocks_per_novel: blocksPerNovel,
          max_bytes_per_block: maxBytesPerBlock,
          genre: genre,
          max_iterations: config.max_iterations,
          discrimination_threshold: config.discrimination_threshold,
          convergence_window: config.convergence_window,
          convergence_threshold: config.convergence_threshold,
        },
        (data) => {
          console.log('收到数据:', data)

          if (data.type === 'iteration_start') {
            setCurrentIteration(data.iteration)
            setProgress(`第 ${data.iteration}/${data.max_iterations} 次迭代`)
            addLog(data.message)
          } else if (data.type === 'progress') {
            setProgress(data.message)
            addLog(data.message)
          } else if (data.type === 'iteration_complete') {
            const record: IterationRecord = {
              iteration: data.iteration,
              timestamp: new Date().toISOString(),
              metrics: data.metrics,
              rule_changes: data.rule_changes || [],
              changes_count: data.changes_count,
              converged: data.converged,
              termination_reason: data.termination_reason,
            }
            setHistory(prev => [...prev, record])
            addLog(
              `迭代 ${data.iteration} 完成: 平均区分度=${data.metrics.avg_discrimination.toFixed(3)}, ` +
              `变更=${data.changes_count}条, 终止=${data.converged}`
            )

            // 收集所有变更
            if (data.rule_changes) {
              setAllChanges(prev => [...prev, ...data.rule_changes])
            }
          } else if (data.type === 'complete') {
            setIsRunning(false)
            setProgress('优化完成')
            addLog('迭代优化完成！')

            if (data.final_report) {
              setSessionId(data.session_id || '')
              setShowConfirm(true)
            }
          } else if (data.type === 'error') {
            addLog(`错误: ${data.error}`)
            setIsRunning(false)
          }
        }
      )
    } catch (e: any) {
      setIsRunning(false)
      setProgress('优化失败')
      addLog(`优化失败: ${e.message}`)
    }
  }

  // 确认变更
  const handleConfirmChanges = async () => {
    if (!sessionId) return

    try {
      await evaluationOptimizerApi.confirmRuleChanges({
        session_id: sessionId,
        confirmed_changes: Array.from(confirmedChanges),
        rejected_changes: Array.from(rejectedChanges),
      })
      alert(`已应用 ${confirmedChanges.size} 条规则变更`)
      setShowConfirm(false)
    } catch (e: any) {
      alert('应用失败: ' + e.message)
    }
  }

  const toggleSelection = (filename: string, type: 'good' | 'bad') => {
    if (type === 'good') {
      setSelectedGood(prev =>
        prev.includes(filename)
          ? prev.filter(f => f !== filename)
          : [...prev, filename]
      )
    } else {
      setSelectedBad(prev =>
        prev.includes(filename)
          ? prev.filter(f => f !== filename)
          : [...prev, filename]
      )
    }
  }

  return (
    <div className="min-h-screen bg-gray-950 text-gray-200 p-6">
      <div className="max-w-7xl mx-auto space-y-6">
        {/* 标题 */}
        <div className="border-b border-gray-800 pb-4">
          <h1 className="text-2xl font-bold text-white">🔄 迭代式规则优化</h1>
          <p className="text-gray-400 text-sm mt-1">
            自动迭代优化评测规则，直到满足终止条件
          </p>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* 左侧面板：配置和选择 */}
          <div className="space-y-6">
            {/* 终止条件配置 */}
            <div className="bg-gray-900 rounded-lg p-4 space-y-4">
              <h2 className="text-lg font-medium text-white">⚙️ 终止条件配置</h2>

              <div>
                <label className="block text-sm text-gray-400 mb-1">
                  最大迭代次数
                </label>
                <input
                  type="number"
                  min={1}
                  max={20}
                  value={config.max_iterations}
                  onChange={e => setConfig(prev => ({ ...prev, max_iterations: parseInt(e.target.value) }))}
                  className="w-full bg-gray-800 border border-gray-700 rounded px-3 py-2 text-sm"
                />
              </div>

              <div>
                <label className="block text-sm text-gray-400 mb-1">
                  区分度阈值 (0-1)
                </label>
                <input
                  type="number"
                  min={0}
                  max={1}
                  step={0.1}
                  value={config.discrimination_threshold}
                  onChange={e => setConfig(prev => ({ ...prev, discrimination_threshold: parseFloat(e.target.value) }))}
                  className="w-full bg-gray-800 border border-gray-700 rounded px-3 py-2 text-sm"
                />
                <p className="text-xs text-gray-500 mt-1">
                  平均区分度达到此值时停止
                </p>
              </div>

              <div>
                <label className="block text-sm text-gray-400 mb-1">
                  收敛窗口
                </label>
                <input
                  type="number"
                  min={2}
                  max={5}
                  value={config.convergence_window}
                  onChange={e => setConfig(prev => ({ ...prev, convergence_window: parseInt(e.target.value) }))}
                  className="w-full bg-gray-800 border border-gray-700 rounded px-3 py-2 text-sm"
                />
                <p className="text-xs text-gray-500 mt-1">
                  连续N次改善小于阈值时停止
                </p>
              </div>

              <div>
                <label className="block text-sm text-gray-400 mb-1">
                  收敛阈值
                </label>
                <input
                  type="number"
                  min={0.001}
                  max={0.1}
                  step={0.001}
                  value={config.convergence_threshold}
                  onChange={e => setConfig(prev => ({ ...prev, convergence_threshold: parseFloat(e.target.value) }))}
                  className="w-full bg-gray-800 border border-gray-700 rounded px-3 py-2 text-sm"
                />
              </div>
            </div>

            {/* 小说选择 */}
            <div className="bg-gray-900 rounded-lg p-4 space-y-4">
              <h2 className="text-lg font-medium text-white">📚 选择参考小说</h2>

              <div>
                <label className="block text-sm text-green-400 mb-2">好小说</label>
                <div className="space-y-1 max-h-40 overflow-y-auto">
                  {referenceNovels.map(novel => (
                    <label key={novel} className="flex items-center gap-2 cursor-pointer hover:bg-gray-800 p-1 rounded">
                      <input
                        type="checkbox"
                        checked={selectedGood.includes(novel)}
                        onChange={() => toggleSelection(novel, 'good')}
                        className="rounded border-gray-600"
                      />
                      <span className="text-sm text-gray-300 truncate">{novel}</span>
                    </label>
                  ))}
                </div>
              </div>

              <div>
                <label className="block text-sm text-red-400 mb-2">坏小说</label>
                <div className="space-y-1 max-h-40 overflow-y-auto">
                  {referenceNovels.map(novel => (
                    <label key={novel} className="flex items-center gap-2 cursor-pointer hover:bg-gray-800 p-1 rounded">
                      <input
                        type="checkbox"
                        checked={selectedBad.includes(novel)}
                        onChange={() => toggleSelection(novel, 'bad')}
                        className="rounded border-gray-600"
                      />
                      <span className="text-sm text-gray-300 truncate">{novel}</span>
                    </label>
                  ))}
                </div>
              </div>

              <div className="grid grid-cols-2 gap-2">
                <div>
                  <label className="block text-xs text-gray-400 mb-1">采样块数</label>
                  <input
                    type="number"
                    min={1}
                    max={10}
                    value={blocksPerNovel}
                    onChange={e => setBlocksPerNovel(parseInt(e.target.value))}
                    className="w-full bg-gray-800 border border-gray-700 rounded px-2 py-1 text-sm"
                  />
                </div>
                <div>
                  <label className="block text-xs text-gray-400 mb-1">每块字节数</label>
                  <input
                    type="number"
                    min={1000}
                    max={20000}
                    step={1000}
                    value={maxBytesPerBlock}
                    onChange={e => setMaxBytesPerBlock(parseInt(e.target.value))}
                    className="w-full bg-gray-800 border border-gray-700 rounded px-2 py-1 text-sm"
                  />
                </div>
              </div>

              <button
                onClick={handleStartOptimization}
                disabled={isRunning}
                className="w-full py-2 bg-blue-600 hover:bg-blue-500 disabled:bg-gray-700 text-white rounded-lg font-medium transition-colors"
              >
                {isRunning ? '🔄 优化中...' : '🚀 开始迭代优化'}
              </button>
            </div>
          </div>

          {/* 中间面板：进度和日志 */}
          <div className="space-y-6">
            {/* 当前进度 */}
            {isRunning && (
              <div className="bg-gray-900 rounded-lg p-4">
                <div className="flex items-center justify-between mb-2">
                  <h3 className="text-sm font-medium text-white">当前进度</h3>
                  <span className="text-xs text-blue-400">
                    迭代 {currentIteration}/{config.max_iterations}
                  </span>
                </div>
                <div className="w-full bg-gray-800 rounded-full h-2 mb-2">
                  <div
                    className="bg-blue-600 h-2 rounded-full transition-all"
                    style={{ width: `${(currentIteration / config.max_iterations) * 100}%` }}
                  />
                </div>
                <p className="text-sm text-gray-400">{progress}</p>
              </div>
            )}

            {/* 迭代历史表格 */}
            {history.length > 0 && (
              <div className="bg-gray-900 rounded-lg p-4">
                <h3 className="text-sm font-medium text-white mb-3">迭代历史</h3>
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="text-gray-400 border-b border-gray-800">
                        <th className="text-left py-2 px-2">迭代</th>
                        <th className="text-right py-2 px-2">平均区分度</th>
                        <th className="text-right py-2 px-2">最小</th>
                        <th className="text-right py-2 px-2">最大</th>
                        <th className="text-right py-2 px-2">变更数</th>
                        <th className="text-center py-2 px-2">状态</th>
                      </tr>
                    </thead>
                    <tbody>
                      {history.map(record => (
                        <tr key={record.iteration} className="border-b border-gray-800/50 hover:bg-gray-800/50">
                          <td className="py-2 px-2">{record.iteration}</td>
                          <td className="text-right py-2 px-2 font-mono">
                            <span className={record.metrics.avg_discrimination >= config.discrimination_threshold ? 'text-green-400' : 'text-blue-400'}>
                              {record.metrics.avg_discrimination.toFixed(3)}
                            </span>
                          </td>
                          <td className="text-right py-2 px-2 font-mono text-gray-400">
                            {record.metrics.min_discrimination.toFixed(3)}
                          </td>
                          <td className="text-right py-2 px-2 font-mono text-gray-400">
                            {record.metrics.max_discrimination.toFixed(3)}
                          </td>
                          <td className="text-right py-2 px-2">{record.changes_count}</td>
                          <td className="text-center py-2 px-2">
                            {record.converged ? (
                              <span className="text-xs px-2 py-0.5 rounded bg-green-900/50 text-green-400">
                                ✓ 终止
                              </span>
                            ) : (
                              <span className="text-xs px-2 py-0.5 rounded bg-gray-800 text-gray-400">
                                继续
                              </span>
                            )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}

            {/* 折线图 */}
            {history.length > 1 && <MetricsChart history={history} />}

            {/* 日志 */}
            <div className="bg-gray-900 rounded-lg p-4">
              <h3 className="text-sm font-medium text-white mb-2">运行日志</h3>
              <div className="bg-gray-950 rounded p-2 h-48 overflow-y-auto font-mono text-xs space-y-1">
                {logs.map((log, i) => (
                  <div key={i} className="text-gray-400">{log}</div>
                ))}
                {logs.length === 0 && <div className="text-gray-600 italic">等待开始...</div>}
              </div>
            </div>
          </div>

          {/* 右侧面板：规则变更确认 */}
          <div className="space-y-6">
            {showConfirm && allChanges.length > 0 && (
              <div className="bg-gray-900 rounded-lg p-4 space-y-4">
                <div className="flex items-center justify-between">
                  <h2 className="text-lg font-medium text-white">✅ 规则变更确认</h2>
                  <div className="text-xs text-gray-400">
                    已确认 {confirmedChanges.size} / 共 {allChanges.length}
                  </div>
                </div>

                <p className="text-sm text-gray-400">
                  请逐条确认是否应用以下规则变更。未确认的变更将被忽略。
                </p>

                <RuleChangesConfirm
                  changes={allChanges}
                  onConfirm={(ruleId) => {
                    setConfirmedChanges(prev => new Set([...prev, ruleId]))
                    setRejectedChanges(prev => {
                      const next = new Set(prev)
                      next.delete(ruleId)
                      return next
                    })
                  }}
                  onReject={(ruleId) => {
                    setRejectedChanges(prev => new Set([...prev, ruleId]))
                    setConfirmedChanges(prev => {
                      const next = new Set(prev)
                      next.delete(ruleId)
                      return next
                    })
                  }}
                />

                <div className="flex gap-2 pt-4 border-t border-gray-800">
                  <button
                    onClick={handleConfirmChanges}
                    disabled={confirmedChanges.size === 0}
                    className="flex-1 py-2 bg-green-600 hover:bg-green-500 disabled:bg-gray-700 text-white rounded-lg text-sm font-medium transition-colors"
                  >
                    应用确认的变更 ({confirmedChanges.size})
                  </button>
                  <button
                    onClick={() => setShowConfirm(false)}
                    className="px-4 py-2 bg-gray-700 hover:bg-gray-600 text-gray-300 rounded-lg text-sm transition-colors"
                  >
                    取消
                  </button>
                </div>
              </div>
            )}

            {/* 每次迭代的变更详情 */}
            {history.map(record => (
              <div key={record.iteration} className="bg-gray-900 rounded-lg p-4">
                <h3 className="text-sm font-medium text-white mb-2">
                  迭代 {record.iteration} 的变更
                </h3>
                <RuleChangesConfirm changes={record.rule_changes} readOnly />
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}
