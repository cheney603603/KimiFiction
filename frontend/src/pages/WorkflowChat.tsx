import { useState, useEffect, useRef } from 'react'
import { useParams, Link } from 'react-router-dom'
import { useQuery, useMutation } from '@tanstack/react-query'
import { Send, Bot, User, Loader2, Sparkles, CheckCircle, ArrowLeft } from 'lucide-react'
import { workflowApi } from '../services/api'
import type { WorkflowState, AgentMessage } from '../types'

export function WorkflowChat() {
  const { novelId } = useParams<{ novelId: string }>()
  const id = parseInt(novelId || '0')
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const [input, setInput] = useState('')

  const { data: workflowState, refetch, error: workflowError, isError } = useQuery({
    queryKey: ['workflow', id],
    queryFn: () => workflowApi.getState(id),
    enabled: !!id,
    refetchInterval: workflowError ? false : 5000, // 404时不刷新
    retry: false,
  })

  // 检查是否是404错误（工作流未初始化）
  const isNotFound = isError && (workflowError as any)?.response?.status === 404

  const submitMutation = useMutation({
    mutationFn: (message: string) => workflowApi.submitInput(id, message),
    onSuccess: () => {
      refetch()
      setInput('')
    },
  })

  const generateCharactersMutation = useMutation({
    mutationFn: () => workflowApi.generateCharacters(id),
    onSuccess: () => refetch(),
  })

  const generateOutlineMutation = useMutation({
    mutationFn: () => workflowApi.generateOutline(id),
    onSuccess: () => refetch(),
  })

  const startWritingMutation = useMutation({
    mutationFn: () => workflowApi.startWriting(id),
    onSuccess: () => refetch(),
  })

  const startWorkflowMutation = useMutation({
    mutationFn: (data: { title: string; initial_idea?: string }) =>
      workflowApi.start({ title: data.title, initial_idea: data.initial_idea }),
    onSuccess: () => refetch(),
  })

  // 自动滚动到底部
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [workflowState?.messages])

  const handleSubmit = () => {
    if (input.trim() && !submitMutation.isPending) {
      submitMutation.mutate(input.trim())
    }
  }

  const state = workflowState as WorkflowState
  const messages = state?.messages || []

  // 获取当前阶段提示
  const getStageHint = () => {
    const stageHints: Record<string, string> = {
      awaiting_genre: '正在分析小说类型...',
      discussing_plot: '正在讨论剧情走向...',
      designing_chars: '正在设计角色...',
      generating_outline: '正在生成大纲...',
      writing_chapter: '正在撰写章节...',
      reviewing: '等待审核...',
      paused: '已暂停',
    }
    return stageHints[state?.current_state] || '创作中...'
  }

  // 如果工作流未初始化，显示初始化界面
  if (isNotFound) {
    return (
      <div className="max-w-2xl mx-auto">
        {/* 返回按钮 */}
        <Link
          to={`/novel/${id}`}
          className="inline-flex items-center gap-2 text-gray-600 dark:text-gray-400 hover:text-primary-600 dark:hover:text-primary-400 transition-colors mb-6"
        >
          <ArrowLeft className="h-5 w-5" />
          返回小说详情
        </Link>

        <div className="bg-white dark:bg-gray-800 rounded-xl shadow-sm border border-gray-200 dark:border-gray-700 p-8 text-center">
          <Bot className="h-16 w-16 text-primary-600 mx-auto mb-6" />
          <h1 className="text-2xl font-bold text-gray-900 dark:text-white mb-4">
            开始创作您的小说
          </h1>
          <p className="text-gray-500 dark:text-gray-400 mb-8 max-w-md mx-auto">
            工作流尚未初始化。点击下方按钮开始与 AI 助手一起创作小说。
          </p>
          <button
            onClick={() => startWorkflowMutation.mutate({ title: `小说${id}`, initial_idea: '' })}
            disabled={startWorkflowMutation.isPending}
            className="px-6 py-3 bg-primary-600 text-white rounded-lg hover:bg-primary-700 disabled:opacity-50 flex items-center gap-2 mx-auto"
          >
            {startWorkflowMutation.isPending ? (
              <Loader2 className="h-5 w-5 animate-spin" />
            ) : (
              <Sparkles className="h-5 w-5" />
            )}
            开始创作
          </button>
        </div>
      </div>
    )
  }

  return (
    <div className="h-[calc(100vh-8rem)] flex flex-col">
      {/* 返回按钮 */}
      <Link
        to={`/novel/${id}`}
        className="inline-flex items-center gap-2 text-gray-600 dark:text-gray-400 hover:text-primary-600 dark:hover:text-primary-400 transition-colors mb-4"
      >
        <ArrowLeft className="h-5 w-5" />
        返回小说详情
      </Link>
      {/* 顶部状态栏 */}
      <div className="bg-white dark:bg-gray-800 rounded-t-xl p-4 border-b border-gray-200 dark:border-gray-700">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-lg font-semibold text-gray-900 dark:text-white">
              AI创作助手
            </h1>
            <p className="text-sm text-gray-500 dark:text-gray-400">
              {getStageHint()}
            </p>
          </div>
          <div className="flex items-center gap-2">
            {/* 进度指示器 */}
            <div className="flex items-center gap-1">
              {['genre_confirmed', 'plot_discussed', 'characters_designed', 'outline_generated', 'writing_started'].map((step, i) => (
                <div
                  key={step}
                  className={`w-2 h-2 rounded-full ${
                    state?.progress?.[step as keyof typeof state.progress]
                      ? 'bg-green-500'
                      : 'bg-gray-300 dark:bg-gray-600'
                  }`}
                />
              ))}
            </div>
          </div>
        </div>
      </div>

      {/* 消息区域 */}
      <div className="flex-1 overflow-y-auto bg-gray-50 dark:bg-gray-900 p-4 space-y-4">
        {messages.length === 0 ? (
          <div className="text-center py-12">
            <Bot className="h-12 w-12 text-gray-400 mx-auto mb-4" />
            <h3 className="text-lg font-medium text-gray-900 dark:text-white mb-2">
              开始创作您的小说
            </h3>
            <p className="text-gray-500 dark:text-gray-400 max-w-md mx-auto">
              告诉我您想写什么类型的小说，我会帮您分析、设计角色、生成大纲，并自动撰写章节。
            </p>
          </div>
        ) : (
          messages.map((msg: AgentMessage, index: number) => (
            <div
              key={index}
              className={`flex gap-3 ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
            >
              {msg.role !== 'user' && (
                <div className="w-8 h-8 rounded-full bg-primary-100 dark:bg-primary-900 flex items-center justify-center shrink-0">
                  {msg.role === 'agent' ? (
                    <Bot className="h-5 w-5 text-primary-600" />
                  ) : (
                    <Sparkles className="h-5 w-5 text-primary-600" />
                  )}
                </div>
              )}
              
              <div
                className={`max-w-[70%] rounded-2xl px-4 py-2 ${
                  msg.role === 'user'
                    ? 'bg-primary-600 text-white'
                    : msg.message_type === 'suggestion'
                    ? 'bg-green-50 dark:bg-green-900/20 border border-green-200 dark:border-green-800'
                    : 'bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700'
                }`}
              >
                <p className={`text-sm ${msg.role === 'user' ? 'text-white' : 'text-gray-800 dark:text-gray-200'}`}>
                  {msg.content}
                </p>
                {msg.message_type === 'suggestion' && (
                  <div className="mt-2 flex items-center gap-1 text-xs text-green-600 dark:text-green-400">
                    <CheckCircle className="h-3 w-3" />
                    建议
                  </div>
                )}
              </div>

              {msg.role === 'user' && (
                <div className="w-8 h-8 rounded-full bg-gray-200 dark:bg-gray-700 flex items-center justify-center shrink-0">
                  <User className="h-5 w-5 text-gray-600 dark:text-gray-400" />
                </div>
              )}
            </div>
          ))
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* 快捷操作按钮 */}
      {state?.suggestions && state.suggestions.length > 0 && (
        <div className="bg-white dark:bg-gray-800 border-t border-gray-200 dark:border-gray-700 p-2">
          <div className="flex gap-2 overflow-x-auto">
            {state.suggestions.map((suggestion, i) => (
              <button
                key={i}
                onClick={() => submitMutation.mutate(suggestion)}
                className="px-3 py-1.5 text-sm bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-300 rounded-full whitespace-nowrap hover:bg-gray-200 dark:hover:bg-gray-600"
              >
                {suggestion}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* 特殊操作按钮 */}
      {state?.current_state === 'designing_chars' && (
        <div className="bg-white dark:bg-gray-800 border-t border-gray-200 dark:border-gray-700 p-3">
          <button
            onClick={() => generateCharactersMutation.mutate()}
            disabled={generateCharactersMutation.isPending}
            className="w-full py-2 bg-purple-600 text-white rounded-lg hover:bg-purple-700 disabled:opacity-50 flex items-center justify-center gap-2"
          >
            {generateCharactersMutation.isPending ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Sparkles className="h-4 w-4" />
            )}
            生成角色设计
          </button>
        </div>
      )}

      {state?.current_state === 'generating_outline' && (
        <div className="bg-white dark:bg-gray-800 border-t border-gray-200 dark:border-gray-700 p-3">
          <button
            onClick={() => generateOutlineMutation.mutate()}
            disabled={generateOutlineMutation.isPending}
            className="w-full py-2 bg-orange-600 text-white rounded-lg hover:bg-orange-700 disabled:opacity-50 flex items-center justify-center gap-2"
          >
            {generateOutlineMutation.isPending ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Sparkles className="h-4 w-4" />
            )}
            生成剧情大纲
          </button>
        </div>
      )}

      {state?.current_state === 'writing_chapter' && !state?.progress?.writing_started && (
        <div className="bg-white dark:bg-gray-800 border-t border-gray-200 dark:border-gray-700 p-3">
          <button
            onClick={() => startWritingMutation.mutate()}
            disabled={startWritingMutation.isPending}
            className="w-full py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 disabled:opacity-50 flex items-center justify-center gap-2"
          >
            {startWritingMutation.isPending ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Sparkles className="h-4 w-4" />
            )}
            开始自动撰写
          </button>
        </div>
      )}

      {/* 输入区域 */}
      <div className="bg-white dark:bg-gray-800 rounded-b-xl p-4 border-t border-gray-200 dark:border-gray-700">
        <div className="flex gap-2">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleSubmit()}
            placeholder={state?.waiting_for_user ? "输入您的想法..." : "等待AI响应..."}
            disabled={!state?.waiting_for_user || submitMutation.isPending}
            className="flex-1 px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white focus:ring-2 focus:ring-primary-500 focus:border-transparent disabled:opacity-50"
          />
          <button
            onClick={handleSubmit}
            disabled={!input.trim() || !state?.waiting_for_user || submitMutation.isPending}
            className="px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700 disabled:opacity-50 flex items-center gap-2"
          >
            {submitMutation.isPending ? (
              <Loader2 className="h-5 w-5 animate-spin" />
            ) : (
              <Send className="h-5 w-5" />
            )}
          </button>
        </div>
      </div>
    </div>
  )
}
