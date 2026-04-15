import React from 'react'
import { useNavigate } from 'react-router-dom'
import { trainingApi, pipelineApi } from '../services/api'

// 类型定义（与后端对齐）
interface PipelineConfig {
  novel_id: number
  run_imitation: boolean
  run_lora: boolean
  run_grpo: boolean
  num_imitation_samples: number
  lora_epochs: number
  grpo_iterations: number
}

interface PipelineStatus {
  pipeline_id: string
  status: 'running' | 'completed' | 'failed' | 'idle'
  current_stage: string
  progress: number
  stages_completed: number
  stages_total: number
  message: string
}

interface StageResult {
  stage_name: string
  status: string
  duration_seconds?: number
  metrics: Record<string, any>
  sample_outputs?: Array<Record<string, any>>
}

export const TrainingDashboard: React.FC = () => {
  const navigate = useNavigate()
  
  // 状态管理
  const [config, setConfig] = React.useState<PipelineConfig>({
    novel_id: 1,
    run_imitation: true,
    run_lora: true,
    run_grpo: true,
    num_imitation_samples: 432,
    lora_epochs: 3,
    grpo_iterations: 20,
  })
  const [running, setRunning] = React.useState(false)
  const [pipelineId, setPipelineId] = React.useState<string | null>(null)
  const [status, setStatus] = React.useState<PipelineStatus | null>(null)
  const [stages, setStages] = React.useState<StageResult[]>([])
  const [error, setError] = React.useState<string | null>(null)
  const [logs, setLogs] = React.useState<string[]>([])
  const pollRef = React.useRef<ReturnType<typeof setInterval> | null>(null)

  // 添加日志
  const addLog = (msg: string) => {
    const time = new Date().toLocaleTimeString()
    const logEntry = '[' + time + '] ' + msg
    setLogs(prev => [...prev.slice(-50), logEntry])
  }

  // 启动Pipeline
  const handleStartPipeline = async () => {
    setRunning(true)
    setError(null)
    setStages([])
    setStatus(null)
    setLogs([])
    addLog(`启动训练Pipeline: imitation=${config.run_imitation}, lora=${config.run_lora}, grpo=${config.run_grpo}`)
    addLog(`参数: ${config.num_imitation_samples}样本 / LoRA ${config.lora_epochs}轮 / GRPO ${config.grpo_iterations}迭代`)

    try {
      const result: any = await pipelineApi.start(config)
      const pid = result.pipeline_id
      setPipelineId(pid)
      addLog(`Pipeline 已启动! ID: ${pid}`)
      
      // 开始轮询状态
      startPolling(pid)
    } catch (err: any) {
      setError(err.response?.data?.detail || err.message || '启动失败')
      addLog(`错误: ${error}`)
      setRunning(false)
    }
  }

  // 轮询状态
  const startPolling = (pid: string) => {
    if (pollRef.current) clearInterval(pollRef.current)

    pollRef.current = setInterval(async () => {
      try {
        const res: PipelineStatus = await pipelineApi.getStatus(pid)
        setStatus(res)
        addLog(`阶段: ${res.current_stage} (${res.stages_completed}/${res.stages_total}) - ${Math.round(res.progress)}% - ${res.message}`)

        if (res.status === 'completed') {
          stopPolling()
          addLog('Pipeline 完成！获取结果...')
          await fetchResult(pid)
        } else if (res.status === 'failed') {
          stopPolling()
          addLog('Pipeline 失败')
          setRunning(false)
        }
      } catch (e) {
        console.error('Poll error:', e)
      }
    }, 3000) // 每3秒轮询一次
  }

  const stopPolling = () => {
    if (pollRef.current) {
      clearInterval(pollRef.current)
      pollRef.current = null
    }
    setRunning(false)
  }

  // 获取最终结果
  const fetchResult = async (pid: string) => {
    try {
      const result: any = await pipelineApi.getResult(pid)
      if (result.stages) {
        setStages(result.stages)
        result.stages.forEach((s: StageResult, i: number) => {
          addLog(`Stage ${i+1} [${s.status}]: ${s.stage_name} - metrics: ${JSON.stringify(s.metrics || {}).slice(0, 120)}`)
        })
      }
      addLog('=== 训练完成 ===')
    } catch (e) {
      addLog('获取结果失败，可在历史记录中查看')
    }
  }

  // 同步运行（小规模测试）
  const handleRunSync = async () => {
    setRunning(true)
    setError(null)
    setStages([])
    addLog('同步模式启动（小规模测试）...')

    try {
      const result: any = await pipelineApi.runSync({
        ...config,
        num_imitation_samples: 24,   // 同步模式用小数据集
        lora_epochs: 1,
        grpo_iterations: 5,
      })
      setPipelineId(result.pipeline_id)
      addLog(`同步Pipeline 完成! ID: ${result.pipeline_id}`)
      
      if (result.stages) {
        setStages(result.stages)
        result.stages.forEach((s: StageResult, i: number) => {
          addLog(`Stage ${i+1} [${s.status}]: ${JSON.stringify(s.metrics).slice(0, 150)}`)
        })
      }
    } catch (err: any) {
      setError(err.response?.data?.detail || err.message || '同步运行失败')
      addLog(`错误: ${error}`)
    } finally {
      setRunning(false)
    }
  }

  // 清理
  React.useEffect(() => {
    return () => { if (pollRef.current) clearInterval(pollRef.current) }
  }, [])

  return (
    <div className="p-6 max-w-7xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold">RL 训练中心 (V2)</h1>
        <button
          className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50"
          disabled={running}
          onClick={handleStartPipeline}
        >
          {running ? '⏳ 运行中...' : '🚀 启动完整 Pipeline'}
        </button>
      </div>

      {/* 配置面板 */}
      <div className="bg-white dark:bg-gray-800 rounded-lg shadow border border-gray-200 dark:border-gray-700 mb-6 p-5">
        <h2 className="text-lg font-semibold mb-4">训练配置</h2>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {/* 数据规模 */}
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">模仿学习样本数</label>
            <input
              type="number"
              value={config.num_imitation_samples}
              onChange={e => setConfig(c => ({ ...c, num_imitation_samples: parseInt(e.target.value) || 432 }))}
              className="w-full px-3 py-2 border rounded-md bg-white dark:bg-gray-700 dark:text-white"
              min="12" max="1000" step="12"
            />
            <p className="text-xs text-gray-400 mt-1">V2: 12场景 × 6变体 × 2增强</p>
          </div>
          
          {/* LoRA */}
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">LoRA 微调轮数</label>
            <input
              type="number"
              value={config.lora_epochs}
              onChange={e => setConfig(c => ({ ...c, lora_epochs: parseInt(e.target.value) || 3 }))}
              className="w-full px-3 py-2 border rounded-md bg-white dark:bg-gray-700 dark:text-white"
              min="1" max="10"
            />
          </div>
          
          {/* GRPO */}
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">GRPO 迭代次数</label>
            <input
              type="number"
              value={config.grpo_iterations}
              onChange={e => setConfig(c => ({ ...c, grpo_iterations: parseInt(e.target.value) || 20 }))}
              className="w-full px-3 py-2 border rounded-md bg-white dark:bg-gray-700 dark:text-white"
              min="5" max="100" step="5"
            />
            <p className="text-xs text-gray-400 mt-1">组采样策略优化</p>
          </div>
        </div>

        {/* 阶段开关 */}
        <div className="mt-4 flex gap-6">
          <label className="flex items-center gap-2 cursor-pointer">
            <input type="checkbox" checked={config.run_imitation} onChange={e => setConfig(c => ({ ...c, run_imitation: e.target.checked }))} />
            <span>模仿学习 (V2 增强版)</span>
          </label>
          <label className="flex items-center gap-2 cursor-pointer">
            <input type="checkbox" checked={config.run_lora} onChange={e => setConfig(c => ({ ...c, run_lora: e.target.checked }))} />
            <span>SFT / LoRA 微调</span>
          </label>
          <label className="flex items-center gap-2 cursor-pointer">
            <input type="checkbox" checked={config.run_grpo} onChange={e => setConfig(c => ({ ...c, run_grpo: e.target.checked }))} className="text-blue-600 font-semibold" />
            <span className="font-semibold">GRPO 强化学习 ⭐</span>
          </label>
        </div>

        {/* 快速测试按钮 */}
        <div className="mt-4 pt-4 border-t border-gray-200 dark:border-gray-700">
          <button
            className="px-3 py-1.5 text-sm bg-gray-100 dark:bg-gray-700 hover:bg-gray-200 dark:hover:bg-gray-600 rounded-md disabled:opacity-50"
            disabled={running}
            onClick={handleRunSync}
          >
            🧪 小规模同步测试 (24样本/1轮LoRA/5轮GRPO)
          </button>
        </div>
      </div>

      {/* 状态概览 */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6">
        {[
          { label: "状态", value: status ? status.status : "空闲", color: status?.status === 'running' ? 'text-blue-600' : status?.status === 'completed' ? 'text-green-600' : 'text-gray-500' },
          { label: "当前阶段", value: status?.current_stage || '-', color: '' },
          { label: "进度", value: status ? `${Math.round(status.progress)}%` : '-', color: '' },
          { label: "Pipeline ID", value: pipelineId ? pipelineId.slice(0, 12) + '...' : '-', color: 'text-gray-400 font-mono text-sm' },
        ].map(card => (
          <div key={card.label} className="bg-white dark:bg-gray-800 rounded-lg shadow p-4 border border-gray-200 dark:border-gray-700">
            <div className="text-xs text-gray-500">{card.label}</div>
            <div className={`text-xl font-bold ${card.color}`}>{card.value}</div>
          </div>
        ))}
      </div>

      {/* 进度条 */}
      {status && (
        <div className="bg-white dark:bg-gray-800 rounded-lg shadow border border-gray-200 dark:border-gray-700 mb-6 p-4">
          <div className="flex justify-between text-sm mb-2">
            <span>{status.current_stage}</span>
            <span>{Math.round(status.progress)}%</span>
          </div>
          <div className="w-full h-3 bg-gray-200 dark:bg-gray-700 rounded-full overflow-hidden">
            <div
              className={`h-full transition-all duration-500 ease-out rounded-full ${
                status.status === 'completed' ? 'bg-green-500' :
                status.status === 'failed' ? 'bg-red-500' :
                'bg-blue-500 animate-pulse'
              }`}
              style={{ width: `${status.progress}%` }}
            />
          </div>
          <p className="text-sm text-gray-500 mt-2">{status.message}</p>
        </div>
      )}

      {/* 各阶段结果 */}
      {stages.length > 0 && (
        <div className="bg-white dark:bg-gray-800 rounded-lg shadow border border-gray-200 dark:border-gray-700 mb-6">
          <div className="px-5 py-4 border-b border-gray-100 dark:border-gray-700 flex items-center justify-between">
            <h2 className="text-lg font-semibold">各阶段结果</h2>
            <span className="text-sm text-green-600">✅ {stages.filter(s => s.status === 'success').length}/{stages.length} 完成</span>
          </div>
          <div className="divide-y divide-gray-100 dark:divide-gray-700">
            {stages.map((stage, idx) => (
              <div key={idx} className="px-5 py-4 flex items-start justify-between hover:bg-gray-50 dark:hover:bg-gray-900/30">
                <div className="flex-1">
                  <div className="flex items-center gap-2">
                    <span className={`w-2.5 h-2.5 rounded-full flex-shrink-0 ${
                      stage.status === 'success' ? 'bg-green-500' :
                      stage.status === 'skipped' ? 'bg-yellow-500' : 'bg-red-500'
                    }`} />
                    <span className="font-medium">{stage.stage_name}</span>
                    <span className={`text-xs px-2 py-0.5 rounded ${
                      stage.mode === 'real' ? 'bg-green-100 text-green-700' :
                      stage.mode === 'simulated' ? 'bg-yellow-100 text-yellow-700' :
                      'bg-gray-100 text-gray-600'
                    }`}>
                      {stage.mode || stage.status}
                    </span>
                  </div>
                  
                  {/* 指标 */}
                  <div className="mt-2 ml-5 grid grid-cols-2 md:grid-cols-4 gap-2 text-xs">
                    {Object.entries(stage.metrics || {}).map(([k, v]) => (
                      <div key={k} className="bg-gray-50 dark:bg-gray-800 rounded px-2 py-1">
                        <span className="text-gray-400">{k}</span>
                        <span className="font-mono font-medium">{typeof v === 'number' ? v.toFixed(2) : String(v)}</span>
                      </div>
                    ))}
                  </div>

                  {/* GRPO 策略变化详情 */}
                  {stage.sample_outputs?.[0]?.strategy_changes && (
                    <div className="mt-2 ml-5 text-xs">
                      <span className="text-gray-500">动作策略变化:</span>
                      {(stage.sample_outputs[0].strategy_changes as Array<any>).map((ac: any) => (
                        <span key={ac.action} className="inline-block mr-3">
                          {ac.action}: {ac.before} → {ac.after} ({ac.change > 0 ? '+' : ''}{ac.change})
                        </span>
                      ))}
                    </div>
                  )}

                  {/* 奖励曲线 */}
                  {stage.sample_outputs?.[0]?.reward_progression && (
                    <div className="mt-2 ml-5">
                      <span className="text-xs text-gray-500 block mb-1">奖励曲线:</span>
                      <div className="flex items-end gap-1 h-8">
                        {(stage.sample_outputs[0].reward_progression as number[]).map((r, i) => (
                          <div
                            key={i}
                            className="bg-gradient-to-t from-blue-400 to-green-500 rounded-sm"
                            style={{
                              width: '8px',
                              height: `${Math.max(10, r * 60)}%`,
                              opacity: 0.7 + i * 0.03,
                            }}
                            title={`迭代${i + 1}: ${r.toFixed(3)}`}
                          />
                        ))}
                      </div>
                    </div>
                  )}
                </div>
                
                <div className="text-right text-sm text-gray-400 pl-4">
                  {stage.duration_seconds ? `${stage.duration_seconds.toFixed(0)}s` : ''}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* 日志 */}
      <div className="bg-white dark:bg-gray-800 rounded-lg shadow border border-gray-200 dark:border-gray-700">
        <div className="px-5 py-4 border-b border-gray-100 dark:border-gray-700 flex items-center justify-between">
          <h2 className="text-lg font-semibold">运行日志</h2>
          {logs.length > 0 && <span className="text-xs text-gray-400">{logs.length} 条</span>}
        </div>
        <div className="p-5 max-h-64 overflow-y-auto font-mono text-xs space-y-1 bg-gray-900/30 rounded-b mx-5 mb-5">
          {logs.length === 0 ? (
            <p className="text-gray-400 text-center py-8">暂无日志。启动 Pipeline 后此处将显示实时运行信息。</p>
          ) : (
            logs.map((log, i) => (
              <div key={i} className={`${log.includes('错误') ? 'text-red-400' : log.includes('完成') ? 'text-green-400' : 'text-gray-400'}`}>{log}</div>
            ))
          )}
        </div>
      </div>

      {/* 错误提示 */}
      {error && (
        <div className="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 text-red-700 dark:text-red-400 rounded-lg p-4 mb-6">
          <strong>错误:</strong> {error}
        </div>
      )}
    </div>
  )
}
