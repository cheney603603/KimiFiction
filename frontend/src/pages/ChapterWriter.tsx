import { useState, useEffect } from 'react'
import { useParams, Link } from 'react-router-dom'
import { useQuery, useMutation } from '@tanstack/react-query'
import { 
  ArrowLeft, 
  Play, 
  Loader2, 
  Check, 
  BookOpen, 
  Sparkles, 
  Settings,
  FileText,
  ChevronDown,
  ChevronUp,
  MessageSquare,
  Eye,
  Star,
  AlertTriangle,
  Zap
} from 'lucide-react'
import { chapterApi, workflowApi } from '../services/api'
import type { Chapter } from '../types'

interface WritingSettings {
  chapter_number: number
  writing_style: string
  env_description_level: string
  dialogue_ratio: number
  notes: string
  timeout?: number
}

export function ChapterWriter() {
  const { novelId } = useParams<{ novelId: string }>()
  const id = parseInt(novelId || '0')
  
  const [selectedChapter, setSelectedChapter] = useState<number>(1)
  const [isGenerating, setIsGenerating] = useState(false)
  const [generatedContent, setGeneratedContent] = useState<string>('')
  const [showSettings, setShowSettings] = useState(false)
  const [isEditing, setIsEditing] = useState(false)
  const [editedContent, setEditedContent] = useState<string>('')
  const [showGenerateSuccess, setShowGenerateSuccess] = useState(false)
  const [activeTaskId, setActiveTaskId] = useState<string | null>(null)
  const [showFeedbackPanel, setShowFeedbackPanel] = useState(false)
  const [showPromptPanel, setShowPromptPanel] = useState(false)
  const [settings, setSettings] = useState<WritingSettings>({
    chapter_number: 1,
    writing_style: '现代简洁',
    env_description_level: 'normal',
    dialogue_ratio: 0.3,
    notes: '',
    timeout: 900  // 默认15分钟
  })

  // 获取小说信息
  const { data: novel } = useQuery({
    queryKey: ['novel', id],
    queryFn: () => fetch(`http://localhost:8080/api/v1/novels/${id}`).then(r => r.json()),
    enabled: !!id,
  })

  // 获取章节列表
  const { data: chaptersData } = useQuery({
    queryKey: ['chapters', id],
    queryFn: () => chapterApi.list(id, { limit: 200 }),
    enabled: !!id,
  })

  // 获取当前章节内容（如果已存在）
  const { data: currentChapter, refetch: refetchChapter } = useQuery({
    queryKey: ['chapter', id, selectedChapter],
    queryFn: () => chapterApi.getByNumber(id, selectedChapter),
    enabled: !!id && !!selectedChapter,
  })

  // 获取角色信息（用于章节写作上下文）
  const { data: characters } = useQuery({
    queryKey: ['characters', id],
    queryFn: async () => {
      try {
        const response = await fetch(`http://localhost:8080/api/v1/characters/${id}`)
        if (!response.ok) return []
        const result = await response.json()
        return result.items || []
      } catch (error) {
        console.log('角色数据不可用:', error)
        return []
      }
    },
    enabled: !!id,
    retry: false,
  })

  // 获取世界观设定（从工作流）
  const { data: worldSetting } = useQuery({
    queryKey: ['world-setting', id],
    queryFn: async () => {
      try {
        const result = await workflowApi.getPhaseResult(id, 'world_building')
        if (result && (result.data as any)?.world_setting) {
          return (result.data as any).world_setting
        } else if (result && result.data) {
          return result.data
        }
        return null
      } catch (error) {
        console.log('世界观设定不可用:', error)
        return null
      }
    },
    enabled: !!id,
    retry: false,
  })

  // 获取前文摘要（从最近章节）
  const { data: previousChapterSummary } = useQuery({
    queryKey: ['previous-summary', id, selectedChapter],
    queryFn: async () => {
      if (selectedChapter <= 1) return null
      try {
        const prevChapter = await chapterApi.getByNumber(id, selectedChapter - 1)
        return (prevChapter as any)?.summary || null
      } catch (error) {
        console.log('前文摘要不可用:', error)
        return null
      }
    },
    enabled: !!id && !!selectedChapter && selectedChapter > 1,
    retry: false,
  })

  // 获取章节细纲（从工作流）
  const { data: chapterOutline } = useQuery({
    queryKey: ['chapter-outline', id, selectedChapter],
    queryFn: async () => {
      try {
        const result = await workflowApi.getPhaseResult(id, 'outline_detail')
        
        if (!result) return null
        
        let chapterOutlines: any[] = []
        
        // 尝试从不同格式中提取章节细纲数组
        if (result.data?.chapter_outlines && Array.isArray(result.data.chapter_outlines)) {
          chapterOutlines = result.data.chapter_outlines
        } else if (result.data && Array.isArray(result.data)) {
          chapterOutlines = result.data
        } else if (Array.isArray(result)) {
          chapterOutlines = result
        }
        
        return chapterOutlines.find((c: any) => c.chapter_number === selectedChapter) || null
      } catch (error) {
        console.log('章节细纲数据不可用:', error)
        return null
      }
    },
    enabled: !!id && !!selectedChapter,
    retry: false,
  })

  // 获取章节读者反馈
  const { data: chapterFeedback, refetch: refetchFeedback } = useQuery({
    queryKey: ['chapter-feedback', id, selectedChapter],
    queryFn: async () => {
      try {
        const response = await fetch(`http://localhost:8080/api/v1/workflow/chapter-feedback/${id}/${selectedChapter}`)
        if (!response.ok) return null
        const result = await response.json()
        return result
      } catch (error) {
        console.log('读者反馈不可用:', error)
        return null
      }
    },
    enabled: !!id && !!selectedChapter,
    retry: false,
  })

  const readerFeedback = (chapterFeedback as any)?.reader_feedback || {}
  const loopHistory = (chapterFeedback as any)?.loop_history || []
  const editorReview = (chapterFeedback as any)?.editor_review || {}

  // 构建写作提示词预览
  const buildPromptPreview = () => {
    const envMap: Record<string, string> = { minimal: '极简提示', normal: '适度描写', rich: '丰富细腻' }
    const envDesc = envMap[settings.env_description_level] || '适度描写'
    const dialoguePct = Math.round(settings.dialogue_ratio * 100)
    
    const systemPrompt = `你是一位专业的小说写手，擅长撰写吸引人的章节内容。

请根据以下信息撰写章节：
- 小说背景、世界观设定、前文摘要、该章角色及未展开的剧情
- 该章细纲、详细的场景走向、关键事件、结尾钩子
- 主要角色名字、性格、说话风格和当前目标

写作要求
1. 忠实保持细纲的章节走向，不偏离、不遗忘、不跳跃
2. 与前文保持一致，对话符合人物性格和场景设定
3. 根据写作风格写作（${envDesc}）
4. 对话自然流畅，符合场景和内容
5. 每章不少于约{3000}字
6. 章节结构：开头吸引人、中间有发展、结尾留钩子或悬念
7. 注意应用前文的伏笔和悬念

写作风格：${settings.writing_style}
场景描写级别：${envDesc}
对话占比：约${dialoguePct}%`

    const userMessage = `请撰写小说第${selectedChapter}章。

## 上下文背景
${previousChapterSummary ? `前情提要：${previousChapterSummary}` : '（第一章，无前文背景）'}

## 章节细纲
${chapterOutline ? `章节标题：${chapterOutline.title || ''}\n章节大纲：${chapterOutline.summary || ''}` : '（无细纲）'}

## 主要人物角色简介
${characters && characters.length > 0 ? characters.slice(0, 5).map((c: any) => `【${c.name}】(${c.role_type || ''})${c.personality ? ` - 性格：${c.personality}` : ''}`).join('\n') : '（暂无）'}

${settings.notes ? `## 注意事项\n${settings.notes}` : ''}

请开始撰写章节正文：`

    return { systemPrompt, userMessage }
  }

  const generateMutation = useMutation({
    mutationFn: (data: WritingSettings) =>
      workflowApi.writeChapter(id, data),
    onSuccess: (result: any) => {
      const taskId = result?.task_id
      if (taskId) {
        // 异步任务：保存 task_id 并开始轮询
        setActiveTaskId(taskId)
      } else {
        // 兼容同步返回的情况
        const content = result?.data?.content || result?.content || result?.data || result?.result || ''
        if (content && typeof content === 'string') {
          setGeneratedContent(content)
        }
        setIsGenerating(false)
        setShowGenerateSuccess(true)
        setTimeout(() => setShowGenerateSuccess(false), 5000)
      }
    },
    onError: (error: any) => {
      setIsGenerating(false)
      setActiveTaskId(null)
      console.error('生成失败:', error)
      alert('生成失败，请重试')
    },
  })

  // 轮询任务进度
  useEffect(() => {
    if (!activeTaskId) return

    const interval = setInterval(async () => {
      try {
        const progress = await workflowApi.getTaskProgress(activeTaskId) as any
        const step = progress?.steps?.write_chapter
        if (step?.status === 'completed') {
          clearInterval(interval)
          setActiveTaskId(null)
          setIsGenerating(false)
          setShowGenerateSuccess(true)
          await refetchChapter()
          await refetchFeedback()
          setTimeout(() => setShowGenerateSuccess(false), 5000)
        } else if (step?.status === 'failed') {
          clearInterval(interval)
          setActiveTaskId(null)
          setIsGenerating(false)
          alert('章节生成失败：' + (step?.error || '未知错误'))
        }
      } catch (e) {
        console.error('轮询进度失败:', e)
      }
    }, 3000)

    return () => clearInterval(interval)
  }, [activeTaskId, refetchChapter])

  // 保存章节到数据库的 mutation
  const saveMutation = useMutation({
    mutationFn: async (content: string) => {
      // 检查章节是否已存在
      const existingChapter = await chapterApi.getByNumber(id, selectedChapter)
      
      if (existingChapter) {
        // 更新现有章节
        return fetch(`http://localhost:8080/api/v1/chapters/${(existingChapter as any).id}`, {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            content: content,
            title: chapterOutline?.title || `第${selectedChapter}章`,
            summary: chapterOutline?.summary,
          })
        })
      } else {
        // 创建新章节
        return fetch(`http://localhost:8080/api/v1/chapters`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            novel_id: id,
            chapter_number: selectedChapter,
            title: chapterOutline?.title || `第${selectedChapter}章`,
            content: content,
            summary: chapterOutline?.summary,
            characters_present: characters?.map((c: any) => c.name) || [],
          })
        })
      }
    },
    onSuccess: () => {
      alert('章节保存成功！')
      refetchChapter()
    },
    onError: () => {
      alert('保存失败，请重试')
    },
  })

  const chapters = (chaptersData as any)?.items || []
  const totalChapters = novel?.target_chapters || novel?.total_chapters || 20

  const handleGenerate = () => {
    if (!chapterOutline || !chapterOutline.summary) {
      alert(`第${selectedChapter}章缺少有效的章节细纲，无法生成。\n\n请先前往「工作流」页面，完成「章节细纲」阶段的设计，确保本章有细纲内容后再回来撰写。`)
      return
    }
    setIsGenerating(true)
    generateMutation.mutate(settings)
  }

  const handleChapterChange = (chapterNumber: number) => {
    setSelectedChapter(chapterNumber)
    setSettings({ ...settings, chapter_number: chapterNumber })
    setGeneratedContent('')
  }

  const displayContent = generatedContent || (currentChapter as any)?.content || ''

  const handleEdit = () => {
    setEditedContent(displayContent)
    setIsEditing(true)
  }

  const handleSave = () => {
    setIsEditing(false)
    saveMutation.mutate(editedContent)
  }

  const handleCancelEdit = () => {
    setIsEditing(false)
    setEditedContent('')
  }

  // 构建上下文预览
  const contextPreview = (
    <div className="space-y-3 mt-4">
      {worldSetting && (
        <div className="p-3 bg-purple-50 dark:bg-purple-900/20 rounded-lg">
          <h5 className="text-sm font-medium text-purple-800 dark:text-purple-300 mb-1">世界观设定</h5>
          <p className="text-xs text-purple-700 dark:text-purple-400 truncate">
            {typeof worldSetting === 'string' ? worldSetting.substring(0, 200) + '...' : JSON.stringify(worldSetting).substring(0, 200) + '...'}
          </p>
        </div>
      )}
      {characters && characters.length > 0 && (
        <div className="p-3 bg-blue-50 dark:bg-blue-900/20 rounded-lg">
          <h5 className="text-sm font-medium text-blue-800 dark:text-blue-300 mb-1">相关角色 ({characters.length})</h5>
          <div className="flex flex-wrap gap-1">
            {characters.slice(0, 5).map((char: any, i: number) => (
              <span key={i} className="text-xs px-2 py-0.5 bg-blue-100 text-blue-700 rounded dark:bg-blue-800 dark:text-blue-300">
                {char.name}
              </span>
            ))}
            {characters.length > 5 && <span className="text-xs text-blue-600">...</span>}
          </div>
        </div>
      )}
      {previousChapterSummary && (
        <div className="p-3 bg-yellow-50 dark:bg-yellow-900/20 rounded-lg">
          <h5 className="text-sm font-medium text-yellow-800 dark:text-yellow-300 mb-1">前文摘要</h5>
          <p className="text-xs text-yellow-700 dark:text-yellow-400 truncate">
            {previousChapterSummary.substring(0, 200)}...
          </p>
        </div>
      )}
    </div>
  )

  return (
    <div className="h-[calc(100vh-8rem)] flex flex-col">
      {/* 返回按钮和标题 */}
      <div className="flex items-center justify-between mb-4">
        <Link
          to={`/novel/${id}`}
          className="inline-flex items-center gap-2 text-gray-600 dark:text-gray-400 hover:text-primary-600 dark:hover:text-primary-400 transition-colors"
        >
          <ArrowLeft className="h-5 w-5" />
          返回小说详情
        </Link>
        <div className="flex items-center gap-2">
          <span className="text-sm text-gray-500 dark:text-gray-400">
            当前章节: 第 {selectedChapter} / {totalChapters} 章
          </span>
        </div>
      </div>

      {/* 生成成功提示 */}
      {showGenerateSuccess && (
        <div className="mb-4 bg-green-50 dark:bg-green-900/20 border border-green-200 dark:border-green-800 rounded-lg p-4 flex items-center gap-3">
          <Check className="h-5 w-5 text-green-600 dark:text-green-400" />
          <div className="flex-1">
            <p className="text-sm font-medium text-green-800 dark:text-green-300">
              章节生成成功！
            </p>
            <p className="text-xs text-green-700 dark:text-green-400 mt-1">
              您可以查看内容，点击"编辑"按钮修改后再保存到数据库
            </p>
          </div>
          <button
            onClick={() => setShowGenerateSuccess(false)}
            className="text-green-600 dark:text-green-400 hover:text-green-800 dark:hover:text-green-200"
          >
            ✕
          </button>
        </div>
      )}

      {/* 章节选择栏 */}
      <div className="bg-white dark:bg-gray-800 rounded-xl p-4 shadow-sm border border-gray-200 dark:border-gray-700 mb-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-4">
            <div className="flex items-center gap-2">
              <span className="text-sm font-medium text-gray-700 dark:text-gray-300">选择章节:</span>
              <select
                value={selectedChapter}
                onChange={(e) => handleChapterChange(parseInt(e.target.value))}
                className="px-3 py-1.5 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white text-sm"
              >
                {Array.from({ length: totalChapters }, (_, i) => i + 1).map((num) => (
                  <option key={num} value={num}>
                    第{num}章 {chapters.find((c: Chapter) => c.chapter_number === num)?.title || ''}
                  </option>
                ))}
              </select>
            </div>

            {/* 章节细纲预览 */}
            {chapterOutline && (
              <button
                onClick={() => setShowSettings(!showSettings)}
                className="flex items-center gap-2 px-3 py-1.5 text-sm bg-green-100 text-green-700 rounded-lg hover:bg-green-200 dark:bg-green-900/30 dark:text-green-400 dark:hover:bg-green-900/50"
              >
                <FileText className="h-4 w-4" />
                查看细纲
              </button>
            )}

            {(worldSetting || characters?.length > 0 || previousChapterSummary) && (
              <button
                onClick={() => setShowSettings(!showSettings)}
                className="flex items-center gap-2 px-3 py-1.5 text-sm bg-purple-100 text-purple-700 rounded-lg hover:bg-purple-200 dark:bg-purple-900/30 dark:text-purple-400 dark:hover:bg-purple-900/50"
              >
                <BookOpen className="h-4 w-4" />
                查看上下文
              </button>
            )}

            <button
              onClick={() => setShowSettings(!showSettings)}
              className="flex items-center gap-2 px-3 py-1.5 text-sm bg-blue-100 text-blue-700 rounded-lg hover:bg-blue-200 dark:bg-blue-900/30 dark:text-blue-400 dark:hover:bg-blue-900/50"
            >
              <Settings className="h-4 w-4" />
              写作设置
            </button>
          </div>

          <button
            onClick={handleGenerate}
            disabled={isGenerating}
            className="flex items-center gap-2 px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700 disabled:opacity-50"
          >
            {isGenerating ? (
              <>
                <Loader2 className="h-5 w-5 animate-spin" />
                生成中...
              </>
            ) : (
              <>
                <Play className="h-5 w-5" />
                开始生成
              </>
            )}
          </button>
        </div>

        {/* 设置面板 */}
        {showSettings && (
          <div className="mt-4 pt-4 border-t border-gray-200 dark:border-gray-700 space-y-4">
            {/* 上下文预览 */}
            {contextPreview}

            {/* 细纲预览 */}
            {chapterOutline && (
              <div className="p-4 bg-green-50 dark:bg-green-900/20 rounded-lg">
                <h4 className="font-medium text-green-900 dark:text-green-300 mb-2 flex items-center gap-2">
                  <FileText className="h-4 w-4" />
                  章节细纲
                </h4>
                {chapterOutline.summary && (
                  <p className="text-sm text-green-800 dark:text-green-300 mb-2">
                    {chapterOutline.summary}
                  </p>
                )}
                {chapterOutline.key_points && chapterOutline.key_points.length > 0 && (
                  <div className="space-y-1">
                    <p className="text-xs font-medium text-green-700 dark:text-green-400">章节要点:</p>
                    <ul className="text-sm text-green-800 dark:text-green-300 space-y-1 ml-4 list-disc">
                      {chapterOutline.key_points.map((point: string, i: number) => (
                        <li key={i}>{point}</li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            )}

            {/* 写作设置 */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                  文风
                </label>
                <select
                  value={settings.writing_style}
                  onChange={(e) => setSettings({ ...settings, writing_style: e.target.value })}
                  className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white text-sm"
                >
                  <option value="现代简洁">现代简洁</option>
                  <option value="古风典雅">古风典雅</option>
                  <option value="网络轻松">网络轻松</option>
                  <option value="严肃深沉">严肃深沉</option>
                  <option value="幽默诙谐">幽默诙谐</option>
                </select>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                  环境描写级别
                </label>
                <select
                  value={settings.env_description_level}
                  onChange={(e) => setSettings({ ...settings, env_description_level: e.target.value })}
                  className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white text-sm"
                >
                  <option value="minimal">极简</option>
                  <option value="normal">正常</option>
                  <option value="rich">丰富</option>
                </select>
              </div>

              <div className="md:col-span-2">
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                  对话占比: {Math.round(settings.dialogue_ratio * 100)}%
                </label>
                <input
                  type="range"
                  min="0"
                  max="1"
                  step="0.1"
                  value={settings.dialogue_ratio}
                  onChange={(e) => setSettings({ ...settings, dialogue_ratio: parseFloat(e.target.value) })}
                  className="w-full"
                />
              </div>

              <div className="md:col-span-2">
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                  写作注意事项
                </label>
                <textarea
                  value={settings.notes}
                  onChange={(e) => setSettings({ ...settings, notes: e.target.value })}
                  rows={2}
                  placeholder="例如：多描写人物心理，少用对话..."
                  className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white text-sm resize-none"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                  请求超时时间（秒）: {settings.timeout || 900}秒
                </label>
                <input
                  type="range"
                  min="60"
                  max="3600"
                  step="60"
                  value={settings.timeout || 900}
                  onChange={(e) => setSettings({ ...settings, timeout: parseInt(e.target.value) })}
                  className="w-full"
                />
                <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                  根据章节长度和网络情况调整，建议600-1800秒（10-30分钟）
                </p>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* 章节内容显示区 */}
      <div className="flex-1 bg-white dark:bg-gray-800 rounded-xl shadow-sm border border-gray-200 dark:border-gray-700 overflow-hidden flex flex-col">
        {/* 章节标题 */}
        <div className="px-6 py-4 border-b border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-700/50">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <BookOpen className="h-5 w-5 text-primary-600" />
              <div>
                <h2 className="text-xl font-semibold text-gray-900 dark:text-white">
                  第{selectedChapter}章 {(currentChapter as any)?.title || ''}
                </h2>
                <p className="text-sm text-gray-500 dark:text-gray-400">
                  {(currentChapter as any)?.word_count || 0} 字 · {displayContent ? '已生成' : '未生成'}
                </p>
              </div>
            </div>
            {displayContent && !isEditing && (
              <div className="flex gap-2">
                <button
                  onClick={handleEdit}
                  className="flex items-center gap-2 px-3 py-1.5 text-sm bg-blue-100 text-blue-700 rounded-lg hover:bg-blue-200 dark:bg-blue-900/30 dark:text-blue-400 dark:hover:bg-blue-900/50"
                >
                  <Settings className="h-4 w-4" />
                  编辑
                </button>
                <button
                  onClick={() => saveMutation.mutate(displayContent)}
                  disabled={saveMutation.isPending}
                  className="flex items-center gap-2 px-3 py-1.5 text-sm bg-green-100 text-green-700 rounded-lg hover:bg-green-200 dark:bg-green-900/30 dark:text-green-400 dark:hover:bg-green-900/50 disabled:opacity-50"
                >
                  {saveMutation.isPending ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  ) : (
                    <Check className="h-4 w-4" />
                  )}
                  保存到数据库
                </button>
              </div>
            )}
            {isEditing && (
              <div className="flex gap-2">
                <button
                  onClick={handleCancelEdit}
                  className="flex items-center gap-2 px-3 py-1.5 text-sm bg-gray-100 text-gray-700 rounded-lg hover:bg-gray-200 dark:bg-gray-700 dark:text-gray-300 dark:hover:bg-gray-600"
                >
                  取消
                </button>
                <button
                  onClick={handleSave}
                  disabled={saveMutation.isPending}
                  className="flex items-center gap-2 px-3 py-1.5 text-sm bg-green-600 text-white rounded-lg hover:bg-green-700 disabled:opacity-50"
                >
                  {saveMutation.isPending ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  ) : (
                    <Check className="h-4 w-4" />
                  )}
                  确认保存
                </button>
              </div>
            )}
          </div>
        </div>

        {/* 章节内容 */}
        <div className="flex-1 overflow-y-auto p-6">
          {isGenerating ? (
            <div className="flex flex-col items-center justify-center h-full text-gray-500 dark:text-gray-400">
              <Loader2 className="h-12 w-12 animate-spin mb-4 text-primary-600" />
              <p>正在生成章节内容...</p>
              <p className="text-sm mt-2">这可能需要几分钟，请耐心等待</p>
            </div>
          ) : isEditing ? (
            <textarea
              value={editedContent}
              onChange={(e) => setEditedContent(e.target.value)}
              className="w-full h-full min-h-[500px] p-4 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-900 text-gray-900 dark:text-white resize-none leading-relaxed"
              placeholder="在这里编辑章节内容..."
            />
          ) : displayContent ? (
            <div className="prose dark:prose-invert max-w-none">
              {displayContent.split('\n').map((paragraph: string, index: number) => (
                <p key={index} className="mb-4 text-gray-800 dark:text-gray-200 leading-relaxed">
                  {paragraph}
                </p>
              ))}
            </div>
          ) : (
            <div className="flex flex-col items-center justify-center h-full text-gray-500 dark:text-gray-400">
              <Sparkles className="h-12 w-12 mb-4" />
              <p className="text-lg font-medium">准备生成第{selectedChapter}章</p>
              <p className="text-sm mt-2">点击右上角的"开始生成"按钮</p>
              {chapterOutline && (
                <p className="text-sm mt-4 text-green-600 dark:text-green-400 flex items-center gap-1">
                  <Check className="h-4 w-4" />
                  已加载章节细纲
                </p>
              )}
            </div>
          )}
        </div>
      </div>

      {/* 读者评论展示面板 */}
      {(readerFeedback && Object.keys(readerFeedback).length > 0) && (
        <div className="mt-4 bg-white dark:bg-gray-800 rounded-xl shadow-sm border border-gray-200 dark:border-gray-700">
          <button
            onClick={() => setShowFeedbackPanel(!showFeedbackPanel)}
            className="w-full flex items-center justify-between px-6 py-3 text-left"
          >
            <div className="flex items-center gap-2">
              <MessageSquare className="h-5 w-5 text-orange-500" />
              <span className="font-medium text-gray-900 dark:text-white">读者评论</span>
              {loopHistory.length > 0 && (
                <span className="text-xs px-2 py-0.5 bg-orange-100 text-orange-700 rounded-full dark:bg-orange-900/30 dark:text-orange-400">
                  {loopHistory.length}轮修改
                </span>
              )}
            </div>
            {showFeedbackPanel ? <ChevronUp className="h-5 w-5 text-gray-400" /> : <ChevronDown className="h-5 w-5 text-gray-400" />}
          </button>
          
          {showFeedbackPanel && (
            <div className="px-6 pb-4 space-y-4 border-t border-gray-100 dark:border-gray-700">
              {/* 评分卡片 */}
              <div className="grid grid-cols-3 gap-3 pt-4">
                <div className="text-center p-3 bg-blue-50 dark:bg-blue-900/20 rounded-lg">
                  <div className="text-2xl font-bold text-blue-600 dark:text-blue-400">
                    {(readerFeedback.reader_score ?? 0).toFixed(1)}
                  </div>
                  <div className="text-xs text-blue-700 dark:text-blue-300 mt-1 flex items-center justify-center gap-1">
                    <Star className="h-3 w-3" /> 可读性
                  </div>
                </div>
                <div className="text-center p-3 bg-purple-50 dark:bg-purple-900/20 rounded-lg">
                  <div className="text-2xl font-bold text-purple-600 dark:text-purple-400">
                    {(readerFeedback.immersion_score ?? 0).toFixed(1)}
                  </div>
                  <div className="text-xs text-purple-700 dark:text-purple-300 mt-1 flex items-center justify-center gap-1">
                    <Eye className="h-3 w-3" /> 代入感
                  </div>
                </div>
                <div className="text-center p-3 bg-orange-50 dark:bg-orange-900/20 rounded-lg">
                  <div className="text-2xl font-bold text-orange-600 dark:text-orange-400">
                    {(readerFeedback.hook_score ?? 0).toFixed(1)}
                  </div>
                  <div className="text-xs text-orange-700 dark:text-orange-300 mt-1 flex items-center justify-center gap-1">
                    <Zap className="h-3 w-3" /> 钩子力
                  </div>
                </div>
              </div>

              {/* 是否追读 */}
              {readerFeedback.would_continue_reading !== undefined && (
                <div className={`p-3 rounded-lg text-sm ${readerFeedback.would_continue_reading ? 'bg-green-50 dark:bg-green-900/20 text-green-700 dark:text-green-300' : 'bg-red-50 dark:bg-red-900/20 text-red-700 dark:text-red-300'}`}>
                  {readerFeedback.would_continue_reading ? '✅ 读者愿意继续追读' : '❌ 读者可能弃读'}
                </div>
              )}

              {/* 困惑点 */}
              {readerFeedback.confusing_points?.length > 0 && (
                <div>
                  <h5 className="text-sm font-medium text-red-700 dark:text-red-300 mb-2 flex items-center gap-1">
                    <AlertTriangle className="h-4 w-4" /> 困惑点
                  </h5>
                  <ul className="space-y-1">
                    {readerFeedback.confusing_points.map((p: string, i: number) => (
                      <li key={i} className="text-sm text-gray-700 dark:text-gray-300 pl-4 border-l-2 border-red-300 dark:border-red-700">{p}</li>
                    ))}
                  </ul>
                </div>
              )}

              {/* 拖沓点 */}
              {readerFeedback.boring_points?.length > 0 && (
                <div>
                  <h5 className="text-sm font-medium text-yellow-700 dark:text-yellow-300 mb-2">节奏问题</h5>
                  <ul className="space-y-1">
                    {readerFeedback.boring_points.map((p: string, i: number) => (
                      <li key={i} className="text-sm text-gray-700 dark:text-gray-300 pl-4 border-l-2 border-yellow-300 dark:border-yellow-700">{p}</li>
                    ))}
                  </ul>
                </div>
              )}

              {/* 高光时刻 */}
              {readerFeedback.most_engaging_moments?.length > 0 && (
                <div>
                  <h5 className="text-sm font-medium text-green-700 dark:text-green-300 mb-2">高光时刻</h5>
                  <ul className="space-y-1">
                    {readerFeedback.most_engaging_moments.map((p: string, i: number) => (
                      <li key={i} className="text-sm text-gray-700 dark:text-gray-300 pl-4 border-l-2 border-green-300 dark:border-green-700">{p}</li>
                    ))}
                  </ul>
                </div>
              )}

              {/* 改进建议 */}
              {readerFeedback.revision_suggestions?.length > 0 && (
                <div>
                  <h5 className="text-sm font-medium text-blue-700 dark:text-blue-300 mb-2">改进建议</h5>
                  <ul className="space-y-1">
                    {readerFeedback.revision_suggestions.map((p: string, i: number) => (
                      <li key={i} className="text-sm text-gray-700 dark:text-gray-300 pl-4 border-l-2 border-blue-300 dark:border-blue-700">{p}</li>
                    ))}
                  </ul>
                </div>
              )}

              {/* 读者期待 */}
              {readerFeedback.reader_expectations?.length > 0 && (
                <div>
                  <h5 className="text-sm font-medium text-purple-700 dark:text-purple-300 mb-2">读者期待</h5>
                  <ul className="space-y-1">
                    {readerFeedback.reader_expectations.map((p: string, i: number) => (
                      <li key={i} className="text-sm text-gray-700 dark:text-gray-300 pl-4 border-l-2 border-purple-300 dark:border-purple-700">{p}</li>
                    ))}
                  </ul>
                </div>
              )}

              {/* 多轮修改历史 */}
              {loopHistory.length > 1 && (
                <div>
                  <h5 className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">写作修改历史</h5>
                  <div className="space-y-1">
                    {loopHistory.map((h: any, i: number) => (
                      <div key={i} className="flex items-center gap-3 text-xs text-gray-600 dark:text-gray-400 py-1">
                        <span className="font-medium">第{i + 1}轮</span>
                        <span>可读性: {h.reader_score?.toFixed(1) || '-'}</span>
                        <span>钩子: {h.hook_score?.toFixed(1) || '-'}</span>
                        <span className={h.passed ? 'text-green-600' : 'text-red-600'}>
                          {h.passed ? '✓ 通过' : '✗ 未通过'}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {/* 写作提示词展示面板 */}
      <div className="mt-4 bg-white dark:bg-gray-800 rounded-xl shadow-sm border border-gray-200 dark:border-gray-700">
        <button
          onClick={() => setShowPromptPanel(!showPromptPanel)}
          className="w-full flex items-center justify-between px-6 py-3 text-left"
        >
          <div className="flex items-center gap-2">
            <Eye className="h-5 w-5 text-indigo-500" />
            <span className="font-medium text-gray-900 dark:text-white">写作提示词预览</span>
          </div>
          {showPromptPanel ? <ChevronUp className="h-5 w-5 text-gray-400" /> : <ChevronDown className="h-5 w-5 text-gray-400" />}
        </button>
        
        {showPromptPanel && (
          <div className="px-6 pb-4 space-y-3 border-t border-gray-100 dark:border-gray-700">
            <div className="pt-4">
              <h5 className="text-xs font-medium text-gray-500 dark:text-gray-400 mb-1 uppercase tracking-wider">系统提示词 (System Prompt)</h5>
              <pre className="text-xs text-gray-700 dark:text-gray-300 bg-gray-50 dark:bg-gray-900 p-3 rounded-lg overflow-x-auto whitespace-pre-wrap">
                {buildPromptPreview().systemPrompt}
              </pre>
            </div>
            <div>
              <h5 className="text-xs font-medium text-gray-500 dark:text-gray-400 mb-1 uppercase tracking-wider">用户消息 (User Message)</h5>
              <pre className="text-xs text-gray-700 dark:text-gray-300 bg-gray-50 dark:bg-gray-900 p-3 rounded-lg overflow-x-auto whitespace-pre-wrap">
                {buildPromptPreview().userMessage}
              </pre>
            </div>
            <p className="text-xs text-gray-400 dark:text-gray-500">
              💡 以上为前端预览，实际发送给 LLM 的提示词可能略有不同（包含 ReAct 循环等额外信息）。
            </p>
          </div>
        )}
      </div>
    </div>
  )
}
