import { useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { ChevronLeft, ChevronRight, List, Settings, Moon, Sun, Type } from 'lucide-react'
import { novelApi, chapterApi } from '../services/api'

interface ReaderSettings {
  fontSize: number
  lineHeight: number
  darkMode: boolean
}

export function ChapterReader() {
  const { novelId, chapterNumber } = useParams<{ novelId: string; chapterNumber?: string }>()
  const id = parseInt(novelId || '0')
  const currentChapter = parseInt(chapterNumber || '1')

  const [settings, setSettings] = useState<ReaderSettings>({
    fontSize: 18,
    lineHeight: 1.8,
    darkMode: false,
  })
  const [showSettings, setShowSettings] = useState(false)
  const [showToc, setShowToc] = useState(false)

  const { data: novel } = useQuery({
    queryKey: ['novel', id],
    queryFn: () => novelApi.get(id),
    enabled: !!id,
  })

  const { data: chapter } = useQuery({
    queryKey: ['chapter', id, currentChapter],
    queryFn: () => chapterApi.getByNumber(id, currentChapter),
    enabled: !!id,
  })

  const { data: chaptersData } = useQuery({
    queryKey: ['chapters', id],
    queryFn: () => chapterApi.list(id, { limit: 1000 }),
    enabled: !!id,
  })

  const chapters = chaptersData?.items || []
  const totalChapters = novel?.total_chapters || 1

  const prevChapter = currentChapter > 1 ? currentChapter - 1 : null
  const nextChapter = currentChapter < totalChapters ? currentChapter + 1 : null

  if (!chapter) {
    return (
      <div className="flex justify-center items-center h-96">
        <div className="text-gray-500">加载中...</div>
      </div>
    )
  }

  return (
    <div className={`min-h-screen ${settings.darkMode ? 'dark bg-gray-900' : 'bg-[#f5f5f0]'}`}>
      {/* 顶部工具栏 */}
      <header className="sticky top-0 z-50 bg-white/90 dark:bg-gray-800/90 backdrop-blur border-b border-gray-200 dark:border-gray-700">
        <div className="max-w-4xl mx-auto px-4 h-14 flex items-center justify-between">
          <div className="flex items-center gap-4">
            <Link
              to={`/novel/${id}`}
              className="p-2 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-lg"
            >
              <ChevronLeft className="h-5 w-5 text-gray-600 dark:text-gray-400" />
            </Link>
            <button
              onClick={() => setShowToc(!showToc)}
              className="p-2 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-lg"
            >
              <List className="h-5 w-5 text-gray-600 dark:text-gray-400" />
            </button>
          </div>

          <h1 className="text-sm font-medium text-gray-700 dark:text-gray-300 truncate max-w-xs">
            {novel?.title}
          </h1>

          <div className="flex items-center gap-2">
            <button
              onClick={() => setSettings(s => ({ ...s, darkMode: !s.darkMode }))}
              className="p-2 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-lg"
            >
              {settings.darkMode ? (
                <Sun className="h-5 w-5 text-gray-400" />
              ) : (
                <Moon className="h-5 w-5 text-gray-600" />
              )}
            </button>
            <button
              onClick={() => setShowSettings(!showSettings)}
              className="p-2 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-lg"
            >
              <Settings className="h-5 w-5 text-gray-600 dark:text-gray-400" />
            </button>
          </div>
        </div>
      </header>

      <div className="max-w-4xl mx-auto flex">
        {/* 目录侧边栏 */}
        {showToc && (
          <aside className="w-64 fixed left-0 top-14 bottom-0 bg-white dark:bg-gray-800 border-r border-gray-200 dark:border-gray-700 overflow-y-auto z-40">
            <div className="p-4">
              <h3 className="font-semibold text-gray-900 dark:text-white mb-4">目录</h3>
              <nav className="space-y-1">
                {chapters.map((ch: any) => (
                  <Link
                    key={ch.id}
                    to={`/novel/${id}/read/${ch.chapter_number}`}
                    className={`block px-3 py-2 rounded-lg text-sm ${
                      ch.chapter_number === currentChapter
                        ? 'bg-primary-100 text-primary-700 dark:bg-primary-900 dark:text-primary-300'
                        : 'text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-700'
                    }`}
                  >
                    第{ch.chapter_number}章 {ch.title}
                  </Link>
                ))}
              </nav>
            </div>
          </aside>
        )}

        {/* 主内容区 */}
        <main className={`flex-1 px-4 py-8 ${showToc ? 'ml-64' : ''}`}>
          {/* 设置面板 */}
          {showSettings && (
            <div className="mb-6 p-4 bg-white dark:bg-gray-800 rounded-lg shadow-sm border border-gray-200 dark:border-gray-700">
              <div className="flex items-center gap-4">
                <Type className="h-5 w-5 text-gray-500" />
                <span className="text-sm text-gray-600 dark:text-gray-400">字体大小</span>
                <input
                  type="range"
                  min="14"
                  max="24"
                  value={settings.fontSize}
                  onChange={(e) => setSettings(s => ({ ...s, fontSize: parseInt(e.target.value) }))}
                  className="flex-1"
                />
                <span className="text-sm text-gray-600 dark:text-gray-400 w-8">{settings.fontSize}px</span>
              </div>
            </div>
          )}

          {/* 章节内容 */}
          <article className="bg-white dark:bg-gray-800 rounded-lg shadow-sm p-8 md:p-12">
            <h1 className="text-2xl md:text-3xl font-bold text-center text-gray-900 dark:text-white mb-2">
              第{chapter.chapter_number}章
            </h1>
            <h2 className="text-xl text-center text-gray-600 dark:text-gray-400 mb-8">
              {chapter.title}
            </h2>

            <div
              className="reader-content text-gray-800 dark:text-gray-200"
              style={{
                fontSize: `${settings.fontSize}px`,
                lineHeight: settings.lineHeight,
              }}
            >
              {chapter.content.split('\n').map((paragraph: string, index: number) => (
                <p key={index}>{paragraph}</p>
              ))}
            </div>
          </article>

          {/* 章节导航 */}
          <div className="flex justify-between mt-8">
            {prevChapter ? (
              <Link
                to={`/novel/${id}/read/${prevChapter}`}
                className="flex items-center gap-2 px-4 py-2 bg-white dark:bg-gray-800 rounded-lg shadow-sm border border-gray-200 dark:border-gray-700 text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-700"
              >
                <ChevronLeft className="h-5 w-5" />
                上一章
              </Link>
            ) : (
              <div />
            )}
            
            {nextChapter ? (
              <Link
                to={`/novel/${id}/read/${nextChapter}`}
                className="flex items-center gap-2 px-4 py-2 bg-white dark:bg-gray-800 rounded-lg shadow-sm border border-gray-200 dark:border-gray-700 text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-700"
              >
                下一章
                <ChevronRight className="h-5 w-5" />
              </Link>
            ) : (
              <div />
            )}
          </div>
        </main>
      </div>
    </div>
  )
}
