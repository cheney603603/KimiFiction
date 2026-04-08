/**
 * 新版工作流创作页面
 * 修复内容:
 * 1. 输入为空时阻止执行（除非已完成该阶段）
 * 2. 上一阶段结果自动传入下一阶段（后端实现）
 * 3. 进入下一阶段只切换阶段，不自动执行
 * 4. 章节写作添加章节号输入
 * 5. 章节写作调用真正的LLM（后端实现）
 * 6. 章节写作添加更多参数（文风、环境描写级别、对话占比、注意事项）
 * 7. 阶段结果保存到数据库
 */
import { useState, useEffect, useRef, useCallback } from 'react'
import { useParams, Link } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  ArrowLeft, Pause, CheckCircle, Circle, Loader2, ChevronRight,
  Sparkles, FileText, Users, Globe, Layers, Edit3, BookOpen,
  AlertCircle, RotateCcw, MessageSquare, Send, Target, Terminal,
  Clock, BookMarked,
} from 'lucide-react'
import { workflowApi, novelApi, chapterApi, llmConfigApi } from '../services/api'

const PHASES = [
  { id: 'demand_analysis', name: '需求分析', icon: Target, color: 'blue', description: '分析创作需求，确定小说类型、风格、目标读者等', allowEmptyExecute: false },
  { id: 'world_building', name: '世界观', icon: Globe, color: 'purple', description: '构建小说的世界观设定', allowEmptyExecute: true },
  { id: 'character_design', name: '角色设计', icon: Users, color: 'pink', description: '设计主要角色', allowEmptyExecute: true },
  { id: 'outline_draft', name: '剧情大纲', icon: FileText, color: 'green', description: '生成完整的故事大纲', allowEmptyExecute: true },
  { id: 'plot_design', name: '冲突伏笔', icon: Layers, color: 'orange', description: '设计主线剧情、冲突、伏笔等', allowEmptyExecute: true },
  { id: 'outline_detail', name: '章节细纲', icon: Edit3, color: 'teal', description: '为每个章节生成详细的细纲', allowEmptyExecute: true },
  { id: 'chapter_writing', name: '章节写作', icon: BookOpen, color: 'indigo', description: '开始撰写具体章节内容', allowEmptyExecute: true },
]

// 阶段结果显示组件
function PhaseResultViewer({ phaseId, phaseName, novelId, isCompleted }: { phaseId: string; phaseName: string; novelId: number; isCompleted: boolean }) {
  const [result, setResult] = useState<any>(null)
  const [promptInfo, setPromptInfo] = useState<any>(null)
  const [loading, setLoading] = useState(false)
  const [expanded, setExpanded] = useState(false)
  const [showPrompt, setShowPrompt] = useState(false)
  const [toggling, setToggling] = useState(false)
  const queryClient = useQueryClient()

  useEffect(() => {
    if (novelId) {
      setLoading(true)
      // 获取阶段结果
      workflowApi.getPhaseResult(novelId, phaseId)
        .then((data: any) => {
          if (data.success && data.data) {
            setResult(data.data)
          } else {
            setResult(null)
          }
        })
        .catch(console.error)
      
      // 获取提示词信息
      workflowApi.getPhasePromptInfo(novelId, phaseId)
        .then((data: any) => {
          if (data.success && data.prompt_info) {
            setPromptInfo(data.prompt_info)
          }
        })
        .catch(console.error)
        .finally(() => setLoading(false))
    }
  }, [phaseId, novelId, isCompleted])

  const handleToggleCompletion = async () => {
    setToggling(true)
    try {
      const response = await workflowApi.togglePhaseCompletion(novelId, phaseId, result || undefined) as any
      if (response.success) {
        // 刷新进度数据
        queryClient.invalidateQueries({ queryKey: ['workflowProgress', novelId] })
        // 重新获取阶段结果
        const data = await workflowApi.getPhaseResult(novelId, phaseId) as any
        if (data.success && data.data) {
          setResult(data.data)
        } else {
          setResult(null)
        }
      }
    } catch (error) {
      console.error('切换阶段状态失败:', error)
    } finally {
      setToggling(false)
    }
  }

  const renderContent = () => {
    switch (phaseId) {
      case 'demand_analysis':
        return (
          <div className="space-y-2 text-sm">
            {result.genre && <div><span className="text-gray-500">类型:</span> <span className="font-medium">{result.genre}</span></div>}
            {result.target_audience && <div><span className="text-gray-500">目标读者:</span> <span>{result.target_audience}</span></div>}
            {result.main_selling_points && (
              <div>
                <span className="text-gray-500">核心卖点:</span>
                <ul className="ml-4 mt-1 space-y-1">
                  {Array.isArray(result.main_selling_points) ? result.main_selling_points.map((p: string, i: number) => (
                    <li key={i} className="text-gray-700 dark:text-gray-300">• {p}</li>
                  )) : <li className="text-gray-700 dark:text-gray-300">{result.main_selling_points}</li>}
                </ul>
              </div>
            )}
          </div>
        )
      case 'world_building':
        return (
          <div className="space-y-2 text-sm">
            {result.world_name && <div><span className="text-gray-500">世界名称:</span> <span className="font-medium">{result.world_name}</span></div>}
            {result.overview && <div><span className="text-gray-500">概述:</span> <span className="text-gray-700 dark:text-gray-300">{result.overview}</span></div>}
            {result.power_systems && result.power_systems.length > 0 && (
              <div>
                <span className="text-gray-500">力量体系:</span>
                <ul className="ml-4 mt-1 space-y-1">
                  {result.power_systems.slice(0, 2).map((ps: any, i: number) => (
                    <li key={i} className="text-gray-700 dark:text-gray-300">• {ps.name || '未命名'}</li>
                  ))}
                  {result.power_systems.length > 2 && <li className="text-gray-400">...等{result.power_systems.length}个体系</li>}
                </ul>
              </div>
            )}
          </div>
        )
      case 'character_design':
        const characters = result.characters || []
        return (
          <div className="space-y-2 text-sm">
            <div><span className="text-gray-500">角色数量:</span> <span className="font-medium">{characters.length}人</span></div>
            {characters.length > 0 && (
              <div>
                <span className="text-gray-500">主要角色:</span>
                <ul className="ml-4 mt-1 space-y-1">
                  {characters.slice(0, 3).map((char: any, i: number) => (
                    <li key={i} className="text-gray-700 dark:text-gray-300">
                      • {char.name || '未命名'} {char.role_type ? `(${char.role_type})` : ''}
                    </li>
                  ))}
                  {characters.length > 3 && <li className="text-gray-400">...等{characters.length}个角色</li>}
                </ul>
              </div>
            )}
          </div>
        )
      case 'plot_design':
        return (
          <div className="space-y-2 text-sm">
            {result.core_conflicts && result.core_conflicts.length > 0 && (
              <div>
                <span className="text-gray-500">核心冲突:</span>
                <ul className="ml-4 mt-1 space-y-1">
                  {result.core_conflicts.slice(0, 2).map((c: any, i: number) => (
                    <li key={i} className="text-gray-700 dark:text-gray-300">• {c.name || c.type || '冲突'}</li>
                  ))}
                </ul>
              </div>
            )}
            {result.foreshadowing_plan && (
              <div><span className="text-gray-500">伏笔数量:</span> <span>{Array.isArray(result.foreshadowing_plan) ? result.foreshadowing_plan.length : '已规划'}</span></div>
            )}
          </div>
        )
      case 'outline_draft':
        const volumes = result.volumes || []
        return (
          <div className="space-y-2 text-sm">
            <div><span className="text-gray-500">总卷数:</span> <span className="font-medium">{volumes.length}卷</span></div>
            {volumes.length > 0 && (
              <div>
                <span className="text-gray-500">卷标题:</span>
                <ul className="ml-4 mt-1 space-y-1">
                  {volumes.slice(0, 2).map((v: any, i: number) => (
                    <li key={i} className="text-gray-700 dark:text-gray-300">• {v.title || `第${v.volume_number}卷`}</li>
                  ))}
                  {volumes.length > 2 && <li className="text-gray-400">...等{volumes.length}卷</li>}
                </ul>
              </div>
            )}
          </div>
        )
      default:
        return <div className="text-sm text-gray-500">该阶段已完成，数据已保存</div>
    }
  }

  return (
    <div className={`mt-3 rounded-lg p-3 ${isCompleted ? 'bg-green-50 dark:bg-green-900/20 border border-green-200 dark:border-green-800' : 'bg-gray-50 dark:bg-gray-900'}`}>
      <div className="flex items-center justify-between">
        <button
          onClick={() => setExpanded(!expanded)}
          className="flex items-center gap-2 text-left flex-1"
        >
          <span className={`text-xs font-medium ${isCompleted ? 'text-green-700 dark:text-green-400' : 'text-gray-600 dark:text-gray-400'}`}>
            {phaseName}
            {isCompleted && <CheckCircle className="h-3 w-3 inline ml-1" />}
          </span>
          {expanded ? <ChevronRight className="h-3 w-3 rotate-90 transition-transform" /> : <ChevronRight className="h-3 w-3 transition-transform" />}
        </button>
        <div className="flex items-center gap-1">
          {isCompleted && promptInfo && (
            <button
              onClick={() => setShowPrompt(!showPrompt)}
              className="text-xs px-2 py-1 rounded bg-blue-100 text-blue-700 hover:bg-blue-200 dark:bg-blue-900/30 dark:text-blue-400"
            >
              {showPrompt ? '隐藏提示词' : '查看提示词'}
            </button>
          )}
          <button
            onClick={handleToggleCompletion}
            disabled={toggling}
            className={`text-xs px-2 py-1 rounded ${
              isCompleted 
                ? 'bg-orange-100 text-orange-700 hover:bg-orange-200 dark:bg-orange-900/30 dark:text-orange-400' 
                : 'bg-green-100 text-green-700 hover:bg-green-200 dark:bg-green-900/30 dark:text-green-400'
            } disabled:opacity-50`}
          >
            {toggling ? <Loader2 className="h-3 w-3 animate-spin" /> : isCompleted ? '标记未完成' : '标记完成'}
          </button>
        </div>
      </div>
      {expanded && (
        <div className="mt-2 pt-2 border-t border-gray-200 dark:border-gray-700">
          {loading ? (
            <div className="flex items-center gap-2 text-xs text-gray-500">
              <Loader2 className="h-3 w-3 animate-spin" /> 加载中...
            </div>
          ) : isCompleted && result ? (
            renderContent()
          ) : (
            <div className="text-sm text-gray-500">该阶段尚未完成</div>
          )}
        </div>
      )}
      {showPrompt && promptInfo && (
        <div className="mt-2 pt-2 border-t border-gray-200 dark:border-gray-700">
          <div className="text-xs font-medium text-gray-600 dark:text-gray-400 mb-2">提示词构建信息：</div>
          {promptInfo.user_input && (
            <div className="mb-2">
              <div className="text-xs text-gray-500">用户输入：</div>
              <div className="text-xs text-gray-700 dark:text-gray-300 bg-gray-100 dark:bg-gray-800 p-2 rounded">{promptInfo.user_input}</div>
            </div>
          )}
          {promptInfo.context_summary && (
            <div className="mb-2">
              <div className="text-xs text-gray-500">上下文摘要：</div>
              <div className="text-xs text-gray-700 dark:text-gray-300">{promptInfo.context_summary}</div>
            </div>
          )}
          {promptInfo.key_requirements && promptInfo.key_requirements.length > 0 && (
            <div className="mb-2">
              <div className="text-xs text-gray-500">关键需求：</div>
              <ul className="text-xs text-gray-700 dark:text-gray-300 ml-4">
                {promptInfo.key_requirements.map((req: string, i: number) => (
                  <li key={i}>• {req}</li>
                ))}
              </ul>
            </div>
          )}
          {promptInfo.template_adaptations && promptInfo.template_adaptations.length > 0 && (
            <div>
              <div className="text-xs text-gray-500">模板调整：</div>
              <ul className="text-xs text-gray-700 dark:text-gray-300 ml-4">
                {promptInfo.template_adaptations.map((adapt: string, i: number) => (
                  <li key={i}>• {adapt}</li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

const PHASE_COLORS: Record<string, Record<string, string>> = {
  blue: { bg: 'bg-blue-100 dark:bg-blue-900/30', text: 'text-blue-600 dark:text-blue-400', ring: 'ring-blue-500' },
  purple: { bg: 'bg-purple-100 dark:bg-purple-900/30', text: 'text-purple-600 dark:text-purple-400', ring: 'ring-purple-500' },
  pink: { bg: 'bg-pink-100 dark:bg-pink-900/30', text: 'text-pink-600 dark:text-pink-400', ring: 'ring-pink-500' },
  orange: { bg: 'bg-orange-100 dark:bg-orange-900/30', text: 'text-orange-600 dark:text-orange-400', ring: 'ring-orange-500' },
  green: { bg: 'bg-green-100 dark:bg-green-900/30', text: 'text-green-600 dark:text-green-400', ring: 'ring-green-500' },
  teal: { bg: 'bg-teal-100 dark:bg-teal-900/30', text: 'text-teal-600 dark:text-teal-400', ring: 'ring-teal-500' },
  indigo: { bg: 'bg-indigo-100 dark:bg-indigo-900/30', text: 'text-indigo-600 dark:text-indigo-400', ring: 'ring-indigo-500' },
}

const WRITING_STYLE_OPTIONS = [
  { value: '叙事流畅，情节紧凑', label: '叙事流畅，情节紧凑' },
  { value: '古风典雅，辞藻华丽', label: '古风典雅，辞藻华丽' },
  { value: '现代简洁，对话为主', label: '现代简洁，对话为主' },
  { value: '网络轻松，幽默诙谐', label: '网络轻松，幽默诙谐' },
  { value: '悬疑烧脑，节奏明快', label: '悬疑烧脑，节奏明快' },
  { value: '情感细腻，心理描写丰富', label: '情感细腻，心理描写丰富' },
]

const ENV_LEVEL_OPTIONS = [
  { value: 'minimal', label: '简洁暗示' },
  { value: 'normal', label: '适度描写' },
  { value: 'rich', label: '丰富细腻' },
]

const DIALOGUE_RATIO_OPTIONS = [
  { value: 0.2, label: '低（20%）— 偏叙述' },
  { value: 0.3, label: '中（30%）— 平衡' },
  { value: 0.4, label: '较高（40%）— 对话较多' },
  { value: 0.5, label: '高（50%）— 对话为主' },
]

interface ChatMessage { role: 'user' | 'assistant' | 'system'; content: string; timestamp: Date; phase?: string }
interface ProgressStep { step_id: string; name: string; status: string; progress: string; progress_percent: number; logs: Array<{ timestamp: string; level: string; message: string }>; error?: string }
interface TaskProgress { task_id: string; current_step: string; steps: Record<string, ProgressStep> }

function isPhaseCompleted(phaseId: string, completedPhases: string[]): boolean { return completedPhases.includes(phaseId) }

export function WorkflowPage() {
  const { novelId } = useParams<{ novelId: string }>()
  const queryClient = useQueryClient()
  const id = parseInt(novelId || '0')

  const [chatMessages, setChatMessages] = useState<ChatMessage[]>(() => {
    if (id) {
      const saved = localStorage.getItem(`workflow_chat_${id}`)
      if (saved) {
        try { const parsed = JSON.parse(saved); return parsed.map((msg: any) => ({ ...msg, timestamp: new Date(msg.timestamp) })) } catch (e) {}
      }
    }
    return []
  })
  const [inputMessage, setInputMessage] = useState('')
  const [isTyping, setIsTyping] = useState(false)
  const [currentTaskId, setCurrentTaskId] = useState<string | null>(null)
  const [taskProgress, setTaskProgress] = useState<TaskProgress | null>(null)
  const [showProgressPanel, setShowProgressPanel] = useState(false)
  const [chapterNumber, setChapterNumber] = useState(1)
  const [writingStyle, setWritingStyle] = useState('叙事流畅，情节紧凑')
  const [envLevel, setEnvLevel] = useState('normal')
  const [dialogueRatio, setDialogueRatio] = useState(0.3)
  const [chapterNotes, setChapterNotes] = useState('')
  const [phaseTimeouts, setPhaseTimeouts] = useState<Record<string, number>>({})
  const [showTimeoutConfig, setShowTimeoutConfig] = useState(false)
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const progressPollingRef = useRef<ReturnType<typeof setInterval> | null>(null)

  const { data: novel, isLoading: isLoadingNovel } = useQuery({ queryKey: ['novel', id], queryFn: () => novelApi.get(id), enabled: !!id })
  const { data: progress } = useQuery({ queryKey: ['workflowProgress', id], queryFn: () => workflowApi.getProgress(id), enabled: !!id, refetchInterval: 5000, retry: false })
  const { data: chapters } = useQuery({ queryKey: ['chapters', id], queryFn: () => chapterApi.list(id), enabled: !!id })

  // 辅助函数：检查阶段是否已完成
  const isPhaseCompleted = (phaseId: string, completed: string[]) => completed.includes(phaseId)

  useEffect(() => {
    const syncConfig = async () => {
      try {
        const savedConfig = localStorage.getItem('llm_config')
        if (savedConfig) { const config = JSON.parse(savedConfig); await llmConfigApi.saveConfig({ provider: config.provider, apiKey: config.apiKey, baseUrl: config.baseUrl, model: config.model, responseTime: config.responseTime }) }
      } catch {}
    }
    syncConfig()

    // 加载阶段超时配置
    try {
      const savedTimeouts = localStorage.getItem('phase_timeouts')
      if (savedTimeouts) {
        setPhaseTimeouts(JSON.parse(savedTimeouts))
      }
    } catch {}
  }, [id])

  // 保存阶段超时配置到localStorage
  const handlePhaseTimeoutChange = (phaseId: string, timeout: number) => {
    const newTimeouts = { ...phaseTimeouts, [phaseId]: timeout }
    setPhaseTimeouts(newTimeouts)
    localStorage.setItem('phase_timeouts', JSON.stringify(newTimeouts))
  }

  const completedPhases: string[] = (progress as any)?.completed_phases || []
  const currentPhaseIndex = (progress as any)?.current_phase ? PHASES.findIndex(p => p.id === (progress as any).current_phase) : 0
  const currentPhase = PHASES[Math.max(0, currentPhaseIndex)]
  const phaseProgress = (progress as any)?.progress_percent || 0
  const isCurrentPhaseCompleted = currentPhase ? isPhaseCompleted(currentPhase.id, completedPhases) : false

  const pollTaskProgress = useCallback(async (taskId: string) => {
    try {
      const progressData = await workflowApi.getTaskProgress(taskId) as unknown as TaskProgress
      setTaskProgress(progressData)
      const currentStep = progressData.steps[progressData.current_step]
      if (currentStep && (currentStep.status === 'completed' || currentStep.status === 'failed')) {
        if (progressPollingRef.current) { clearInterval(progressPollingRef.current); progressPollingRef.current = null }
        setIsTyping(false); setCurrentTaskId(null)
        if (currentStep.status === 'completed') {
          const lastLog = currentStep.logs.slice(-1)[0]?.message || '执行完成'
          setChatMessages(prev => [...prev, { role: 'assistant', content: `成功: ${currentStep.name}\n\n${lastLog}`, timestamp: new Date(), phase: currentPhase?.id }])
        } else {
          setChatMessages(prev => [...prev, { role: 'system', content: `失败: ${currentStep.name} - ${currentStep.error || '未知错误'}`, timestamp: new Date() }])
        }
        queryClient.invalidateQueries({ queryKey: ['workflowProgress', id] }); queryClient.invalidateQueries({ queryKey: ['chapters', id] }); queryClient.invalidateQueries({ queryKey: ['characters', id] })
      }
    } catch {}
  }, [currentPhase?.id, id, queryClient])

  const executePhaseMutation = useMutation({
    mutationFn: async ({ phase, input, timeout }: { phase: string; input?: string; timeout?: number }) => {
      setIsTyping(true); setShowProgressPanel(true)
      const inputData: any = {}
      if (input) inputData.user_input = input
      if (chatMessages.length > 0) { inputData.messages = chatMessages.slice(-20).map(msg => ({ role: msg.role, content: msg.content, timestamp: msg.timestamp.toISOString(), phase: msg.phase })) }
      const result = await workflowApi.executePhase(id, { phase, input_data: inputData, timeout }) as any
      if (result.task_id) {
        setCurrentTaskId(result.task_id)
        if (progressPollingRef.current) clearInterval(progressPollingRef.current)
        progressPollingRef.current = setInterval(() => pollTaskProgress(result.task_id), 1000)
        pollTaskProgress(result.task_id)
      }
      return result
    },
    onError: (error: any) => {
      setIsTyping(false)
      const msg = error?.response?.data?.detail || error?.message || '执行失败'
      setChatMessages(prev => [...prev, { role: 'system', content: `错误: ${msg}`, timestamp: new Date() }])
    },
  })

  useEffect(() => () => { if (progressPollingRef.current) clearInterval(progressPollingRef.current) }, [])
  useEffect(() => { messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' }) }, [chatMessages])
  useEffect(() => { if (id) localStorage.setItem(`workflow_chat_${id}`, JSON.stringify(chatMessages.map(m => ({ ...m, timestamp: m.timestamp.toISOString() })))) }, [chatMessages, id])

  // Fix 1: Empty input blocks execution
  const handleExecuteCurrentPhase = () => {
    if (!currentPhase) return
    if (!inputMessage.trim() && !isCurrentPhaseCompleted && !currentPhase.allowEmptyExecute) {
      setChatMessages(prev => [...prev, { role: 'system', content: '请先在上方输入框中输入内容，再执行当前阶段', timestamp: new Date() }])
      return
    }
    if (inputMessage.trim()) {
      setChatMessages(prev => [...prev, { role: 'user', content: inputMessage.trim(), timestamp: new Date(), phase: currentPhase.id }])
      setInputMessage('')
    }
    // 获取当前阶段的超时设置（如果有）
    const timeout = phaseTimeouts[currentPhase.id]
    executePhaseMutation.mutate({ phase: currentPhase.id, input: inputMessage.trim() || undefined, timeout })
  }

  // 切换到指定阶段
  const handleSwitchPhase = (targetIndex: number) => {
    if (targetIndex < 0 || targetIndex >= PHASES.length) return
    if (targetIndex === currentPhaseIndex) return
    
    const targetPhase = PHASES[targetIndex]
    setChatMessages(prev => [...prev, { role: 'system', content: `已切换到「${targetPhase.name}」阶段，请在下方输入您对这一阶段的指导，然后点击"执行${targetPhase.name}"开始`, timestamp: new Date() }])
    
    // 调用后端 API 切换阶段
    workflowApi.switchPhase(id, targetPhase.id).then(() => {
      // 刷新进度数据
      queryClient.invalidateQueries({ queryKey: ['workflowProgress', id] })
    }).catch((error: any) => {
      const msg = error?.response?.data?.detail || error?.message || '切换阶段失败'
      setChatMessages(prev => [...prev, { role: 'system', content: `错误: ${msg}`, timestamp: new Date() }])
    })
  }

  // Fix 3: Next phase only switches, does not execute
  const handleNextPhase = () => {
    handleSwitchPhase(currentPhaseIndex + 1)
  }

  // 返回上一阶段
  const handlePrevPhase = () => {
    handleSwitchPhase(currentPhaseIndex - 1)
  }

  // Fix 1: Empty message not sent
  const handleSendMessage = () => {
    if (!inputMessage.trim() || !currentPhase) return
    const userMessage = inputMessage.trim()
    setChatMessages(prev => [...prev, { role: 'user', content: userMessage, timestamp: new Date(), phase: currentPhase.id }])
    setInputMessage('')
    // 获取当前阶段的超时设置（如果有）
    const timeout = phaseTimeouts[currentPhase.id]
    executePhaseMutation.mutate({ phase: currentPhase.id, input: userMessage, timeout })
  }

  // Fix 4 & 6: Chapter writing with parameters
  const handleWriteChapter = () => {
    if (!chapterNumber || chapterNumber < 1) {
      setChatMessages(prev => [...prev, { role: 'system', content: '请输入有效的章节号', timestamp: new Date() }])
      return
    }
    setIsTyping(true); setShowProgressPanel(true)
    workflowApi.writeChapter(id, {
      chapter_number: chapterNumber,
      writing_style: writingStyle,
      env_description_level: envLevel,
      dialogue_ratio: dialogueRatio,
      notes: chapterNotes || undefined,
    }).then((result: any) => {
      if (result.task_id) {
        setCurrentTaskId(result.task_id)
        if (progressPollingRef.current) clearInterval(progressPollingRef.current)
        progressPollingRef.current = setInterval(() => pollTaskProgress(result.task_id), 1000)
        pollTaskProgress(result.task_id)
      }
    }).catch((error: any) => {
      setIsTyping(false)
      const msg = error?.response?.data?.detail || error?.message || '撰写失败'
      setChatMessages(prev => [...prev, { role: 'system', content: `错误: ${msg}`, timestamp: new Date() }])
    })
  }

  if (!id) return (<div className="flex items-center justify-center h-96"><AlertCircle className="h-12 w-12 text-red-500" /><p className="ml-4 text-lg text-gray-600 dark:text-gray-400">无效的小说ID</p></div>)
  if (isLoadingNovel) return (<div className="flex items-center justify-center h-96"><Loader2 className="h-12 w-12 animate-spin text-primary-500" /><p className="ml-4 text-lg text-gray-600 dark:text-gray-400">加载中...</p></div>)

  const currentStepLogs = taskProgress?.current_step ? taskProgress.steps[taskProgress.current_step]?.logs || [] : []
  const canExecute = !isTyping && (isCurrentPhaseCompleted || currentPhase?.allowEmptyExecute || !!inputMessage.trim())

  return (
    <div className="h-[calc(100vh-4rem)] flex flex-col">
      <div className="bg-white dark:bg-gray-800 border-b border-gray-200 dark:border-gray-700 px-6 py-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-4">
            <Link to={`/novel/${id}`} className="flex items-center gap-2 text-gray-600 dark:text-gray-400 hover:text-primary-600"><ArrowLeft className="h-5 w-5" /> 返回</Link>
            <div className="h-6 w-px bg-gray-300 dark:bg-gray-600" />
            <div><h1 className="text-xl font-semibold text-gray-900 dark:text-white">{(novel as any)?.title || 'AI创作助手'}</h1><p className="text-sm text-gray-500 dark:text-gray-400">当前阶段: {currentPhase?.name || '准备中'}</p></div>
          </div>
          <div className="flex items-center gap-3">
            <button onClick={() => setShowProgressPanel(!showProgressPanel)} className={`flex items-center gap-2 px-4 py-2 rounded-lg ${showProgressPanel ? 'bg-primary-100 text-primary-700 dark:bg-primary-900 dark:text-primary-300' : 'bg-gray-100 text-gray-700 dark:bg-gray-700 dark:text-gray-300'}`}><Terminal className="h-4 w-4" /> 执行日志 {isTyping && <Loader2 className="h-4 w-4 animate-spin" />}</button>
            <button onClick={() => workflowApi.pause(id)} className="flex items-center gap-2 px-4 py-2 bg-orange-600 text-white rounded-lg hover:bg-orange-700"><Pause className="h-4 w-4" /> 暂停</button>
          </div>
        </div>
        <div className="mt-4">
          <div className="flex items-center justify-between mb-2">
            <span className="text-sm text-gray-500 dark:text-gray-400">创作进度: {phaseProgress}%</span>
            <span className="text-sm text-gray-500 dark:text-gray-400">章节: {(progress as any)?.completed_chapters || 0} / {(progress as any)?.target_chapters || 0}</span>
          </div>
          <div className="h-2 bg-gray-200 dark:bg-gray-700 rounded-full overflow-hidden"><div className="h-full bg-gradient-to-r from-primary-500 to-primary-600 transition-all" style={{ width: `${phaseProgress}%` }} /></div>
        </div>
        <div className="flex items-center gap-2 mt-4 overflow-x-auto pb-2">
          {PHASES.map((phase, index) => {
            const isCompleted = isPhaseCompleted(phase.id, completedPhases)
            const isCurrent = index === currentPhaseIndex
            const colors = PHASE_COLORS[phase.color]
            return (
              <button
                key={phase.id}
                onClick={() => {
                  // 点击阶段标签直接跳转到该阶段
                  if (index !== currentPhaseIndex) {
                    handleSwitchPhase(index)
                  }
                }}
                className={`flex items-center gap-2 px-3 py-1.5 rounded-full whitespace-nowrap transition-all cursor-pointer ${
                  isCompleted
                    ? 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400 hover:bg-green-200 dark:hover:bg-green-900/50'
                    : isCurrent
                    ? `${colors.bg} ${colors.text} ring-2 ${colors.ring} ring-offset-2 ring-offset-white dark:ring-offset-gray-800`
                    : 'bg-gray-100 text-gray-500 dark:bg-gray-700 dark:text-gray-400 hover:bg-gray-200 dark:hover:bg-gray-600'
                }`}
              >
                {isCompleted ? (
                  <CheckCircle className="h-4 w-4" />
                ) : isCurrent ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <Circle className="h-4 w-4" />
                )}
                <span className="text-sm font-medium">{phase.name}</span>
                {index < PHASES.length - 1 && (
                  <ChevronRight className="h-4 w-4 text-gray-400" />
                )}
              </button>
            )
          })}
        </div>
      </div>

      <div className="flex-1 flex overflow-hidden">
        <div className="w-80 border-r border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-900 overflow-y-auto p-4 space-y-4">
          <div className="bg-white dark:bg-gray-800 rounded-xl p-4 shadow-sm">
            <div className={`inline-flex items-center gap-2 px-3 py-1.5 rounded-full mb-3 ${PHASE_COLORS[currentPhase?.color || 'blue'].bg} ${PHASE_COLORS[currentPhase?.color || 'blue'].text}`}>
              {currentPhase && <currentPhase.icon className="h-4 w-4" />}
              <span className="text-sm font-medium">{currentPhase?.name}</span>
              {isCurrentPhaseCompleted && <CheckCircle className="h-3 w-3 text-green-500" />}
            </div>
            <p className="text-sm text-gray-600 dark:text-gray-400 mb-4">{currentPhase?.description}</p>

            {/* 阶段超时配置 */}
            <div className="mb-4 p-3 bg-gray-50 dark:bg-gray-700 rounded-lg">
              <button
                onClick={() => setShowTimeoutConfig(!showTimeoutConfig)}
                className="flex items-center justify-between w-full text-sm"
              >
                <div className="flex items-center gap-2 text-gray-700 dark:text-gray-300">
                  <Clock className="h-4 w-4" />
                  <span>超时设置</span>
                </div>
                <span className="text-xs text-gray-500 dark:text-gray-400">
                  {phaseTimeouts[currentPhase?.id || ''] ? `${phaseTimeouts[currentPhase?.id || '']}秒` : '默认'}
                </span>
              </button>
              {showTimeoutConfig && (
                <div className="mt-3 space-y-2">
                  <div className="flex items-center gap-2">
                    <input
                      type="number"
                      min="30"
                      max="3600"
                      value={phaseTimeouts[currentPhase?.id || ''] || ''}
                      onChange={(e) => handlePhaseTimeoutChange(currentPhase?.id || '', parseInt(e.target.value) || 0)}
                      className="flex-1 px-3 py-2 text-sm border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-800 text-gray-900 dark:text-white focus:ring-2 focus:ring-primary-500 focus:border-transparent"
                      placeholder="留空则使用默认值"
                    />
                    <span className="text-sm text-gray-500 dark:text-gray-400">秒</span>
                  </div>
                  <p className="text-xs text-gray-500 dark:text-gray-400">
                    为当前阶段设置LLM请求超时时间（30-3600秒）。留空则使用系统自动计算的超时时间。
                  </p>
                  {phaseTimeouts[currentPhase?.id || ''] && (
                    <button
                      onClick={() => handlePhaseTimeoutChange(currentPhase?.id || '', 0)}
                      className="text-xs text-red-600 hover:text-red-700 dark:text-red-400 dark:hover:text-red-300"
                    >
                      清除自定义超时，使用默认值
                    </button>
                  )}
                </div>
              )}
            </div>

            <div className="space-y-2">
              <button onClick={handleExecuteCurrentPhase} disabled={!canExecute}
                className="w-full flex items-center justify-center gap-2 px-4 py-2.5 bg-primary-600 text-white rounded-lg hover:bg-primary-700 disabled:opacity-50 disabled:cursor-not-allowed"
                title={!canExecute && !isCurrentPhaseCompleted && !currentPhase?.allowEmptyExecute ? '请先在上方输入框中输入内容' : ''}>
                {isTyping ? <Loader2 className="h-5 w-5 animate-spin" /> : <Sparkles className="h-5 w-5" />}
                {isTyping ? '执行中...' : `执行${currentPhase?.name || ''}`}
              </button>
              {currentPhaseIndex > 0 && (
                <button onClick={handlePrevPhase} disabled={isTyping} className="w-full flex items-center justify-center gap-2 px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-700 text-gray-700 dark:text-gray-300">
                  <ChevronRight className="h-4 w-4 rotate-180" /> 返回上一阶段
                </button>
              )}
              {currentPhaseIndex < PHASES.length - 1 && (
                <button onClick={handleNextPhase} disabled={isTyping} className="w-full flex items-center justify-center gap-2 px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 disabled:opacity-50">
                  <ChevronRight className="h-4 w-4" /> 进入下一阶段
                </button>
              )}
            </div>
            {!inputMessage.trim() && !isCurrentPhaseCompleted && !currentPhase?.allowEmptyExecute && (
              <div className="mt-3 px-3 py-2 bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-700 rounded-lg">
                <p className="text-xs text-amber-700 dark:text-amber-400">请在上方输入框中输入内容，然后点击「执行」</p>
              </div>
            )}
          </div>

          {currentPhase?.id === 'chapter_writing' && (
            <div className="bg-white dark:bg-gray-800 rounded-xl p-4 shadow-sm space-y-3">
              <h3 className="text-sm font-semibold text-gray-700 dark:text-gray-300 flex items-center gap-2"><BookMarked className="h-4 w-4 text-indigo-500" /> 章节写作参数</h3>
              <div>
                <label className="block text-xs text-gray-500 mb-1">章节号</label>
                <input type="number" min="1" value={chapterNumber} onChange={(e) => setChapterNumber(parseInt(e.target.value) || 1)}
                  className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white text-sm" />
                <p className="text-xs text-gray-400 mt-1">已完成：第 {(progress as any)?.completed_chapters || 0} 章</p>
              </div>
              <div>
                <label className="block text-xs text-gray-500 mb-1">文风</label>
                <select value={writingStyle} onChange={(e) => setWritingStyle(e.target.value)}
                  className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white text-sm">
                  {WRITING_STYLE_OPTIONS.map(opt => <option key={opt.value} value={opt.value}>{opt.label}</option>)}
                </select>
              </div>
              <div>
                <label className="block text-xs text-gray-500 mb-1">环境描写</label>
                <select value={envLevel} onChange={(e) => setEnvLevel(e.target.value)}
                  className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white text-sm">
                  {ENV_LEVEL_OPTIONS.map(opt => <option key={opt.value} value={opt.value}>{opt.label}</option>)}
                </select>
              </div>
              <div>
                <label className="block text-xs text-gray-500 mb-1">对话占比: {Math.round(dialogueRatio * 100)}%</label>
                <select value={dialogueRatio} onChange={(e) => setDialogueRatio(parseFloat(e.target.value))}
                  className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white text-sm">
                  {DIALOGUE_RATIO_OPTIONS.map(opt => <option key={opt.value} value={opt.value}>{opt.label}</option>)}
                </select>
              </div>
              <div>
                <label className="block text-xs text-gray-500 mb-1">注意事项（可选）</label>
                <textarea value={chapterNotes} onChange={(e) => setChapterNotes(e.target.value)} placeholder="例如：需要突出主角的成长变化..."
                  rows={3} className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white text-sm resize-none" />
              </div>
              <button onClick={handleWriteChapter} disabled={isTyping || !chapterNumber}
                className="w-full flex items-center justify-center gap-2 px-4 py-2.5 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 disabled:opacity-50">
                {isTyping ? <Loader2 className="h-5 w-5 animate-spin" /> : <BookMarked className="h-5 w-5" />}
                {isTyping ? '撰写中...' : `撰写第${chapterNumber}章`}
              </button>
            </div>
          )}

          {currentPhase?.id !== 'chapter_writing' && (
            <div className="bg-white dark:bg-gray-800 rounded-xl p-4 shadow-sm">
              <h3 className="text-sm font-semibold text-gray-700 dark:text-gray-300 mb-3">创作进度</h3>
              <div className="space-y-2">
                <div className="flex justify-between text-sm"><span className="text-gray-500">已完成阶段</span><span className="font-medium">{completedPhases.length} / {PHASES.length}</span></div>
                <div className="flex justify-between text-sm"><span className="text-gray-500">已完成章节</span><span className="font-medium">{(progress as any)?.completed_chapters || 0} 章</span></div>
              </div>
              {completedPhases.length > 0 && (
                <div className="mt-3 pt-3 border-t border-gray-200 dark:border-gray-700">
                  <p className="text-xs text-gray-500 mb-2">已完成:</p>
                  <div className="flex flex-wrap gap-1">
                    {completedPhases.map(phaseId => { const phase = PHASES.find(p => p.id === phaseId); return phase ? (
                      <span key={phaseId} className="text-xs px-2 py-0.5 bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-400 rounded-full">{phase.name}</span>
                    ) : null })}
                  </div>
                </div>
              )}
            </div>
          )}

          {/* 阶段成果展示 - 显示所有阶段而不仅是已完成的 */}
          <div className="bg-white dark:bg-gray-800 rounded-xl p-4 shadow-sm">
            <h3 className="text-sm font-semibold text-gray-700 dark:text-gray-300 mb-3 flex items-center gap-2">
              <CheckCircle className="h-4 w-4 text-green-500" /> 阶段成果
            </h3>
            <div className="space-y-2">
              {PHASES.filter(p => p.id !== 'chapter_writing').map(phase => (
                <PhaseResultViewer
                  key={phase.id}
                  phaseId={phase.id}
                  phaseName={phase.name}
                  novelId={id}
                  isCompleted={completedPhases.includes(phase.id)}
                />
              ))}
            </div>
          </div>
        </div>

        <div className="flex-1 flex flex-col bg-gray-50 dark:bg-gray-900">
          <div className="flex-1 overflow-y-auto p-4 space-y-4">
            {chatMessages.length === 0 ? (
              <div className="flex flex-col items-center justify-center h-full text-center">
                <MessageSquare className="h-16 w-16 text-gray-300 dark:text-gray-600 mb-4" />
                <h3 className="text-lg font-medium text-gray-900 dark:text-white mb-2">开始{currentPhase?.name}</h3>
                <p className="text-gray-500 dark:text-gray-400 max-w-md mb-4">{currentPhase?.description}</p>
                <p className="text-sm text-gray-400">
                  {currentPhase?.id === 'chapter_writing' ? '使用左侧面板设置章节参数后，点击「撰写第X章」' : `点击左侧「执行${currentPhase?.name}」按钮开始，或在下方输入您的想法`}
                </p>
              </div>
            ) : chatMessages.map((msg, index) => (
              <div key={index} className={`flex ${msg.role === 'user' ? 'justify-end' : msg.role === 'system' ? 'justify-center' : 'justify-start'}`}>
                {msg.role === 'system' ? (
                  <div className="px-4 py-2 bg-amber-100 dark:bg-amber-900/30 text-amber-700 dark:text-amber-400 rounded-lg text-sm">{msg.content}</div>
                ) : (
                  <div className={`max-w-[80%] rounded-2xl px-4 py-3 ${msg.role === 'user' ? 'bg-primary-600 text-white' : 'bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700'}`}>
                    {msg.phase && msg.phase !== currentPhase?.id && <div className="text-xs text-gray-400 mb-1">{PHASES.find(p => p.id === msg.phase)?.name}</div>}
                    <p className="text-sm whitespace-pre-wrap">{msg.content}</p>
                    <p className={`text-xs mt-1 ${msg.role === 'user' ? 'text-primary-200' : 'text-gray-400'}`}>{msg.timestamp.toLocaleTimeString()}</p>
                  </div>
                )}
              </div>
            ))}
            {isTyping && (
              <div className="flex justify-start"><div className="max-w-[80%] rounded-2xl px-4 py-3 bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700"><div className="flex items-center gap-2"><Loader2 className="h-4 w-4 animate-spin text-primary-500" /><span className="text-sm text-gray-500">AI正在思考...</span></div></div></div>
            )}
            <div ref={messagesEndRef} />
          </div>
          <div className="p-4 bg-white dark:bg-gray-800 border-t border-gray-200 dark:border-gray-700">
            <div className="flex gap-2">
              <input type="text" value={inputMessage} onChange={(e) => setInputMessage(e.target.value)}
                onKeyDown={(e) => { if (e.key === 'Enter' && !isTyping) handleSendMessage() }}
                placeholder={currentPhase?.id === 'chapter_writing' ? '章节写作请使用左侧面板' : (currentPhase?.id === 'demand_analysis' ? '描述您想要创作的小说类型、风格、主题等...' : '输入消息...')}
                disabled={isTyping}
                className="flex-1 px-4 py-2.5 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white focus:ring-2 focus:ring-primary-500 disabled:opacity-50" />
              <button onClick={handleSendMessage} disabled={!inputMessage.trim() || isTyping}
                className="px-6 py-2.5 bg-primary-600 text-white rounded-lg hover:bg-primary-700 disabled:opacity-50 flex items-center gap-2">
                {isTyping ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}发送
              </button>
            </div>
            <div className="flex items-center justify-between mt-2">
              <p className="text-xs text-gray-400">{currentPhase?.id === 'chapter_writing' ? '提示: 建议使用左侧面板的「撰写第X章」按钮' : '提示: 发送消息将结合您的输入执行当前阶段'}</p>
              {chatMessages.length > 0 && (
                <button onClick={() => { if (confirm('确定要清空当前聊天记录吗？')) { setChatMessages([]); localStorage.removeItem(`workflow_chat_${id}`) } }}
                  className="text-xs text-red-500 hover:text-red-600">清空记录</button>
              )}
            </div>
          </div>
        </div>

        {showProgressPanel ? (
          <div className="w-96 border-l border-gray-200 dark:border-gray-700 bg-gray-900 text-gray-100 overflow-y-auto">
            <div className="p-4">
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-lg font-semibold flex items-center gap-2"><Terminal className="h-5 w-5" /> 执行日志</h3>
                {isTyping && <span className="text-xs bg-yellow-600 px-2 py-1 rounded flex items-center gap-1"><Loader2 className="h-3 w-3 animate-spin" />执行中</span>}
              </div>
              {currentTaskId && (
                <div className="mb-4 p-3 bg-gray-800 rounded-lg"><div className="text-xs text-gray-400 mb-1">任务ID</div><div className="text-sm font-mono truncate">{currentTaskId}</div></div>
              )}
              {taskProgress?.current_step && taskProgress.steps[taskProgress.current_step] && (
                <div className="mb-4">
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-sm font-medium">{taskProgress.steps[taskProgress.current_step].name}</span>
                    <span className="text-xs text-gray-400">{taskProgress.steps[taskProgress.current_step].progress}</span>
                  </div>
                  <div className="h-2 bg-gray-700 rounded-full overflow-hidden"><div className="h-full bg-primary-500" style={{ width: `${taskProgress.steps[taskProgress.current_step].progress_percent}%` }} /></div>
                </div>
              )}
              <div className="space-y-2">
                {currentStepLogs.length === 0 ? (
                  <div className="text-center text-gray-500 py-8"><Clock className="h-8 w-8 mx-auto mb-2 opacity-50" /><p className="text-sm">暂无执行日志，点击「执行」按钮开始</p></div>
                ) : currentStepLogs.map((log, index) => (
                  <div key={index} className={`p-3 rounded-lg text-sm ${log.level === 'error' ? 'bg-red-900/30 border border-red-700' : log.level === 'success' ? 'bg-green-900/30 border border-green-700' : 'bg-gray-800'}`}>
                      <span className={`text-xs px-1.5 py-0.5 rounded ${log.level === 'error' ? 'bg-red-700' : log.level === 'success' ? 'bg-green-700' : 'bg-gray-600'}`}>{log.level}</span>
                      <span className={`text-xs text-gray-400`}>{new Date(log.timestamp).toLocaleTimeString()}</span>
                    <p className={`mt-1 text-gray-200`}>{log.message}</p>
                  </div>
                ))}
              </div>
              {taskProgress?.current_step && taskProgress.steps[taskProgress.current_step]?.error && (
                <div className={`mt-4 p-3 bg-red-900/30 border border-red-700 rounded-lg`}>
                  <div className={`text-sm font-medium text-red-400 mb-1`}>错误</div>
                  <p className={`text-sm text-red-200`}>{taskProgress.steps[taskProgress.current_step].error}</p>
                </div>
              )}
            </div>
          </div>
        ) : (
          <div className={`w-96 border-l border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 overflow-y-auto`}>
            <div className={`p-4`}>
              <h3 className={`text-lg font-semibold text-gray-900 dark:text-white mb-4`}>已完成章节</h3>
              {(chapters as any)?.items && ((chapters as any).items as any[]).length > 0 ? (
                <div className={`space-y-2`}>
                  {((chapters as any).items as any[]).map((chapter: any) => (
                    <div key={chapter.id} className={`p-3 bg-gray-50 dark:bg-gray-700 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-600 transition-colors`}>
                      <div className={`font-medium text-gray-900 dark:text-white`}>第{chapter.chapter_number}章 {chapter.title}</div>
                      <div className={`text-xs text-gray-500 mt-1`}>{chapter.word_count || 0} 字</div>
                    </div>
                  ))}
                </div>
              ) : (
                <div className={`text-center text-gray-500 dark:text-gray-400 py-8`}>
                  <BookOpen className={`h-12 w-12 mx-auto mb-3 opacity-50`} />
                  <p>暂无章节</p>
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
