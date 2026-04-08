import { useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { BookOpen, ChevronDown, ChevronRight, Sparkles, ArrowLeft, Edit, FileText, List } from 'lucide-react'
import { outlineApi, workflowApi } from '../services/api'
import type { Outline, Arc } from '../types'

export function OutlineEditor() {
  const { novelId } = useParams<{ novelId: string }>()
  const id = parseInt(novelId || '0')
  const [expandedVolumes, setExpandedVolumes] = useState<Set<number>>(new Set([1]))
  const [expandedChapters, setExpandedChapters] = useState<Set<number>>(new Set())

  // 获取工作流的大纲数据
  const { data: workflowOutline } = useQuery({
    queryKey: ['workflow-outline', id],
    queryFn: async () => {
      try {
        const result = await workflowApi.getPhaseResult(id, 'outline_draft')
        console.log('工作流大纲数据:', result)
        
        if (!result) return null
        
        // 如果 result.data 是对象
        if (result.data && typeof result.data === 'object') {
          return result.data
        }
        
        // 如果 result 本身是对象
        if (typeof result === 'object') {
          return result
        }
        
        return null
      } catch (error) {
        console.log('工作流大纲数据不可用:', error)
        return null
      }
    },
    enabled: !!id,
    retry: false,
  })

  // 获取工作流的章节细纲数据
  const { data: workflowChapterOutlines } = useQuery({
    queryKey: ['workflow-chapter-outlines', id],
    queryFn: async () => {
      try {
        const result = await workflowApi.getPhaseResult(id, 'outline_detail')
        console.log('工作流章节细纲数据:', result)
        
        if (!result) return []
        
        // 如果 result.data.chapter_outlines 是数组
        if (result.data?.chapter_outlines && Array.isArray(result.data.chapter_outlines)) {
          return result.data.chapter_outlines
        }
        
        // 如果 result.data 是数组
        if (result.data && Array.isArray(result.data)) {
          return result.data
        }
        
        // 如果 result 本身是数组
        if (Array.isArray(result)) {
          return result
        }
        
        return []
      } catch (error) {
        console.log('工作流章节细纲数据不可用:', error)
        return []
      }
    },
    enabled: !!id,
    retry: false,
  })

  const { data: outlinesData } = useQuery({
    queryKey: ['outlines', id],
    queryFn: () => outlineApi.list(id),
    enabled: !!id,
  })

  const outlines = (outlinesData as any)?.items || []

  // 加载状态
  if (outlinesData === undefined && !workflowOutline) {
    return (
      <div className="flex justify-center items-center h-64">
        <div className="text-gray-500 dark:text-gray-400">加载中...</div>
      </div>
    )
  }

  const toggleVolume = (volumeNumber: number) => {
    const newExpanded = new Set(expandedVolumes)
    if (newExpanded.has(volumeNumber)) {
      newExpanded.delete(volumeNumber)
    } else {
      newExpanded.add(volumeNumber)
    }
    setExpandedVolumes(newExpanded)
  }

  const toggleChapter = (chapterNumber: number) => {
    const newExpanded = new Set(expandedChapters)
    if (newExpanded.has(chapterNumber)) {
      newExpanded.delete(chapterNumber)
    } else {
      newExpanded.add(chapterNumber)
    }
    setExpandedChapters(newExpanded)
  }

  return (
    <div className="space-y-6">
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
          <h1 className="text-2xl font-bold text-gray-900 dark:text-white">
            大纲编辑
          </h1>
          {(workflowOutline || workflowChapterOutlines?.length > 0) && (
            <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
              {workflowOutline && '包含工作流生成的剧情大纲 '}
              {workflowChapterOutlines?.length > 0 && `和 ${workflowChapterOutlines.length} 章的细纲`}
            </p>
          )}
        </div>
        <button className="flex items-center gap-2 px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700">
          <Sparkles className="h-5 w-5" />
          AI生成大纲
        </button>
      </div>

      {/* 工作流生成的大纲 */}
      {workflowOutline && (
        <div className="bg-white dark:bg-gray-800 rounded-xl shadow-sm border border-gray-200 dark:border-gray-700 overflow-hidden">
          <div className="p-4 border-b border-gray-200 dark:border-gray-700 flex items-center gap-2 bg-purple-50 dark:bg-purple-900/20">
            <Sparkles className="h-5 w-5 text-purple-600" />
            <h3 className="font-semibold text-gray-900 dark:text-white">工作流生成的剧情大纲</h3>
          </div>
          
          <div className="p-4 space-y-4">
            {/* 总体概述 */}
            {workflowOutline.overview && (
              <div className="p-4 bg-blue-50 dark:bg-blue-900/20 rounded-lg">
                <h4 className="font-medium text-blue-900 dark:text-blue-300 mb-2">故事概述</h4>
                <p className="text-sm text-blue-800 dark:text-blue-300">{workflowOutline.overview}</p>
              </div>
            )}

            {/* 分卷大纲 */}
            {workflowOutline.volumes && workflowOutline.volumes.length > 0 && (
              <div className="space-y-3">
                {workflowOutline.volumes.map((volume: any, vIndex: number) => (
                  <div key={vIndex} className="border border-gray-200 dark:border-gray-700 rounded-lg">
                    <button
                      onClick={() => toggleVolume(volume.volume_number)}
                      className="w-full px-4 py-3 flex items-center justify-between hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors"
                    >
                      <div className="flex items-center gap-3">
                        {expandedVolumes.has(volume.volume_number) ? (
                          <ChevronDown className="h-4 w-4 text-gray-400" />
                        ) : (
                          <ChevronRight className="h-4 w-4 text-gray-400" />
                        )}
                        <span className="font-medium text-gray-900 dark:text-white">
                          第{volume.volume_number}卷: {volume.title}
                        </span>
                      </div>
                      <span className="text-sm text-gray-500">
                        {volume.chapters?.length || 0} 章
                      </span>
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
                            {chapter.summary && (
                              <p className="text-xs text-gray-500 dark:text-gray-400 ml-6 mt-1">
                                {chapter.summary}
                              </p>
                            )}
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}

            {/* 剧情弧光 */}
            {workflowOutline.arcs && workflowOutline.arcs.length > 0 && (
              <div>
                <h4 className="font-medium text-gray-900 dark:text-white mb-2">剧情弧光</h4>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                  {workflowOutline.arcs.map((arc: Arc, index: number) => (
                    <div key={index} className="p-3 bg-gray-50 dark:bg-gray-700/50 rounded-lg">
                      <div className="flex items-start justify-between mb-2">
                        <h5 className="font-medium text-gray-900 dark:text-white text-sm">
                          {arc.title}
                        </h5>
                        <span className="text-xs text-gray-500">
                          第{arc.start_chapter}-{arc.end_chapter}章
                        </span>
                      </div>
                      <p className="text-xs text-gray-600 dark:text-gray-400 mb-2">
                        {arc.description}
                      </p>
                      {arc.key_events && arc.key_events.length > 0 && (
                        <div className="flex flex-wrap gap-1">
                          {arc.key_events.slice(0, 3).map((event, i) => (
                            <span
                              key={i}
                              className="text-xs px-2 py-0.5 bg-white dark:bg-gray-600 rounded text-gray-600 dark:text-gray-300"
                            >
                              {event}
                            </span>
                          ))}
                          {arc.key_events.length > 3 && (
                            <span className="text-xs text-gray-500">+{arc.key_events.length - 3}</span>
                          )}
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

      {/* 章节细纲 */}
      {workflowChapterOutlines && workflowChapterOutlines.length > 0 && (
        <div className="bg-white dark:bg-gray-800 rounded-xl shadow-sm border border-gray-200 dark:border-gray-700 overflow-hidden">
          <div className="p-4 border-b border-gray-200 dark:border-gray-700 flex items-center gap-2 bg-green-50 dark:bg-green-900/20">
            <List className="h-5 w-5 text-green-600" />
            <h3 className="font-semibold text-gray-900 dark:text-white">章节细纲</h3>
            <span className="text-sm text-gray-500">共 {workflowChapterOutlines.length} 章</span>
          </div>
          
          <div className="p-4 space-y-3">
            {workflowChapterOutlines.map((chapter: any, index: number) => (
              <div key={index} className="border border-gray-200 dark:border-gray-700 rounded-lg">
                <button
                  onClick={() => toggleChapter(chapter.chapter_number)}
                  className="w-full px-4 py-3 flex items-center justify-between hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors"
                >
                  <div className="flex items-center gap-3">
                    {expandedChapters.has(chapter.chapter_number) ? (
                      <ChevronDown className="h-4 w-4 text-gray-400" />
                    ) : (
                      <ChevronRight className="h-4 w-4 text-gray-400" />
                    )}
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="font-medium text-gray-900 dark:text-white">
                          第{chapter.chapter_number}章
                        </span>
                        {chapter.title && (
                          <span className="text-gray-600 dark:text-gray-400">{chapter.title}</span>
                        )}
                      </div>
                      {chapter.summary && (
                        <p className="text-xs text-gray-500 dark:text-gray-400 mt-0.5 max-w-lg">
                          {chapter.summary}
                        </p>
                      )}
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <button
                      className="p-1 hover:bg-gray-200 dark:hover:bg-gray-600 rounded"
                      title="编辑"
                    >
                      <Edit className="h-4 w-4 text-gray-400" />
                    </button>
                  </div>
                </button>

                {expandedChapters.has(chapter.chapter_number) && (
                  <div className="px-4 pb-4 pt-2 border-t border-gray-200 dark:border-gray-700 space-y-3">
                    {/* 章节要点 */}
                    {chapter.key_points && chapter.key_points.length > 0 && (
                      <div>
                        <h5 className="text-sm font-medium text-gray-900 dark:text-white mb-2">章节要点</h5>
                        <ul className="text-sm text-gray-600 dark:text-gray-400 space-y-1 ml-4 list-disc">
                          {chapter.key_points.map((point: string, i: number) => (
                            <li key={i}>{point}</li>
                          ))}
                        </ul>
                      </div>
                    )}

                    {/* 角色出场 */}
                    {chapter.characters && chapter.characters.length > 0 && (
                      <div>
                        <h5 className="text-sm font-medium text-gray-900 dark:text-white mb-2">角色出场</h5>
                        <div className="flex flex-wrap gap-2">
                          {chapter.characters.map((char: string, i: number) => (
                            <span
                              key={i}
                              className="px-2 py-1 text-xs bg-blue-100 text-blue-700 rounded dark:bg-blue-900/30 dark:text-blue-400"
                            >
                              {char}
                            </span>
                          ))}
                        </div>
                      </div>
                    )}

                    {/* 关键事件 */}
                    {chapter.events && chapter.events.length > 0 && (
                      <div>
                        <h5 className="text-sm font-medium text-gray-900 dark:text-white mb-2">关键事件</h5>
                        <div className="space-y-1">
                          {chapter.events.map((event: any, i: number) => (
                            <div key={i} className="text-sm text-gray-600 dark:text-gray-400 flex items-start gap-2">
                              <span className="text-purple-600 dark:text-purple-400">•</span>
                              <span>{event.description}</span>
                              {event.chapter_ref && (
                                <span className="text-xs text-gray-500">（伏笔）</span>
                              )}
                            </div>
                          ))}
                        </div>
                      </div>
                    )}

                    {/* 场景设定 */}
                    {chapter.scenes && chapter.scenes.length > 0 && (
                      <div>
                        <h5 className="text-sm font-medium text-gray-900 dark:text-white mb-2">场景设定</h5>
                        <div className="space-y-2">
                          {chapter.scenes.map((scene: any, i: number) => (
                            <div key={i} className="text-sm text-gray-600 dark:text-gray-400">
                              <span className="font-medium">{scene.location}</span>
                              {scene.time && <span className="ml-2 text-gray-500">{scene.time}</span>}
                              {scene.purpose && (
                                <p className="text-xs text-gray-500 mt-1 ml-2">{scene.purpose}</p>
                              )}
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* 数据库中的大纲 */}
      {outlines.length === 0 && !workflowOutline && !workflowChapterOutlines?.length ? (
        <div className="text-center py-16 bg-white dark:bg-gray-800 rounded-xl border border-dashed border-gray-300 dark:border-gray-600">
          <BookOpen className="h-12 w-12 text-gray-400 mx-auto mb-4" />
          <h3 className="text-lg font-medium text-gray-900 dark:text-white mb-2">
            还没有大纲
          </h3>
          <p className="text-gray-500 dark:text-gray-400 mb-4">
            使用AI生成大纲或手动创建
          </p>
          <button className="px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700">
            生成大纲
          </button>
        </div>
      ) : outlines.length > 0 && (
        <div className="space-y-4">
          <h3 className="text-lg font-semibold text-gray-900 dark:text-white">已保存的大纲</h3>
          {outlines.map((outline: Outline) => (
            <div
              key={outline.id}
              className="bg-white dark:bg-gray-800 rounded-xl shadow-sm border border-gray-200 dark:border-gray-700 overflow-hidden"
            >
              {/* 卷标题 */}
              <button
                onClick={() => toggleVolume(outline.volume_number)}
                className="w-full px-6 py-4 flex items-center justify-between hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors"
              >
                <div className="flex items-center gap-4">
                  {expandedVolumes.has(outline.volume_number) ? (
                    <ChevronDown className="h-5 w-5 text-gray-400" />
                  ) : (
                    <ChevronRight className="h-5 w-5 text-gray-400" />
                  )}
                  <div>
                    <h3 className="text-lg font-semibold text-gray-900 dark:text-white">
                      第{outline.volume_number}卷: {outline.volume_title}
                    </h3>
                    <p className="text-sm text-gray-500 dark:text-gray-400">
                      {outline.actual_chapters} / {outline.target_chapters} 章
                      {outline.summary && ` · ${outline.summary}`}
                    </p>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <span className="text-sm text-gray-500">
                    {outline.arcs?.length || 0} 个剧情弧
                  </span>
                </div>
              </button>

              {/* 剧情弧详情 */}
              {expandedVolumes.has(outline.volume_number) && (
                <div className="border-t border-gray-200 dark:border-gray-700 px-6 py-4">
                  {outline.key_points && (
                    <div className="mb-4 p-3 bg-blue-50 dark:bg-blue-900/20 rounded-lg">
                      <p className="text-sm text-blue-800 dark:text-blue-300">
                        <strong>关键节点:</strong> {outline.key_points}
                      </p>
                    </div>
                  )}

                  <div className="space-y-3">
                    {outline.arcs?.map((arc: Arc, index: number) => (
                      <div
                        key={arc.arc_id || index}
                        className="p-4 bg-gray-50 dark:bg-gray-700/50 rounded-lg"
                      >
                        <div className="flex items-start justify-between mb-2">
                          <h4 className="font-medium text-gray-900 dark:text-white">
                            {arc.title}
                          </h4>
                          <span className="text-xs text-gray-500">
                            第{arc.start_chapter}-{arc.end_chapter}章
                          </span>
                        </div>
                        <p className="text-sm text-gray-600 dark:text-gray-400 mb-2">
                          {arc.description}
                        </p>
                        {arc.key_events && arc.key_events.length > 0 && (
                          <div className="flex flex-wrap gap-2">
                            {arc.key_events.map((event, i) => (
                              <span
                                key={i}
                                className="text-xs px-2 py-1 bg-white dark:bg-gray-600 rounded text-gray-600 dark:text-gray-300"
                              >
                                {event}
                              </span>
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
    </div>
  )
}
