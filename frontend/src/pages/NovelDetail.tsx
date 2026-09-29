import { useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import {
  BookOpen, Users, FileText, MessageSquare, ChevronRight, Download, X, FileDown,
  ArrowLeft, Sparkles, Network, History, Shield, MapPin, Package, Zap, Share2, BookMarked,
} from 'lucide-react'
import { novelApi, chapterApi, exportApi, worldApi } from '../services/api'
import { NovelNav } from '../components/NovelNav'

export function NovelDetail() {
  const { novelId } = useParams<{ novelId: string }>()
  const id = parseInt(novelId || '0')
  const [showExportModal, setShowExportModal] = useState(false)
  const [isExporting, setIsExporting] = useState(false)

  const { data: novel } = useQuery({
    queryKey: ['novel', id],
    queryFn: () => novelApi.get(id),
    enabled: !!id,
  })

  const { data: chaptersData } = useQuery({
    queryKey: ['chapters', id],
    queryFn: () => chapterApi.list(id, { limit: 5 }),
    enabled: !!id,
  })

  const { data: world } = useQuery({
    queryKey: ['world', id],
    queryFn: () => worldApi.get(id),
    enabled: !!id,
  })

  if (!novel) {
    return (
      <div className="flex justify-center items-center h-64">
        <div className="text-gray-500 dark:text-gray-400">加载中...</div>
      </div>
    )
  }

  const chapters = chaptersData?.items || []
  const c = world?.counts
  // 角色数：与「角色管理」页一致 —— 该页展示 characters 表中的角色，
  // 实体抽取出的角色只体现在图谱/知识库中，避免数字对不上。
  const roleCount = c?.characters_db ?? 0
  const overview = [
    { label: '角色', value: roleCount, icon: Users, color: 'bg-amber-500', href: `/novel/${id}/characters` },
    { label: '势力', value: c?.faction ?? 0, icon: Shield, color: 'bg-blue-500', href: `/novel/${id}/graph` },
    { label: '地点', value: c?.location ?? 0, icon: MapPin, color: 'bg-emerald-500', href: `/novel/${id}/map` },
    { label: '物品', value: c?.item ?? 0, icon: Package, color: 'bg-purple-500', href: `/novel/${id}/graph` },
    { label: '技能', value: c?.skill ?? 0, icon: Zap, color: 'bg-cyan-500', href: `/novel/${id}/graph` },
    { label: '关系', value: c?.relationships ?? 0, icon: Share2, color: 'bg-pink-500', href: `/novel/${id}/graph` },
    { label: '记忆', value: c?.memory_nodes ?? 0, icon: BookMarked, color: 'bg-rose-500', href: `/novel/${id}/knowledge` },
    { label: '大纲', value: c?.outlines ?? 0, icon: FileText, color: 'bg-orange-500', href: `/novel/${id}/outline` },
  ]

  const handleExport = async (format: string) => {
    setIsExporting(true)
    try {
      let blob
      let filename

      switch (format) {
        case 'txt':
          blob = await exportApi.exportTxt(id)
          filename = `${novel?.title || 'novel'}.txt`
          break
        case 'markdown':
          blob = await exportApi.exportMarkdown(id)
          filename = `${novel?.title || 'novel'}.md`
          break
        case 'json':
          blob = await exportApi.exportJson(id)
          filename = `${novel?.title || 'novel'}.json`
          break
        case 'characters':
          blob = await exportApi.exportCharacters(id)
          filename = `${novel?.title || 'novel'}_characters.md`
          break
        case 'outline':
          blob = await exportApi.exportOutline(id)
          filename = `${novel?.title || 'novel'}_outline.md`
          break
        default:
          setIsExporting(false)
          return
      }

      const url = window.URL.createObjectURL(blob)
      const link = document.createElement('a')
      link.href = url
      link.download = filename
      document.body.appendChild(link)
      link.click()
      document.body.removeChild(link)
      window.URL.revokeObjectURL(url)

      setShowExportModal(false)
    } catch (error) {
      console.error('导出失败:', error)
      alert('导出失败，请重试')
    } finally {
      setIsExporting(false)
    }
  }

  return (
    <div className="space-y-6">
      {/* 返回按钮 */}
      <Link
        to="/"
        className="inline-flex items-center gap-2 text-gray-600 dark:text-gray-400 hover:text-primary-600 dark:hover:text-primary-400 transition-colors"
      >
        <ArrowLeft className="h-5 w-5" />
        返回工作台
      </Link>

      {/* 标题 */}
      <div className="bg-white dark:bg-gray-800 rounded-xl p-6 shadow-sm border border-gray-200 dark:border-gray-700">
        <div className="flex justify-between items-start">
          <div>
            <h1 className="text-2xl font-bold text-gray-900 dark:text-white">
              {novel.title}
            </h1>
            {novel.genre && (
              <p className="text-gray-500 dark:text-gray-400 mt-1">
                {novel.genre}
              </p>
            )}
            <div className="flex gap-4 mt-4 text-sm text-gray-600 dark:text-gray-400">
              <span>{novel.total_chapters} 章</span>
              <span>{novel.total_words.toLocaleString()} 字</span>
              <span className="capitalize">{novel.status}</span>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <Link
              to={`/novel/${id}/workflow/new`}
              className="flex items-center gap-2 px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-500 transition-colors"
            >
              <Sparkles className="h-4 w-4" />
              AI 创作助手
            </Link>
            <button
              onClick={() => setShowExportModal(true)}
              className="flex items-center gap-2 px-4 py-2 text-gray-600 dark:text-gray-400 hover:text-primary-600 dark:hover:text-primary-400 border border-gray-300 dark:border-gray-600 rounded-lg hover:border-primary-600 transition-colors"
            >
              <Download className="h-5 w-5" />
              导出
            </button>
          </div>
        </div>

        {/* 小说内导航：在一个区域内切换所有创作工具 */}
        <div className="mt-5 pt-4 border-t border-gray-100 dark:border-gray-700">
          <NovelNav />
        </div>
      </div>

      {/* 世界观概况：点击直达对应视图 */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {overview.map(item => (
          <Link
            key={item.label}
            to={item.href}
            className="flex items-center gap-4 p-4 bg-white dark:bg-gray-800 rounded-xl shadow-sm border border-gray-200 dark:border-gray-700 hover:shadow-md transition-all group"
          >
            <div className={`${item.color} p-3 rounded-lg shrink-0`}>
              <item.icon className="h-5 w-5 text-white" />
            </div>
            <div className="min-w-0">
              <p className="text-2xl font-bold text-gray-900 dark:text-white leading-none">
                {item.value}
              </p>
              <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
                {item.label}
              </p>
            </div>
            <ChevronRight className="h-5 w-5 text-gray-400 ml-auto group-hover:text-gray-600 dark:group-hover:text-gray-300" />
          </Link>
        ))}
      </div>

      {/* 创作入口 */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {[
          { title: '继续创作', description: '单一章节撰写，快速生成内容', icon: MessageSquare, href: `/novel/${id}/write`, color: 'bg-blue-500' },
          { title: '阅读小说', description: `已生成 ${novel.total_chapters} 章`, icon: BookOpen, href: `/novel/${id}/read`, color: 'bg-green-500' },
          { title: '实体图谱', description: '角色与势力的关系网', icon: Network, href: `/novel/${id}/graph`, color: 'bg-indigo-500', badge: '新' },
          { title: '快照管理', description: '查看历史状态，可回滚', icon: History, href: `/novel/${id}/snapshots`, color: 'bg-red-500' },
        ].map(item => (
          <Link
            key={item.title}
            to={item.href}
            className="flex items-center gap-4 p-4 bg-white dark:bg-gray-800 rounded-xl shadow-sm border border-gray-200 dark:border-gray-700 hover:shadow-md transition-all group"
          >
            <div className={`${item.color} p-3 rounded-lg`}>
              <item.icon className="h-6 w-6 text-white" />
            </div>
            <div className="flex-1">
              <div className="flex items-center gap-2">
                <h3 className="font-semibold text-gray-900 dark:text-white">
                  {item.title}
                </h3>
                {item.badge && (
                  <span className="px-2 py-0.5 text-xs font-medium rounded-full bg-indigo-100 text-indigo-700 dark:bg-indigo-900/30 dark:text-indigo-400">
                    {item.badge}
                  </span>
                )}
              </div>
              <p className="text-sm text-gray-500 dark:text-gray-400">
                {item.description}
              </p>
            </div>
            <ChevronRight className="h-5 w-5 text-gray-400 group-hover:text-gray-600 dark:group-hover:text-gray-300" />
          </Link>
        ))}
      </div>

      {/* 最近章节 */}
      <div className="bg-white dark:bg-gray-800 rounded-xl shadow-sm border border-gray-200 dark:border-gray-700">
        <div className="p-4 border-b border-gray-200 dark:border-gray-700 flex justify-between items-center">
          <h2 className="font-semibold text-gray-900 dark:text-white">最近章节</h2>
          <Link
            to={`/novel/${id}/read`}
            className="text-sm text-primary-600 hover:text-primary-700"
          >
            查看全部
          </Link>
        </div>
        <div className="divide-y divide-gray-200 dark:divide-gray-700">
          {chapters.length === 0 ? (
            <p className="p-4 text-gray-500 dark:text-gray-400 text-center">
              还没有章节，开始创作吧！
            </p>
          ) : (
            chapters.map((chapter: any) => (
              <Link
                key={chapter.id}
                to={`/novel/${id}/read/${chapter.chapter_number}`}
                className="flex items-center justify-between p-4 hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors"
              >
                <div>
                  <p className="font-medium text-gray-900 dark:text-white">
                    第{chapter.chapter_number}章 {chapter.title}
                  </p>
                  <p className="text-sm text-gray-500 dark:text-gray-400">
                    {chapter.word_count} 字
                  </p>
                </div>
                <ChevronRight className="h-5 w-5 text-gray-400" />
              </Link>
            ))
          )}
        </div>
      </div>

      {/* 导出弹窗 */}
      {showExportModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-white dark:bg-gray-800 rounded-xl p-6 w-full max-w-md mx-4">
            <div className="flex justify-between items-center mb-6">
              <h2 className="text-xl font-bold text-gray-900 dark:text-white">
                导出小说
              </h2>
              <button
                onClick={() => setShowExportModal(false)}
                className="p-1 hover:bg-gray-100 dark:hover:bg-gray-700 rounded"
              >
                <X className="h-5 w-5 text-gray-500" />
              </button>
            </div>

            <div className="space-y-3">
              <button
                onClick={() => handleExport('txt')}
                disabled={isExporting}
                className="w-full flex items-center gap-3 p-4 bg-gray-50 dark:bg-gray-700 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-600 transition-colors text-left"
              >
                <FileDown className="h-5 w-5 text-gray-600 dark:text-gray-400" />
                <div>
                  <p className="font-medium text-gray-900 dark:text-white">导出为 TXT</p>
                  <p className="text-sm text-gray-500">纯文本格式，适合阅读</p>
                </div>
              </button>

              <button
                onClick={() => handleExport('markdown')}
                disabled={isExporting}
                className="w-full flex items-center gap-3 p-4 bg-gray-50 dark:bg-gray-700 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-600 transition-colors text-left"
              >
                <FileDown className="h-5 w-5 text-gray-600 dark:text-gray-400" />
                <div>
                  <p className="font-medium text-gray-900 dark:text-white">导出为 Markdown</p>
                  <p className="text-sm text-gray-500">Markdown格式，带目录结构</p>
                </div>
              </button>

              <button
                onClick={() => handleExport('json')}
                disabled={isExporting}
                className="w-full flex items-center gap-3 p-4 bg-gray-50 dark:bg-gray-700 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-600 transition-colors text-left"
              >
                <FileDown className="h-5 w-5 text-gray-600 dark:text-gray-400" />
                <div>
                  <p className="font-medium text-gray-900 dark:text-white">导出为 JSON</p>
                  <p className="text-sm text-gray-500">完整数据，包含所有元信息</p>
                </div>
              </button>

              <div className="border-t border-gray-200 dark:border-gray-700 my-4" />

              <button
                onClick={() => handleExport('characters')}
                disabled={isExporting}
                className="w-full flex items-center gap-3 p-4 bg-gray-50 dark:bg-gray-700 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-600 transition-colors text-left"
              >
                <Users className="h-5 w-5 text-gray-600 dark:text-gray-400" />
                <div>
                  <p className="font-medium text-gray-900 dark:text-white">导出角色设定</p>
                  <p className="text-sm text-gray-500">所有角色的人设信息</p>
                </div>
              </button>

              <button
                onClick={() => handleExport('outline')}
                disabled={isExporting}
                className="w-full flex items-center gap-3 p-4 bg-gray-50 dark:bg-gray-700 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-600 transition-colors text-left"
              >
                <FileText className="h-5 w-5 text-gray-600 dark:text-gray-400" />
                <div>
                  <p className="font-medium text-gray-900 dark:text-white">导出大纲</p>
                  <p className="text-sm text-gray-500">剧情大纲和分卷结构</p>
                </div>
              </button>
            </div>

            {isExporting && (
              <p className="mt-4 text-center text-sm text-gray-500">
                正在导出...
              </p>
            )}
          </div>
        </div>
      )}
    </div>
  )
}