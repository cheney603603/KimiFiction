import { useEffect, useRef, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { useMutation, useQuery } from '@tanstack/react-query'
import { ArrowLeft, Bot, Loader2, Send, Sparkles, User } from 'lucide-react'

import { workflowApi } from '../services/api'
import type { AgentMessage, WorkflowState } from '../types'

/**
 * WorkflowChat - 轻量级工作流对话页面
 *
 * 设计原则：
 * 1. 只保留核心聊天能力，不与 WorkflowPage 功能重叠
 * 2. 修复自引用查询问题（refetchInterval 不依赖 query 内部状态）
 * 3. 状态管理极简，只读工作流状态，不写复杂逻辑
 */

export function WorkflowChat() {
  const { novelId } = useParams<{ novelId: string }>()
  const id = parseInt(novelId || '0')
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const [input, setInput] = useState('')

  // ── 工作流状态查询（修复自引用问题） ──
  // 问题：原代码 refetchInterval 使用了 query.state.error，这是自引用
  // 修复：使用独立的 isError 状态控制轮询
  const {
    data: workflowState,
    refetch,
    isError,
    isLoading,
  } = useQuery<WorkflowState>({
    queryKey: ['workflow', id],
    queryFn: () => workflowApi.getState(id),
    enabled: !!id,
    // 修复：refetchInterval 使用函数参数中的 state，而不是闭包变量
    refetchInterval: (query) => {
      // 有错误时停止轮询，避免无限报错
      if (query.state.error) return false
      return 5000
    },
    retry: 1, // 只重试1次，避免404时疯狂重试
    staleTime: 3000, // 3秒内不重复请求
  })

  // 404 表示工作流未初始化
  const isNotFound = isError

  // ── 消息提交 ──
  const submitMutation = useMutation({
    mutationFn: (message: string) => workflowApi.submitInput(id, message),
    onSuccess: () => {
      setInput('')
      refetch()
    },
  })

  // ── 初始化工作流 ──
  const startWorkflowMutation = useMutation({
    mutationFn: (data: { title: string; initial_idea?: string }) =>
      workflowApi.start({ title: data.title, initial_idea: data.initial_idea }),
    onSuccess: () => refetch(),
  })

  // ── 自动滚动 ──
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [workflowState?.messages])

  const messages: AgentMessage[] = workflowState?.messages || []

  const handleSubmit = () => {
    if (!input.trim() || submitMutation.isPending) return
    submitMutation.mutate(input.trim())
  }

  // ── 阶段提示文字 ──
  const getStageHint = () => {
    const stageHints: Record<string, string> = {
      awaiting_genre: '等待选择小说类型...',
      discussing_plot: '正在讨论剧情...',
      designing_chars: '正在设计角色...',
      generating_outline: '正在生成大纲...',
      writing_chapter: '正在撰写章节...',
      reviewing: '正在审阅...',
      paused: '已暂停',
      completed: '已完成',
    }
    return stageHints[workflowState?.current_state || ''] || '创作中...'
  }

  // ── 未初始化状态 ──
  if (isNotFound && !workflowState) {
    return (
      <div className="max-w-2xl mx-auto p-6">
        <Link
          to={`/novel/${id}`}
          className="inline-flex items-center gap-2 text-gray-400 hover:text-indigo-400 transition-colors mb-6"
        >
          <ArrowLeft className="h-4 w-4" />
          返回小说详情
        </Link>

        <div className="bg-gray-900 rounded-xl border border-gray-800 p-8 text-center">
          <Sparkles className="h-12 w-12 text-indigo-500 mx-auto mb-4" />
          <h1 className="text-xl font-bold text-white mb-3">初始化工作流</h1>
          <p className="text-gray-400 mb-6">
            当前小说还没有创建工作流对话状态，初始化后即可开始 AI 辅助创作。
          </p>
          <button
            onClick={() =>
              startWorkflowMutation.mutate({
                title: `小说${id}`,
                initial_idea: '',
              })
            }
            disabled={startWorkflowMutation.isPending}
            className="inline-flex items-center gap-2 px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 disabled:opacity-50"
          >
            {startWorkflowMutation.isPending ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Sparkles className="h-4 w-4" />
            )}
            初始化
          </button>
        </div>
      </div>
    )
  }

  // ── 主界面 ──
  return (
    <div className="max-w-4xl mx-auto p-6">
      {/* 头部 */}
      <Link
        to={`/novel/${id}`}
        className="inline-flex items-center gap-2 text-gray-400 hover:text-indigo-400 transition-colors mb-6"
      >
        <ArrowLeft className="h-4 w-4" />
        返回小说详情
      </Link>

      <div className="bg-gray-900 rounded-xl border border-gray-800 overflow-hidden">
        {/* 标题栏 */}
        <div className="px-6 py-4 border-b border-gray-800 flex items-center justify-between">
          <div>
            <h1 className="text-xl font-bold text-white">工作流对话</h1>
            <p className="text-sm text-gray-500">
              {isLoading ? '加载中...' : getStageHint()}
            </p>
          </div>
          {workflowState?.can_proceed && (
            <span className="inline-flex items-center gap-1 px-3 py-1 text-xs bg-green-900/30 text-green-400 rounded-full">
              可继续
            </span>
          )}
        </div>

        {/* 消息区 */}
        <div className="p-4 h-[60vh] overflow-y-auto space-y-4 bg-gray-950">
          {messages.length === 0 ? (
            <div className="text-center text-gray-500 py-12">
              <Bot className="h-10 w-10 mx-auto mb-3 opacity-50" />
              <p>还没有消息，开始你的创作对话吧。</p>
              <p className="text-xs text-gray-600 mt-2">
                提示：如需完整阶段控制，请使用
                <Link
                  to={`/novel/${id}/workflow`}
                  className="text-indigo-400 hover:text-indigo-300 ml-1"
                >
                  新版工作流页面
                </Link>
              </p>
            </div>
          ) : (
            messages.map((message, index) => (
              <div
                key={`${message.timestamp}-${index}`}
                className={`flex ${
                  message.role === 'user' ? 'justify-end' : 'justify-start'
                }`}
              >
                <div
                  className={`max-w-[80%] rounded-2xl px-4 py-3 ${
                    message.role === 'user'
                      ? 'bg-indigo-600 text-white'
                      : 'bg-gray-800 border border-gray-700'
                  }`}
                >
                  <div className="flex items-center gap-2 mb-1">
                    {message.role === 'user' ? (
                      <User className="h-4 w-4" />
                    ) : (
                      <Bot className="h-4 w-4 text-indigo-400" />
                    )}
                    <span className="text-xs opacity-75">
                      {message.role === 'user' ? '你' : 'Agent'}
                    </span>
                  </div>
                  <p className="text-sm whitespace-pre-wrap">{message.content}</p>
                </div>
              </div>
            ))
          )}
          <div ref={messagesEndRef} />
        </div>

        {/* 输入区 */}
        <div className="px-6 py-4 border-t border-gray-800 bg-gray-900">
          <div className="flex gap-2">
            <input
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                  e.preventDefault()
                  handleSubmit()
                }
              }}
              placeholder="输入你的想法..."
              className="flex-1 px-4 py-2.5 border border-gray-700 rounded-lg bg-gray-800 text-gray-200 focus:outline-none focus:border-indigo-500"
            />
            <button
              onClick={handleSubmit}
              disabled={!input.trim() || submitMutation.isPending}
              className="px-4 py-2.5 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 disabled:opacity-50"
            >
              {submitMutation.isPending ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Send className="h-4 w-4" />
              )}
            </button>
          </div>

          {/* 底部提示 */}
          <div className="mt-3 flex items-center justify-between text-xs text-gray-500">
            <span>按 Enter 发送，Shift+Enter 换行</span>
            <Link
              to={`/novel/${id}/workflow`}
              className="text-indigo-400 hover:text-indigo-300"
            >
              切换到完整工作流 →
            </Link>
          </div>
        </div>
      </div>
    </div>
  )
}
