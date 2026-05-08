import { useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import {
  ChevronDown, ChevronRight, Sparkles, ArrowLeft,
  Edit3, FileText, List, Save, X, Plus, Trash2, Check, AlertCircle
} from 'lucide-react'
import { outlineApi, workflowApi } from '../services/api'
import type { Outline, Arc } from '../types'

// 章节细纲编辑弹窗
function ChapterOutlineEditor({
  chapter,
  novelId,
  onClose,
  onSave,
}: {
  chapter: any
  novelId: number
  onClose: () => void
  onSave: (data: any) => void
}) {
  const [form, setForm] = useState({
    title: chapter.title || '',
    summary: chapter.summary || '',
    key_points: (chapter.key_points || []).join('\n'),
    characters: (chapter.characters || []).join(', '),
    scenes: chapter.scenes || [],
    word_count_target: chapter.word_count_target || 3000,
  })
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')

  const handleSave = async () => {
    setSaving(true)
    setError('')
    try {
      const payload = {
        ...chapter,
        title: form.title,
        summary: form.summary,
        key_points: form.key_points.split('\n').filter((s: string) => s.trim()),
        characters: form.characters.split(/[,，]/).map((s: string) => s.trim()).filter(Boolean),
        scenes: form.scenes,
        word_count_target: form.word_count_target,
      }
      await workflowApi.updateChapterOutline(novelId, chapter.chapter_number, payload)
      onSave(payload)
      onClose()
    } catch (e: any) {
      setError(e?.response?.data?.detail || e?.message || '保存失败')
    } finally {
      setSaving(false)
    }
  }

  const updateScene = (idx: number, field: string, value: string) => {
    const newScenes = [...form.scenes]
    newScenes[idx] = { ...newScenes[idx], [field]: value }
    setForm(f => ({ ...f, scenes: newScenes }))
  }

  const addScene = () => {
    setForm(f => ({
      ...f,
      scenes: [...f.scenes, { scene_name: '', description: '', location: '', time: '' }],
    }))
  }

  const removeScene = (idx: number) => {
    setForm(f => ({ ...f, scenes: f.scenes.filter((_: any, i: number) => i !== idx) }))
  }

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <div className="bg-white dark:bg-gray-800 rounded-xl shadow-2xl w-full max-w-2xl max-h-[90vh] overflow-y-auto">
        <div className="sticky top-0 bg-white dark:bg-gray-800 border-b border-gray-200 dark:border-gray-700 px-6 py-4 flex items-center justify-between">
          <h3 className="text-lg font-semibold text-gray-900 dark:text-white">
            编辑第 {chapter.chapter_number} 章细纲
          </h3>
          <button onClick={onClose} className="p-1 hover:bg-gray-100 dark:hover:bg-gray-700 rounded">
            <X className="h-5 w-5 text-gray-500" />
          </button>
        </div>

        <div className="p-6 space-y-5">
          {error && (
            <div className="p-3 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg flex items-start gap-2">
              <AlertCircle className="h-5 w-5 text-red-500 mt-0.5 shrink-0" />
              <span className="text-sm text-red-700 dark:text-red-300">{error}</span>
            </div>
          )}

          {/* 标题 */}
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">章节标题</label>
            <input
              type="text"
              value={form.title}
              onChange={e => setForm(f => ({ ...f, title: e.target.value }))}
              className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white focus:ring-2 focus:ring-primary-500"
              placeholder="例：初入异境"
            />
          </div>

          {/* 概要 */}
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">章节概要</label>
            <textarea
              value={form.summary}
              onChange={e => setForm(f => ({ ...f, summary: e.target.value }))}
              rows={4}
              className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white focus:ring-2 focus:ring-primary-500"
              placeholder="描述本章的主要内容和走向..."
            />
          </div>

          {/* 要点 */}
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
              章节要点 <span className="text-gray-400 font-normal">（每行一条）</span>
            </label>
            <textarea
              value={form.key_points}
              onChange={e => setForm(f => ({ ...f, key_points: e.target.value }))}
              rows={4}
              className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white focus:ring-2 focus:ring-primary-500 font-mono text-sm"
              placeholder={"推进主线剧情\n揭示新规则\n角色心理变化\n埋下伏笔"}
            />
          </div>

          {/* 角色 */}
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
              出场角色 <span className="text-gray-400 font-normal">（逗号分隔）</span>
            </label>
            <input
              type="text"
              value={form.characters}
              onChange={e => setForm(f => ({ ...f, characters: e.target.value }))}
              className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white focus:ring-2 focus:ring-primary-500"
              placeholder="主角, 配角A, 反派B"
            />
          </div>

          {/* 场景 */}
          <div>
            <div className="flex items-center justify-between mb-2">
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300">场景设定</label>
              <button
                onClick={addScene}
                className="flex items-center gap-1 text-sm text-primary-600 hover:text-primary-700"
              >
                <Plus className="h-4 w-4" /> 添加场景
              </button>
            </div>
            <div className="space-y-3">
              {form.scenes.map((scene: any, idx: number) => (
                <div key={idx} className="p-3 border border-gray-200 dark:border-gray-600 rounded-lg space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="text-xs text-gray-500">场景 {idx + 1}</span>
                    <button onClick={() => removeScene(idx)} className="text-red-400 hover:text-red-600">
                      <Trash2 className="h-3.5 w-3.5" />
                    </button>
                  </div>
                  <div className="grid grid-cols-2 gap-2">
                    <input
                      type="text"
                      value={scene.scene_name || scene.location || ''}
                      onChange={e => updateScene(idx, scene.scene_name !== undefined ? 'scene_name' : 'location', e.target.value)}
                      placeholder="场景名/地点"
                      className="px-2 py-1.5 text-sm border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
                    />
                    <input
                      type="text"
                      value={scene.time || ''}
                      onChange={e => updateScene(idx, 'time', e.target.value)}
                      placeholder="时间（可选）"
                      className="px-2 py-1.5 text-sm border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
                    />
                  </div>
                  <textarea
                    value={scene.description || scene.purpose || ''}
                    onChange={e => updateScene(idx, scene.description !== undefined ? 'description' : 'purpose', e.target.value)}
                    placeholder="场景描述..."
                    rows={2}
                    className="w-full px-2 py-1.5 text-sm border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
                  />
                </div>
              ))}
              {form.scenes.length === 0 && (
                <p className="text-sm text-gray-400 text-center py-3">暂无场景，点击上方添加</p>
              )}
            </div>
          </div>

          {/* 目标字数 */}
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">目标字数</label>
            <input
              type="number"
              value={form.word_count_target}
              onChange={e => setForm(f => ({ ...f, word_count_target: parseInt(e.target.value) || 3000 }))}
              className="w-32 px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white focus:ring-2 focus:ring-primary-500"
            />
          </div>
        </div>

        <div className="sticky bottom-0 bg-white dark:bg-gray-800 border-t border-gray-200 dark:border-gray-700 px-6 py-4 flex justify-end gap-3">
          <button
            onClick={onClose}
            className="px-4 py-2 text-sm text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-lg"
          >
            取消
          </button>
          <button
            onClick={handleSave}
            disabled={saving}
            className="flex items-center gap-2 px-4 py-2 text-sm bg-primary-600 text-white rounded-lg hover:bg-primary-700 disabled:opacity-50"
          >
            {saving ? (
              <span className="animate-spin">⏳</span>
            ) : (
              <Save className="h-4 w-4" />
            )}
            {saving ? '保存中...' : '保存'}
          </button>
        </div>
      </div>
    </div>
  )
}

// 新增章节细纲弹窗
function NewChapterOutlineDialog({
  novelId,
  nextChapterNumber,
  onClose,
  onSave,
}: {
  novelId: number
  nextChapterNumber: number
  onClose: () => void
  onSave: (data: any) => void
}) {
  const [form, setForm] = useState({
    title: '',
    summary: '',
    key_points: '',
    characters: '',
    word_count_target: 3000,
  })
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')

  const handleSave = async () => {
    setSaving(true)
    setError('')
    try {
      const payload = {
        chapter_number: nextChapterNumber,
        title: form.title || `第${nextChapterNumber}章`,
        summary: form.summary,
        key_points: form.key_points.split('\n').filter(s => s.trim()),
        characters: form.characters.split(/[,，]/).map(s => s.trim()).filter(Boolean),
        scenes: [],
        word_count_target: form.word_count_target,
      }
      await workflowApi.updateChapterOutline(novelId, nextChapterNumber, payload)
      onSave(payload)
      onClose()
    } catch (e: any) {
      setError(e?.response?.data?.detail || e?.message || '创建失败')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <div className="bg-white dark:bg-gray-800 rounded-xl shadow-2xl w-full max-w-lg">
        <div className="border-b border-gray-200 dark:border-gray-700 px-6 py-4 flex items-center justify-between">
          <h3 className="text-lg font-semibold text-gray-900 dark:text-white">
            新增第 {nextChapterNumber} 章细纲
          </h3>
          <button onClick={onClose} className="p-1 hover:bg-gray-100 dark:hover:bg-gray-700 rounded">
            <X className="h-5 w-5 text-gray-500" />
          </button>
        </div>

        <div className="p-6 space-y-4">
          {error && (
            <div className="p-3 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg flex items-start gap-2">
              <AlertCircle className="h-5 w-5 text-red-500 mt-0.5 shrink-0" />
              <span className="text-sm text-red-700 dark:text-red-300">{error}</span>
            </div>
          )}

          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">章节标题</label>
            <input
              type="text"
              value={form.title}
              onChange={e => setForm(f => ({ ...f, title: e.target.value }))}
              className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
              placeholder={`第${nextChapterNumber}章`}
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">章节概要</label>
            <textarea
              value={form.summary}
              onChange={e => setForm(f => ({ ...f, summary: e.target.value }))}
              rows={3}
              className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
              placeholder="描述本章的主要内容和走向..."
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
              章节要点 <span className="text-gray-400 font-normal">（每行一条）</span>
            </label>
            <textarea
              value={form.key_points}
              onChange={e => setForm(f => ({ ...f, key_points: e.target.value }))}
              rows={3}
              className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white font-mono text-sm"
              placeholder={"推进主线\n揭示新内容"}
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
              出场角色 <span className="text-gray-400 font-normal">（逗号分隔）</span>
            </label>
            <input
              type="text"
              value={form.characters}
              onChange={e => setForm(f => ({ ...f, characters: e.target.value }))}
              className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
              placeholder="主角, 配角A"
            />
          </div>
        </div>

        <div className="border-t border-gray-200 dark:border-gray-700 px-6 py-4 flex justify-end gap-3">
          <button onClick={onClose} className="px-4 py-2 text-sm text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-lg">
            取消
          </button>
          <button
            onClick={handleSave}
            disabled={saving}
            className="flex items-center gap-2 px-4 py-2 text-sm bg-primary-600 text-white rounded-lg hover:bg-primary-700 disabled:opacity-50"
          >
            <Plus className="h-4 w-4" />
            {saving ? '创建中...' : '创建'}
          </button>
        </div>
      </div>
    </div>
  )
}

export function OutlineEditor() {
  const { novelId } = useParams<{ novelId: string }>()
  const id = parseInt(novelId || '0')
  const queryClient = useQueryClient()
  const [expandedVolumes, setExpandedVolumes] = useState<Set<number>>(new Set([1]))
  const [expandedChapters, setExpandedChapters] = useState<Set<number>>(new Set())
  const [editingChapter, setEditingChapter] = useState<any>(null)
  const [showNewDialog, setShowNewDialog] = useState(false)
  const [deletingChapter, setDeletingChapter] = useState<number | null>(null)
  const [toast, setToast] = useState<{ msg: string; type: 'ok' | 'err' } | null>(null)

  // 获取工作流的大纲数据
  const { data: workflowOutline } = useQuery({
    queryKey: ['workflow-outline', id],
    queryFn: async () => {
      try {
        const result = await workflowApi.getPhaseResult(id, 'outline_draft')
        if (result && typeof result === 'object' && (result as any).data) return (result as any).data
        if (result && typeof result === 'object') return result
        return null
      } catch {
        return null
      }
    },
    enabled: !!id,
    retry: false,
  })

  // 获取工作流的章节细纲数据 — 直接用新的 CRUD API
  const { data: chapterOutlinesData, isLoading: outlinesLoading } = useQuery({
    queryKey: ['chapter-outlines', id],
    queryFn: async () => {
      try {
        const result = await workflowApi.listChapterOutlines(id)
        return (result as any)?.chapter_outlines || []
      } catch {
        return []
      }
    },
    enabled: !!id,
    retry: false,
  })

  const chapterOutlines: any[] = chapterOutlinesData || []

  const { data: outlinesData } = useQuery({
    queryKey: ['outlines', id],
    queryFn: () => outlineApi.list(id),
    enabled: !!id,
  })

  const outlines = (outlinesData as any)?.items || []

  const showToast = (msg: string, type: 'ok' | 'err' = 'ok') => {
    setToast({ msg, type })
    setTimeout(() => setToast(null), 3000)
  }

  const toggleVolume = (volumeNumber: number) => {
    const newExpanded = new Set(expandedVolumes)
    if (newExpanded.has(volumeNumber)) newExpanded.delete(volumeNumber)
    else newExpanded.add(volumeNumber)
    setExpandedVolumes(newExpanded)
  }

  const toggleChapter = (chapterNumber: number) => {
    const newExpanded = new Set(expandedChapters)
    if (newExpanded.has(chapterNumber)) newExpanded.delete(chapterNumber)
    else newExpanded.add(chapterNumber)
    setExpandedChapters(newExpanded)
  }

  const handleOutlineSaved = (updated: any) => {
    queryClient.setQueryData(['chapter-outlines', id], (old: any[] | undefined) => {
      const list = old || []
      const idx = list.findIndex((co: any) => co.chapter_number === updated.chapter_number)
      if (idx >= 0) {
        const newList = [...list]
        newList[idx] = updated
        return newList
      }
      return [...list, updated].sort((a: any, b: any) => a.chapter_number - b.chapter_number)
    })
    showToast(`第 ${updated.chapter_number} 章细纲已保存`)
  }

  const handleDeleteChapter = async (chapterNumber: number) => {
    try {
      await workflowApi.deleteChapterOutline(id, chapterNumber)
      queryClient.setQueryData(['chapter-outlines', id], (old: any[] | undefined) =>
        (old || []).filter((co: any) => co.chapter_number !== chapterNumber)
      )
      setDeletingChapter(null)
      showToast(`第 ${chapterNumber} 章细纲已删除`)
    } catch (e: any) {
      showToast(e?.response?.data?.detail || '删除失败', 'err')
    }
  }

  const nextChapterNumber = chapterOutlines.length > 0
    ? Math.max(...chapterOutlines.map((co: any) => co.chapter_number || 0)) + 1
    : 1

  return (
    <div className="space-y-6">
      {/* Toast */}
      {toast && (
        <div className={`fixed top-4 right-4 z-50 px-4 py-3 rounded-lg shadow-lg flex items-center gap-2 text-sm font-medium ${
          toast.type === 'ok'
            ? 'bg-green-100 text-green-800 dark:bg-green-900/40 dark:text-green-300'
            : 'bg-red-100 text-red-800 dark:bg-red-900/40 dark:text-red-300'
        }`}>
          {toast.type === 'ok' ? <Check className="h-4 w-4" /> : <AlertCircle className="h-4 w-4" />}
          {toast.msg}
        </div>
      )}

      {/* 返回按钮 */}
      <Link
        to={`/novel/${id}`}
        className="inline-flex items-center gap-2 text-gray-600 dark:text-gray-400 hover:text-primary-600 dark:hover:text-primary-400 transition-colors"
      >
        <ArrowLeft className="h-5 w-5" />
        返回小说详情
      </Link>

      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 dark:text-white">大纲编辑</h1>
          {(workflowOutline || chapterOutlines.length > 0) && (
            <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
              {workflowOutline && '包含工作流生成的剧情大纲 '}
              {chapterOutlines.length > 0 && `和 ${chapterOutlines.length} 章的细纲`}
            </p>
          )}
        </div>
        <div className="flex items-center gap-2">
          {chapterOutlines.length > 0 && (
            <button
              onClick={() => setShowNewDialog(true)}
              className="flex items-center gap-2 px-3 py-2 text-sm border border-gray-300 dark:border-gray-600 text-gray-700 dark:text-gray-300 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-700"
            >
              <Plus className="h-4 w-4" /> 新增章节
            </button>
          )}
          <button className="flex items-center gap-2 px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700">
            <Sparkles className="h-5 w-5" />
            AI生成大纲
          </button>
        </div>
      </div>

      {/* 工作流生成的大纲（剧情大纲 — 只读） */}
      {workflowOutline && (
        <div className="bg-white dark:bg-gray-800 rounded-xl shadow-sm border border-gray-200 dark:border-gray-700 overflow-hidden">
          <div className="p-4 border-b border-gray-200 dark:border-gray-700 flex items-center gap-2 bg-purple-50 dark:bg-purple-900/20">
            <Sparkles className="h-5 w-5 text-purple-600" />
            <h3 className="font-semibold text-gray-900 dark:text-white">工作流生成的剧情大纲</h3>
            <span className="text-xs text-gray-500 ml-auto">只读</span>
          </div>
          
          <div className="p-4 space-y-4">
            {workflowOutline.overview && (
              <div className="p-4 bg-blue-50 dark:bg-blue-900/20 rounded-lg">
                <h4 className="font-medium text-blue-900 dark:text-blue-300 mb-2">故事概述</h4>
                <p className="text-sm text-blue-800 dark:text-blue-300">{workflowOutline.overview}</p>
              </div>
            )}

            {workflowOutline.volumes && workflowOutline.volumes.length > 0 && (
              <div className="space-y-3">
                {workflowOutline.volumes.map((volume: any, vIndex: number) => (
                  <div key={vIndex} className="border border-gray-200 dark:border-gray-700 rounded-lg">
                    <button
                      onClick={() => toggleVolume(volume.volume_number)}
                      className="w-full px-4 py-3 flex items-center justify-between hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors"
                    >
                      <div className="flex items-center gap-3">
                        {expandedVolumes.has(volume.volume_number) ? <ChevronDown className="h-4 w-4 text-gray-400" /> : <ChevronRight className="h-4 w-4 text-gray-400" />}
                        <span className="font-medium text-gray-900 dark:text-white">第{volume.volume_number}卷: {volume.title}</span>
                      </div>
                      <span className="text-sm text-gray-500">{volume.chapters?.length || 0} 章</span>
                    </button>
                    {expandedVolumes.has(volume.volume_number) && volume.chapters && (
                      <div className="px-4 pb-4 pt-2">
                        {volume.chapters.map((chapter: any, cIndex: number) => (
                          <div key={cIndex} className="ml-6 mb-2">
                            <div className="flex items-center gap-2 text-sm text-gray-700 dark:text-gray-300">
                              <FileText className="h-4 w-4" />
                              <span className="font-medium">第{chapter.chapter_number}章</span>
                              {chapter.title && <span>{chapter.title}</span>}
                            </div>
                            {chapter.summary && <p className="text-xs text-gray-500 dark:text-gray-400 ml-6 mt-1">{chapter.summary}</p>}
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}

            {workflowOutline.arcs && workflowOutline.arcs.length > 0 && (
              <div>
                <h4 className="font-medium text-gray-900 dark:text-white mb-2">剧情弧光</h4>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                  {workflowOutline.arcs.map((arc: Arc, index: number) => (
                    <div key={index} className="p-3 bg-gray-50 dark:bg-gray-700/50 rounded-lg">
                      <div className="flex items-start justify-between mb-2">
                        <h5 className="font-medium text-gray-900 dark:text-white text-sm">{arc.title}</h5>
                        <span className="text-xs text-gray-500">第{arc.start_chapter}-{arc.end_chapter}章</span>
                      </div>
                      <p className="text-xs text-gray-600 dark:text-gray-400 mb-2">{arc.description}</p>
                      {arc.key_events && arc.key_events.length > 0 && (
                        <div className="flex flex-wrap gap-1">
                          {arc.key_events.slice(0, 3).map((event, i) => (
                            <span key={i} className="text-xs px-2 py-0.5 bg-white dark:bg-gray-600 rounded text-gray-600 dark:text-gray-300">{event}</span>
                          ))}
                          {arc.key_events.length > 3 && <span className="text-xs text-gray-500">+{arc.key_events.length - 3}</span>}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* 章节细纲（可编辑） */}
      <div className="bg-white dark:bg-gray-800 rounded-xl shadow-sm border border-gray-200 dark:border-gray-700 overflow-hidden">
        <div className="p-4 border-b border-gray-200 dark:border-gray-700 flex items-center gap-2 bg-green-50 dark:bg-green-900/20">
          <List className="h-5 w-5 text-green-600" />
          <h3 className="font-semibold text-gray-900 dark:text-white">章节细纲</h3>
          {chapterOutlines.length > 0 && (
            <span className="text-sm text-gray-500">共 {chapterOutlines.length} 章</span>
          )}
          <span className="text-xs text-green-600 ml-auto">可编辑</span>
        </div>
        
        {outlinesLoading ? (
          <div className="p-8 text-center text-gray-500">加载中...</div>
        ) : chapterOutlines.length === 0 ? (
          <div className="p-8 text-center">
            <FileText className="h-10 w-10 text-gray-400 mx-auto mb-3" />
            <p className="text-gray-500 dark:text-gray-400 mb-3">暂无章节细纲</p>
            <button
              onClick={() => setShowNewDialog(true)}
              className="inline-flex items-center gap-2 px-4 py-2 text-sm bg-primary-600 text-white rounded-lg hover:bg-primary-700"
            >
              <Plus className="h-4 w-4" /> 创建第一章细纲
            </button>
          </div>
        ) : (
          <div className="p-4 space-y-3">
            {chapterOutlines.map((chapter: any) => (
              <div key={chapter.chapter_number} className="border border-gray-200 dark:border-gray-700 rounded-lg">
                <button
                  onClick={() => toggleChapter(chapter.chapter_number)}
                  className="w-full px-4 py-3 flex items-center justify-between hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors"
                >
                  <div className="flex items-center gap-3">
                    {expandedChapters.has(chapter.chapter_number) ? <ChevronDown className="h-4 w-4 text-gray-400" /> : <ChevronRight className="h-4 w-4 text-gray-400" />}
                    <div className="text-left">
                      <div className="flex items-center gap-2">
                        <span className="font-medium text-gray-900 dark:text-white">第{chapter.chapter_number}章</span>
                        {chapter.title && <span className="text-gray-600 dark:text-gray-400">{chapter.title}</span>}
                      </div>
                      {chapter.summary && (
                        <p className="text-xs text-gray-500 dark:text-gray-400 mt-0.5 max-w-lg line-clamp-2">{chapter.summary}</p>
                      )}
                    </div>
                  </div>
                  <div className="flex items-center gap-1">
                    <button
                      onClick={e => { e.stopPropagation(); setEditingChapter(chapter) }}
                      className="p-1.5 hover:bg-gray-200 dark:hover:bg-gray-600 rounded"
                      title="编辑"
                    >
                      <Edit3 className="h-4 w-4 text-gray-400" />
                    </button>
                    <button
                      onClick={e => { e.stopPropagation(); setDeletingChapter(chapter.chapter_number) }}
                      className="p-1.5 hover:bg-red-100 dark:hover:bg-red-900/30 rounded"
                      title="删除"
                    >
                      <Trash2 className="h-4 w-4 text-gray-400 hover:text-red-500" />
                    </button>
                  </div>
                </button>

                {expandedChapters.has(chapter.chapter_number) && (
                  <div className="px-4 pb-4 pt-2 border-t border-gray-200 dark:border-gray-700 space-y-3">
                    {chapter.key_points && chapter.key_points.length > 0 && (
                      <div>
                        <h5 className="text-sm font-medium text-gray-900 dark:text-white mb-2">章节要点</h5>
                        <ul className="text-sm text-gray-600 dark:text-gray-400 space-y-1 ml-4 list-disc">
                          {chapter.key_points.map((point: string, i: number) => <li key={i}>{point}</li>)}
                        </ul>
                      </div>
                    )}
                    {chapter.characters && chapter.characters.length > 0 && (
                      <div>
                        <h5 className="text-sm font-medium text-gray-900 dark:text-white mb-2">角色出场</h5>
                        <div className="flex flex-wrap gap-2">
                          {chapter.characters.map((char: string, i: number) => (
                            <span key={i} className="px-2 py-1 text-xs bg-blue-100 text-blue-700 rounded dark:bg-blue-900/30 dark:text-blue-400">{char}</span>
                          ))}
                        </div>
                      </div>
                    )}
                    {chapter.events && chapter.events.length > 0 && (
                      <div>
                        <h5 className="text-sm font-medium text-gray-900 dark:text-white mb-2">关键事件</h5>
                        <div className="space-y-1">
                          {chapter.events.map((event: any, i: number) => (
                            <div key={i} className="text-sm text-gray-600 dark:text-gray-400 flex items-start gap-2">
                              <span className="text-purple-600 dark:text-purple-400">•</span>
                              <span>{event.description}</span>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                    {chapter.scenes && chapter.scenes.length > 0 && (
                      <div>
                        <h5 className="text-sm font-medium text-gray-900 dark:text-white mb-2">场景设定</h5>
                        <div className="space-y-2">
                          {chapter.scenes.map((scene: any, i: number) => (
                            <div key={i} className="text-sm text-gray-600 dark:text-gray-400">
                              <span className="font-medium">{scene.scene_name || scene.location}</span>
                              {scene.time && <span className="ml-2 text-gray-500">{scene.time}</span>}
                              {(scene.description || scene.purpose) && (
                                <p className="text-xs text-gray-500 mt-1 ml-2">{scene.description || scene.purpose}</p>
                              )}
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                    {chapter.word_count_target && (
                      <div className="text-xs text-gray-400">目标字数: {chapter.word_count_target}</div>
                    )}
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>

      {/* 数据库中的大纲 */}
      {outlines.length > 0 && (
        <div className="space-y-4">
          <h3 className="text-lg font-semibold text-gray-900 dark:text-white">已保存的大纲</h3>
          {outlines.map((outline: Outline) => (
            <div key={outline.id} className="bg-white dark:bg-gray-800 rounded-xl shadow-sm border border-gray-200 dark:border-gray-700 overflow-hidden">
              <button
                onClick={() => toggleVolume(outline.volume_number)}
                className="w-full px-6 py-4 flex items-center justify-between hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors"
              >
                <div className="flex items-center gap-4">
                  {expandedVolumes.has(outline.volume_number) ? <ChevronDown className="h-5 w-5 text-gray-400" /> : <ChevronRight className="h-5 w-5 text-gray-400" />}
                  <div>
                    <h3 className="text-lg font-semibold text-gray-900 dark:text-white">第{outline.volume_number}卷: {outline.volume_title}</h3>
                    <p className="text-sm text-gray-500 dark:text-gray-400">
                      {outline.actual_chapters} / {outline.target_chapters} 章
                      {outline.summary && ` · ${outline.summary}`}
                    </p>
                  </div>
                </div>
                <span className="text-sm text-gray-500">{outline.arcs?.length || 0} 个剧情弧</span>
              </button>
              {expandedVolumes.has(outline.volume_number) && (
                <div className="border-t border-gray-200 dark:border-gray-700 px-6 py-4">
                  {outline.key_points && (
                    <div className="mb-4 p-3 bg-blue-50 dark:bg-blue-900/20 rounded-lg">
                      <p className="text-sm text-blue-800 dark:text-blue-300"><strong>关键节点:</strong> {outline.key_points}</p>
                    </div>
                  )}
                  <div className="space-y-3">
                    {outline.arcs?.map((arc: Arc, index: number) => (
                      <div key={arc.arc_id || index} className="p-4 bg-gray-50 dark:bg-gray-700/50 rounded-lg">
                        <div className="flex items-start justify-between mb-2">
                          <h4 className="font-medium text-gray-900 dark:text-white">{arc.title}</h4>
                          <span className="text-xs text-gray-500">第{arc.start_chapter}-{arc.end_chapter}章</span>
                        </div>
                        <p className="text-sm text-gray-600 dark:text-gray-400 mb-2">{arc.description}</p>
                        {arc.key_events && arc.key_events.length > 0 && (
                          <div className="flex flex-wrap gap-2">
                            {arc.key_events.map((event, i) => (
                              <span key={i} className="text-xs px-2 py-1 bg-white dark:bg-gray-600 rounded text-gray-600 dark:text-gray-300">{event}</span>
                            ))}
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      {/* 编辑弹窗 */}
      {editingChapter && (
        <ChapterOutlineEditor
          chapter={editingChapter}
          novelId={id}
          onClose={() => setEditingChapter(null)}
          onSave={handleOutlineSaved}
        />
      )}

      {/* 新增弹窗 */}
      {showNewDialog && (
        <NewChapterOutlineDialog
          novelId={id}
          nextChapterNumber={nextChapterNumber}
          onClose={() => setShowNewDialog(false)}
          onSave={handleOutlineSaved}
        />
      )}

      {/* 删除确认 */}
      {deletingChapter !== null && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-white dark:bg-gray-800 rounded-xl shadow-2xl p-6 max-w-sm w-full">
            <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-2">确认删除</h3>
            <p className="text-sm text-gray-600 dark:text-gray-400 mb-4">
              确定删除第 {deletingChapter} 章细纲？此操作不可恢复。
            </p>
            <div className="flex justify-end gap-3">
              <button onClick={() => setDeletingChapter(null)} className="px-4 py-2 text-sm text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-lg">
                取消
              </button>
              <button onClick={() => handleDeleteChapter(deletingChapter)} className="px-4 py-2 text-sm bg-red-600 text-white rounded-lg hover:bg-red-700">
                删除
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
