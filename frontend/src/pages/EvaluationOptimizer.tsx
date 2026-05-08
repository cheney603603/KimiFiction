import { useState, useEffect } from 'react'
import { evaluationOptimizerApi } from '../services/api'

// ─── 类型定义 ───────────────────────────────────────────────

interface RuleAdjustment {
  rule_id: string
  dimension: string
  name: string
  current_weight: number
  suggested_weight: number
  reason: string
  good_pass_rate: number
  bad_pass_rate: number
  discrimination: number
  action: 'keep' | 'modify' | 'delete' | 'merge'
  merge_target?: string
  consistency_score?: number
}

interface DimensionAnalysis {
  dimension_id: string
  dimension_name: string
  current_weight: number
  suggested_weight: number
  avg_discrimination: number
  rules_count: number
}

interface ConsistencyIssue {
  novel_type: string
  block_scores: number[]
  average: number
  std_dev: number
  issue: string
  suggestion: string
}

interface OptimizationReport {
  created_at: string
  total_samples: number
  good_novels: string[]
  bad_novels: string[]
  rule_adjustments: RuleAdjustment[]
  dimension_analysis: DimensionAnalysis[]
  consistency_issues: ConsistencyIssue[]
  recommendations: string[]
}

interface OptimizationHistoryItem {
  id: string
  created_at: string
  description: string
  good_novels: string[]
  bad_novels: string[]
  total_samples: number
  rule_changes: Array<{
    rule_id: string
    name: string
    old_weight: number
    new_weight: number
    reason: string
  }>
  applied: boolean
  applied_at?: string
}

// ─── 组件 ───────────────────────────────────────────────

export default function EvaluationOptimizer() {
  // 状态
  const [referenceNovels, setReferenceNovels] = useState<string[]>([])
  const [selectedGood, setSelectedGood] = useState<string[]>([])
  const [selectedBad, setSelectedBad] = useState<string[]>([])
  const [blocksPerNovel, setBlocksPerNovel] = useState(5)
  const [maxBytesPerBlock, setMaxBytesPerBlock] = useState(8000)
  const [genre, setGenre] = useState('玄幻')
  
  const [loading, setLoading] = useState(false)
  const [progress, setProgress] = useState<string>('')
  const [report, setReport] = useState<OptimizationReport | null>(null)
  const [error, setError] = useState<string>('')
  
  // 详细日志
  const [logs, setLogs] = useState<string[]>([])
  const [showLogs, setShowLogs] = useState(false)
  const [apiStats, setApiStats] = useState<{current: number, total: number}>({current: 0, total: 0})
  
  // 历史记录
  const [history, setHistory] = useState<OptimizationHistoryItem[]>([])
  const [showHistory, setShowHistory] = useState(false)
  const [saveDescription, setSaveDescription] = useState('')
  const [showSaveDialog, setShowSaveDialog] = useState(false)

  // 加载参考小说列表和历史记录
  useEffect(() => {
    loadReferenceNovels()
    loadHistory()
  }, [])

  const loadReferenceNovels = async () => {
    try {
      const res = await evaluationOptimizerApi.listReferenceNovels()
      setReferenceNovels(res.files || [])
    } catch (e: any) {
      console.error('加载参考小说失败:', e)
    }
  }

  const loadHistory = async () => {
    try {
      const res = await evaluationOptimizerApi.listHistory()
      setHistory(res.items || [])
    } catch (e: any) {
      console.error('加载历史记录失败:', e)
    }
  }

  const handleSaveOptimization = async () => {
    if (!report || !saveDescription.trim()) return
    
    const ruleChanges = report.rule_adjustments
      .filter(r => Math.abs(r.suggested_weight - r.current_weight) > 0.001)
      .map(r => ({
        rule_id: r.rule_id,
        name: r.name,
        old_weight: r.current_weight,
        new_weight: r.suggested_weight,
        reason: r.reason
      }))
    
    try {
      await evaluationOptimizerApi.saveHistory({
        description: saveDescription,
        good_novels: report.good_novels,
        bad_novels: report.bad_novels,
        blocks_per_novel: blocksPerNovel,
        total_samples: report.total_samples,
        rule_changes: ruleChanges,
        dimension_changes: report.dimension_analysis.map(d => ({
          dimension_id: d.dimension_id,
          old_weight: d.current_weight,
          new_weight: d.suggested_weight
        })),
        applied: false
      })
      setShowSaveDialog(false)
      setSaveDescription('')
      loadHistory()
      alert('优化记录已保存')
    } catch (e: any) {
      alert('保存失败: ' + e.message)
    }
  }

  const handleApplyOptimization = async (historyId: string) => {
    if (!confirm('确定要应用此优化吗？这将修改规则文件。')) return
    
    try {
      await evaluationOptimizerApi.applyHistory(historyId)
      loadHistory()
      alert('优化已应用')
    } catch (e: any) {
      alert('应用失败: ' + e.message)
    }
  }

  const handleAnalyze = async () => {
    if (selectedGood.length === 0 || selectedBad.length === 0) {
      setError('请至少选择一本好小说和一本坏小说')
      return
    }

    setLoading(true)
    setError('')
    setProgress('开始分析...')
    setReport(null)
    setLogs([])
    setApiStats({current: 0, total: 0})

    const addLog = (msg: string) => {
      setLogs(prev => [...prev, `[${new Date().toLocaleTimeString()}] ${msg}`])
    }

    try {
      addLog('开始分析...')
      addLog(`好小说: ${selectedGood.join(', ')}`)
      addLog(`坏小说: ${selectedBad.join(', ')}`)
      addLog(`每本采样块数: ${blocksPerNovel}`)
      
      await evaluationOptimizerApi.analyzeRulesStream(
        {
          good_novel_files: selectedGood,
          bad_novel_files: selectedBad,
          blocks_per_novel: blocksPerNovel,
          max_bytes_per_block: maxBytesPerBlock,
          genre: genre,
        },
        (data) => {
          console.log('收到数据:', data)
          if (data.type === 'progress') {
            if (data.stage === 'loading') {
              setProgress('正在加载规则...')
              addLog('正在加载评测规则...')
            } else if (data.stage === 'evaluating') {
              setProgress(`正在评测: ${data.novel} (${data.progress})`)
              addLog(`评测中: ${data.novel} (${data.progress})`)
              if (data.api_calls) {
                setApiStats({current: data.api_calls, total: data.total_calls || 0})
              }
              if (data.message) {
                addLog(data.message)
              }
            } else if (data.stage === 'analyzing') {
              setProgress('正在分析结果...')
              addLog('正在分析评测结果...')
            }
          } else if (data.type === 'complete') {
            setReport(data.report)
            setProgress('分析完成')
            addLog(`分析完成! 共 ${data.report.total_samples} 个样本`)
            addLog(`发现 ${data.report.rule_adjustments?.length || 0} 条规则需要调整`)
          } else if (data.type === 'error') {
            addLog(`错误: ${data.error}`)
            setError(data.error)
          }
        }
      )
    } catch (e: any) {
      const errMsg = e?.message || '未知错误'
      setError('分析失败: ' + errMsg)
      addLog(`分析失败: ${errMsg}`)
      console.error('分析失败:', e)
    } finally {
      setLoading(false)
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

  // 颜色函数
  const discriminationColor = (d: number) => {
    if (d > 0.4) return 'text-green-400'
    if (d > 0.2) return 'text-yellow-400'
    if (d >= 0) return 'text-orange-400'
    return 'text-red-400'
  }

  const passRateColor = (r: number) => {
    if (r > 0.7) return 'text-green-400'
    if (r > 0.4) return 'text-yellow-400'
    return 'text-red-400'
  }

  // 操作类型显示
  const actionConfig = {
    keep: { label: '保持', color: 'bg-green-900 text-green-400', icon: '✅' },
    modify: { label: '修改', color: 'bg-yellow-900 text-yellow-400', icon: '📝' },
    delete: { label: '删除', color: 'bg-red-900 text-red-400', icon: '❌' },
    merge: { label: '合并', color: 'bg-blue-900 text-blue-400', icon: '🔗' },
  }

  const getActionDisplay = (action: string) => actionConfig[action as keyof typeof actionConfig] || actionConfig.keep

  return (
    <div className="min-h-screen bg-gray-950 text-gray-200 p-6">
      <div className="max-w-7xl mx-auto space-y-6">
        {/* 标题 */}
        <div className="border-b border-gray-800 pb-4 flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-white">📊 评测规则优化分析</h1>
            <p className="text-gray-400 text-sm mt-1">
              通过对比好小说和坏小说的评分差异，识别需要调整的规则权重
            </p>
          </div>
          <div className="flex gap-2">
            <a
              href="/evaluation"
              className="px-4 py-2 bg-gray-800 hover:bg-gray-700 text-gray-300 rounded-lg text-sm"
            >
              ← 返回评测
            </a>
            <button
              onClick={() => setShowHistory(!showHistory)}
              className="px-4 py-2 bg-gray-800 hover:bg-gray-700 text-gray-300 rounded-lg text-sm"
            >
              {showHistory ? '隐藏历史' : '查看历史'}
            </button>
          </div>
        </div>

        {/* 历史记录 */}
        {showHistory && (
          <div className="bg-gray-900 rounded-xl border border-gray-800 p-6">
            <h2 className="text-lg font-semibold text-white mb-4">📜 优化历史</h2>
            {history.length === 0 ? (
              <p className="text-gray-500 text-sm">暂无优化记录</p>
            ) : (
              <div className="space-y-3 max-h-96 overflow-y-auto">
                {history.map((item) => (
                  <div key={item.id} className="p-4 bg-gray-950 rounded-lg border border-gray-800">
                    <div className="flex items-start justify-between">
                      <div className="flex-1">
                        <div className="flex items-center gap-2">
                          <span className="text-sm font-medium text-white">{item.description}</span>
                          {item.applied && (
                            <span className="text-xs px-2 py-0.5 bg-green-900 text-green-400 rounded">已应用</span>
                          )}
                        </div>
                        <div className="mt-1 text-xs text-gray-500">
                          {new Date(item.created_at).toLocaleString()} · 
                          好小说: {item.good_novels.join(', ')} · 
                          坏小说: {item.bad_novels.join(', ')} · 
                          样本: {item.total_samples}
                        </div>
                        {item.rule_changes.length > 0 && (
                          <div className="mt-2 space-y-1">
                            <p className="text-xs text-gray-400">规则调整 ({item.rule_changes.length}条):</p>
                            {item.rule_changes.slice(0, 3).map((change, idx) => (
                              <div key={idx} className="text-xs text-gray-500 pl-2">
                                {change.name}: {change.old_weight.toFixed(3)} → {change.new_weight.toFixed(3)}
                              </div>
                            ))}
                            {item.rule_changes.length > 3 && (
                              <p className="text-xs text-gray-600 pl-2">...还有 {item.rule_changes.length - 3} 条</p>
                            )}
                          </div>
                        )}
                      </div>
                      {!item.applied && (
                        <button
                          onClick={() => handleApplyOptimization(item.id)}
                          className="px-3 py-1 bg-blue-600 hover:bg-blue-500 text-white text-xs rounded"
                        >
                          应用
                        </button>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* 配置区 */}
        <div className="bg-gray-900 rounded-xl border border-gray-800 p-6 space-y-6">
          <h2 className="text-lg font-semibold text-white">⚙️ 分析配置</h2>
          
          {/* 小说选择 */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {/* 好小说 */}
            <div className="space-y-3">
              <label className="text-sm font-medium text-green-400">✅ 好小说（参考标准）</label>
              <div className="bg-gray-950 rounded-lg border border-gray-800 p-3 max-h-48 overflow-y-auto space-y-1">
                {referenceNovels.map(filename => (
                  <label key={`good-${filename}`} className="flex items-center gap-2 cursor-pointer hover:bg-gray-900 p-1 rounded">
                    <input
                      type="checkbox"
                      checked={selectedGood.includes(filename)}
                      onChange={() => toggleSelection(filename, 'good')}
                      className="rounded border-gray-700 bg-gray-800 text-green-500"
                    />
                    <span className="text-sm text-gray-300 truncate">{filename}</span>
                  </label>
                ))}
              </div>
              <p className="text-xs text-gray-500">已选择 {selectedGood.length} 本</p>
            </div>

            {/* 坏小说 */}
            <div className="space-y-3">
              <label className="text-sm font-medium text-red-400">❌ 坏小说（问题样本）</label>
              <div className="bg-gray-950 rounded-lg border border-gray-800 p-3 max-h-48 overflow-y-auto space-y-1">
                {referenceNovels.map(filename => (
                  <label key={`bad-${filename}`} className="flex items-center gap-2 cursor-pointer hover:bg-gray-900 p-1 rounded">
                    <input
                      type="checkbox"
                      checked={selectedBad.includes(filename)}
                      onChange={() => toggleSelection(filename, 'bad')}
                      className="rounded border-gray-700 bg-gray-800 text-red-500"
                    />
                    <span className="text-sm text-gray-300 truncate">{filename}</span>
                  </label>
                ))}
              </div>
              <p className="text-xs text-gray-500">已选择 {selectedBad.length} 本</p>
            </div>
          </div>

          {/* 参数设置 */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="space-y-2">
              <label className="text-sm text-gray-400">每本小说采样块数</label>
              <input
                type="number"
                value={blocksPerNovel}
                onChange={e => setBlocksPerNovel(parseInt(e.target.value) || 5)}
                min={1}
                max={20}
                className="w-full bg-gray-950 border border-gray-800 rounded-lg px-3 py-2 text-white"
              />
            </div>
            <div className="space-y-2">
              <label className="text-sm text-gray-400">每块最大字节数</label>
              <input
                type="number"
                value={maxBytesPerBlock}
                onChange={e => setMaxBytesPerBlock(parseInt(e.target.value) || 8000)}
                min={1000}
                max={50000}
                step={1000}
                className="w-full bg-gray-950 border border-gray-800 rounded-lg px-3 py-2 text-white"
              />
            </div>
            <div className="space-y-2">
              <label className="text-sm text-gray-400">题材类型</label>
              <select
                value={genre}
                onChange={e => setGenre(e.target.value)}
                className="w-full bg-gray-950 border border-gray-800 rounded-lg px-3 py-2 text-white"
              >
                <option value="玄幻">玄幻</option>
                <option value="科幻">科幻</option>
                <option value="都市">都市</option>
                <option value="历史">历史</option>
                <option value="武侠">武侠</option>
                <option value="仙侠">仙侠</option>
              </select>
            </div>
          </div>

          {/* 分析按钮 */}
          <div className="flex items-center gap-4">
            <button
              onClick={handleAnalyze}
              disabled={loading}
              className="px-6 py-2 bg-indigo-600 hover:bg-indigo-500 disabled:bg-gray-700 text-white rounded-lg font-medium transition-colors"
            >
              {loading ? '分析中...' : '开始分析'}
            </button>
            {loading && (
              <span className="text-sm text-gray-400 animate-pulse">{progress}</span>
            )}
          </div>

          {error && (
            <div className="p-3 bg-red-950/50 border border-red-800 rounded-lg text-red-400 text-sm">
              {error}
            </div>
          )}
          
          {/* 执行日志 */}
          {(logs.length > 0 || loading) && (
            <div className="mt-4">
              <div className="flex items-center justify-between mb-2">
                <button
                  onClick={() => setShowLogs(!showLogs)}
                  className="text-sm text-gray-400 hover:text-white flex items-center gap-1"
                >
                  {showLogs ? '▼' : '▶'} 执行日志 ({logs.length} 条)
                </button>
                {apiStats.total > 0 && (
                  <span className="text-xs text-gray-500">
                    API调用: {apiStats.current}/{apiStats.total}
                  </span>
                )}
              </div>
              {showLogs && (
                <div className="bg-gray-950 rounded-lg border border-gray-800 p-3 max-h-64 overflow-y-auto font-mono text-xs">
                  {logs.length === 0 ? (
                    <span className="text-gray-600">暂无日志...</span>
                  ) : (
                    logs.map((log, idx) => (
                      <div key={idx} className="text-gray-400 py-0.5 border-b border-gray-900/50 last:border-0">
                        {log}
                      </div>
                    ))
                  )}
                  {loading && (
                    <div className="text-indigo-400 animate-pulse py-0.5">...</div>
                  )}
                </div>
              )}
            </div>
          )}
        </div>

        {/* 分析报告 */}
        {report && (
          <div className="space-y-6">
            {/* 概览 */}
            <div className="bg-gray-900 rounded-xl border border-gray-800 p-6">
              <h2 className="text-lg font-semibold text-white mb-4">📋 分析概览</h2>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <div className="bg-gray-950 rounded-lg p-4">
                  <div className="text-2xl font-bold text-white">{report.total_samples}</div>
                  <div className="text-xs text-gray-500">分析样本数</div>
                </div>
                <div className="bg-gray-950 rounded-lg p-4">
                  <div className="text-2xl font-bold text-green-400">{report.good_novels.length}</div>
                  <div className="text-xs text-gray-500">好小说</div>
                </div>
                <div className="bg-gray-950 rounded-lg p-4">
                  <div className="text-2xl font-bold text-red-400">{report.bad_novels.length}</div>
                  <div className="text-xs text-gray-500">坏小说</div>
                </div>
                <div className="bg-gray-950 rounded-lg p-4">
                  <div className="text-2xl font-bold text-indigo-400">
                    {report.rule_adjustments.length}
                  </div>
                  <div className="text-xs text-gray-500">规则总数</div>
                </div>
              </div>
            </div>

            {/* 保存按钮 */}
            <div className="flex gap-3">
              <button
                onClick={() => setShowSaveDialog(true)}
                className="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 text-white rounded-lg text-sm"
              >
                💾 保存优化记录
              </button>
            </div>

            {/* 保存对话框 */}
            {showSaveDialog && (
              <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
                <div className="bg-gray-900 rounded-xl border border-gray-800 p-6 w-full max-w-lg">
                  <h3 className="text-lg font-semibold text-white mb-4">保存优化记录</h3>
                  <p className="text-sm text-gray-400 mb-4">
                    记录本次优化分析，方便后续查看和应用。请描述本次优化的目的或背景。
                  </p>
                  <textarea
                    value={saveDescription}
                    onChange={(e) => setSaveDescription(e.target.value)}
                    placeholder="例如：第一次规则调优，针对区分度低的规则进行权重调整..."
                    className="w-full h-24 bg-gray-950 border border-gray-800 rounded-lg p-3 text-sm text-gray-200 placeholder-gray-600"
                  />
                  <div className="mt-4 flex justify-end gap-3">
                    <button
                      onClick={() => setShowSaveDialog(false)}
                      className="px-4 py-2 bg-gray-800 hover:bg-gray-700 text-gray-300 rounded-lg text-sm"
                    >
                      取消
                    </button>
                    <button
                      onClick={handleSaveOptimization}
                      disabled={!saveDescription.trim()}
                      className="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 disabled:bg-gray-700 text-white rounded-lg text-sm"
                    >
                      保存
                    </button>
                  </div>
                </div>
              </div>
            )}

            {/* 优化建议 */}
            {report.recommendations.length > 0 && (
              <div className="bg-gray-900 rounded-xl border border-gray-800 p-6">
                <h2 className="text-lg font-semibold text-white mb-4">💡 优化建议</h2>
                <div className="space-y-3">
                  {report.recommendations.map((rec, idx) => (
                    <div key={idx} className="flex gap-3 p-3 bg-gray-950 rounded-lg">
                      <span className="text-indigo-400 font-bold">{idx + 1}.</span>
                      <span className="text-gray-300 text-sm">{rec}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* 维度分析 */}
            {report.dimension_analysis.length > 0 && (
              <div className="bg-gray-900 rounded-xl border border-gray-800 p-6">
                <h2 className="text-lg font-semibold text-white mb-4">📊 维度分析</h2>
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="text-gray-500 border-b border-gray-800">
                        <th className="text-left py-2 px-3">维度</th>
                        <th className="text-center py-2 px-3">当前权重</th>
                        <th className="text-center py-2 px-3">建议权重</th>
                        <th className="text-center py-2 px-3">平均区分度</th>
                        <th className="text-center py-2 px-3">规则数</th>
                      </tr>
                    </thead>
                    <tbody>
                      {report.dimension_analysis.map((dim, idx) => (
                        <tr key={idx} className="border-b border-gray-800/50 hover:bg-gray-800/30">
                          <td className="py-3 px-3">
                            <div className="font-medium text-white">{dim.dimension_name}</div>
                            <div className="text-xs text-gray-500">{dim.dimension_id}</div>
                          </td>
                          <td className="text-center py-3 px-3 text-gray-400">
                            {dim.current_weight.toFixed(3)}
                          </td>
                          <td className="text-center py-3 px-3">
                            <span className={dim.suggested_weight > dim.current_weight ? 'text-green-400' : 'text-red-400'}>
                              {dim.suggested_weight.toFixed(3)}
                            </span>
                          </td>
                          <td className="text-center py-3 px-3">
                            <span className={discriminationColor(dim.avg_discrimination)}>
                              {dim.avg_discrimination.toFixed(3)}
                            </span>
                          </td>
                          <td className="text-center py-3 px-3 text-gray-400">
                            {dim.rules_count}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}

            {/* 规则调整详情 */}
            {report.rule_adjustments.length > 0 && (
              <div className="bg-gray-900 rounded-xl border border-gray-800 p-6">
                <div className="flex items-center justify-between mb-4">
                  <h2 className="text-lg font-semibold text-white">🔧 规则调整详情</h2>
                  <div className="flex gap-2">
                    {(['delete', 'modify', 'merge', 'keep'] as const).map(action => {
                      const count = report.rule_adjustments.filter(r => r.action === action).length
                      const config = actionConfig[action]
                      return (
                        <span key={action} className={`text-xs px-2 py-1 rounded ${config.color}`}>
                          {config.icon} {config.label} {count}
                        </span>
                      )
                    })}
                  </div>
                </div>
                
                {/* 按操作类型分组显示 */}
                {(['delete', 'modify', 'merge'] as const).map(action => {
                  const rules = report.rule_adjustments.filter(r => r.action === action)
                  if (rules.length === 0) return null
                  const config = actionConfig[action]
                  return (
                    <div key={action} className="mb-4">
                      <h3 className={`text-sm font-medium mb-2 ${config.color.split(' ')[1]}`}>
                        {config.icon} 建议{config.label} ({rules.length}条)
                      </h3>
                      <div className="space-y-2 max-h-64 overflow-y-auto">
                        {rules.map((rule, idx) => (
                          <div key={idx} className={`p-3 bg-gray-950 rounded-lg border ${action === 'delete' ? 'border-red-800/50' : action === 'modify' ? 'border-yellow-800/50' : 'border-blue-800/50'}`}>
                            <div className="flex items-start justify-between gap-4">
                              <div className="flex-1">
                                <div className="flex items-center gap-2">
                                  <span className="font-mono text-xs text-gray-500">{rule.rule_id}</span>
                                  <span className="font-medium text-white">{rule.name}</span>
                                  <span className="text-xs text-gray-500">({rule.dimension})</span>
                                  {rule.merge_target && (
                                    <span className="text-xs text-blue-400">→ {rule.merge_target}</span>
                                  )}
                                </div>
                                <div className="mt-1 text-sm text-gray-400">{rule.reason}</div>
                                {action !== 'delete' && (
                                  <div className="mt-1 text-xs text-gray-500">
                                    权重: {rule.current_weight.toFixed(3)} → {rule.suggested_weight.toFixed(3)}
                                  </div>
                                )}
                              </div>
                              <div className="text-right text-xs space-y-1">
                                <div>
                                  <span className="text-gray-500">好: </span>
                                  <span className={passRateColor(rule.good_pass_rate)}>
                                    {(rule.good_pass_rate * 100).toFixed(0)}%
                                  </span>
                                </div>
                                <div>
                                  <span className="text-gray-500">坏: </span>
                                  <span className={passRateColor(rule.bad_pass_rate)}>
                                    {(rule.bad_pass_rate * 100).toFixed(0)}%
                                  </span>
                                </div>
                                <div>
                                  <span className="text-gray-500">区分: </span>
                                  <span className={discriminationColor(rule.discrimination)}>
                                    {rule.discrimination > 0 ? '+' : ''}{rule.discrimination.toFixed(2)}
                                  </span>
                                </div>
                              </div>
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  )
                })}
                
                {/* 保持的规则（可展开） */}
                {(() => {
                  const keepRules = report.rule_adjustments.filter(r => r.action === 'keep')
                  if (keepRules.length === 0) return null
                  return (
                    <div className="mt-4 pt-4 border-t border-gray-800">
                      <details>
                        <summary className="text-sm text-gray-400 cursor-pointer hover:text-white">
                          ✅ 保持现状 ({keepRules.length}条) - 点击展开
                        </summary>
                        <div className="mt-2 space-y-2 max-h-48 overflow-y-auto">
                          {keepRules.slice(0, 10).map((rule, idx) => (
                            <div key={idx} className="p-2 bg-gray-950/50 rounded text-xs">
                              <span className="font-mono text-gray-500">{rule.rule_id}</span>
                              <span className="ml-2 text-gray-300">{rule.name}</span>
                              <span className="ml-2 text-green-400">区分度: {rule.discrimination.toFixed(2)}</span>
                            </div>
                          ))}
                          {keepRules.length > 10 && (
                            <div className="text-xs text-gray-500">...还有 {keepRules.length - 10} 条</div>
                          )}
                        </div>
                      </details>
                    </div>
                  )
                })()}
              </div>
            )}

            {/* 一致性问题 */}
            {report.consistency_issues.length > 0 && (
              <div className="bg-gray-900 rounded-xl border border-gray-800 p-6">
                <h2 className="text-lg font-semibold text-white mb-4">⚠️ 一致性问题</h2>
                <div className="space-y-3">
                  {report.consistency_issues.map((issue, idx) => (
                    <div key={idx} className="p-4 bg-yellow-950/30 border border-yellow-800/50 rounded-lg">
                      <div className="flex items-center gap-2 mb-2">
                        <span className={`text-xs px-2 py-0.5 rounded ${issue.novel_type === 'good' ? 'bg-green-900 text-green-400' : 'bg-red-900 text-red-400'}`}>
                          {issue.novel_type === 'good' ? '好小说' : '坏小说'}
                        </span>
                        <span className="text-yellow-400 text-sm font-medium">{issue.issue}</span>
                      </div>
                      <div className="text-xs text-gray-400 mb-2">
                        各块得分: {issue.block_scores.join(', ')} | 平均: {issue.average} | 标准差: {issue.std_dev}
                      </div>
                      <div className="text-xs text-gray-500">{issue.suggestion}</div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
