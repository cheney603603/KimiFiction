import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Plus, BookOpen, ChevronRight, Loader2 } from 'lucide-react'
import { Link } from 'react-router-dom'
import { novelApi } from '../services/api'
import type { Novel } from '../types'

export function Dashboard() {
  const queryClient = useQueryClient()
  const [isCreating, setIsCreating] = useState(false)
  const [newNovelTitle, setNewNovelTitle] = useState('')

  const { data: novelsData, isLoading, error } = useQuery({
    queryKey: ['novels'],
    queryFn: () => novelApi.list(),
    retry: false,
  })

  const createMutation = useMutation({
    mutationFn: (title: string) => novelApi.create({ title }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['novels'] })
      setIsCreating(false)
      setNewNovelTitle('')
    },
  })

  const handleCreate = () => {
    if (newNovelTitle.trim()) {
      createMutation.mutate(newNovelTitle.trim())
    }
  }

  const novels = novelsData?.items || []

  // 加载状态
  if (isLoading) {
    return (
      <div className="flex justify-center items-center h-64">
        <Loader2 className="h-8 w-8 animate-spin text-primary-600" />
      </div>
    )
  }

  // 错误状态
  if (error) {
    return (
      <div className="text-center py-16 bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700">
        <p className="text-red-500 dark:text-red-400 mb-4">加载失败，请检查网络或后端服务</p>
        <button
          onClick={() => window.location.reload()}
          className="px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700"
        >
          重新加载
        </button>
      </div>
    )
  }

  const getStatusText = (status: string) => {
    const statusMap: Record<string, string> = {
      planning: '规划中',
      writing: '撰写中',
      paused: '暂停',
      completed: '已完成',
    }
    return statusMap[status] || status
  }

  const getStatusColor = (status: string) => {
    const colorMap: Record<string, string> = {
      planning: 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-300',
      writing: 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-300',
      paused: 'bg-gray-100 text-gray-800 dark:bg-gray-700 dark:text-gray-300',
      completed: 'bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-300',
    }
    return colorMap[status] || 'bg-gray-100 text-gray-800'
  }

  return (
    <div className="space-y-6">
      {/* 标题栏 */}
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 dark:text-white">
            工作台
          </h1>
          <p className="text-gray-500 dark:text-gray-400 mt-1">
            管理您的小说项目
          </p>
        </div>
        
        {!isCreating ? (
          <button
            onClick={() => setIsCreating(true)}
            className="flex items-center gap-2 px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700 transition-colors"
          >
            <Plus className="h-5 w-5" />
            新建小说
          </button>
        ) : (
          <div className="flex items-center gap-2">
            <input
              type="text"
              value={newNovelTitle}
              onChange={(e) => setNewNovelTitle(e.target.value)}
              placeholder="输入小说标题"
              className="px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-800 text-gray-900 dark:text-white focus:ring-2 focus:ring-primary-500 focus:border-transparent"
              onKeyDown={(e) => e.key === 'Enter' && handleCreate()}
              autoFocus
            />
            <button
              onClick={handleCreate}
              disabled={createMutation.isPending}
              className="px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700 disabled:opacity-50"
            >
              {createMutation.isPending ? (
                <Loader2 className="h-5 w-5 animate-spin" />
              ) : (
                '创建'
              )}
            </button>
            <button
              onClick={() => {
                setIsCreating(false)
                setNewNovelTitle('')
              }}
              className="px-4 py-2 text-gray-600 dark:text-gray-400 hover:text-gray-800 dark:hover:text-gray-200"
            >
              取消
            </button>
          </div>
        )}
      </div>

      {/* 小说列表 */}
      {isLoading ? (
        <div className="flex justify-center py-12">
          <Loader2 className="h-8 w-8 animate-spin text-primary-600" />
        </div>
      ) : novels.length === 0 ? (
        <div className="text-center py-16 bg-white dark:bg-gray-800 rounded-xl border border-dashed border-gray-300 dark:border-gray-600">
          <BookOpen className="h-12 w-12 text-gray-400 mx-auto mb-4" />
          <h3 className="text-lg font-medium text-gray-900 dark:text-white mb-2">
            还没有小说项目
          </h3>
          <p className="text-gray-500 dark:text-gray-400">
            点击上方按钮创建您的第一部小说
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {novels.map((novel: Novel) => (
            <Link
              key={novel.id}
              to={`/novel/${novel.id}`}
              className="group bg-white dark:bg-gray-800 rounded-xl shadow-sm border border-gray-200 dark:border-gray-700 p-6 hover:shadow-md transition-all"
            >
              <div className="flex justify-between items-start mb-4">
                <div className="flex-1 min-w-0">
                  <h3 className="text-lg font-semibold text-gray-900 dark:text-white truncate group-hover:text-primary-600 transition-colors">
                    {novel.title}
                  </h3>
                  {novel.genre && (
                    <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
                      {novel.genre}
                    </p>
                  )}
                </div>
                <span className={`px-2 py-1 text-xs font-medium rounded-full ${getStatusColor(novel.status)}`}>
                  {getStatusText(novel.status)}
                </span>
              </div>

              {/* 进度条 */}
              <div className="mb-4">
                <div className="flex justify-between text-sm text-gray-600 dark:text-gray-400 mb-1">
                  <span>进度</span>
                  <span>{(novel.current_chapter || 0)} / {(novel.target_chapters || 100)} 章</span>
                </div>
                <div className="w-full bg-gray-200 dark:bg-gray-700 rounded-full h-2">
                  <div
                    className="bg-primary-600 h-2 rounded-full transition-all"
                    style={{
                      width: `${Math.min(((novel.current_chapter || 0) / (novel.target_chapters || 100)) * 100, 100)}%`
                    }}
                  />
                </div>
              </div>

              {/* 统计信息 */}
              <div className="flex items-center justify-between text-sm text-gray-500 dark:text-gray-400">
                <span>{(novel.total_words || 0).toLocaleString()} 字</span>
                <ChevronRight className="h-5 w-5 text-gray-400 group-hover:text-primary-600 transition-colors" />
              </div>
            </Link>
          ))}
        </div>
      )}
    </div>
  )
}
