import { useMemo, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Loader2, RefreshCw, TrendingUp, TrendingDown, Minus, Flame } from 'lucide-react'
import { rankApi } from '../services/api'

interface Genre { id: string; name: string; gender: string }
interface RankItem {
  rank: number
  rank_change: number
  book_id: string
  book_name: string
  author: string
  word_count: number
  read_count: number
  status: string
  last_chapter: string
  decode_ok: boolean
}

function fmtWan(n: number): string {
  if (!n) return '—'
  if (n >= 10000) return `${(n / 10000).toFixed(n >= 1000000 ? 0 : 1)}万`
  return String(n)
}

export function Rank() {
  const [gender, setGender] = useState<'male' | 'female'>('male')
  const [genreId, setGenreId] = useState<string>('')
  const [rankType, setRankType] = useState<'read' | 'new'>('read')
  const [top, setTop] = useState(20)

  const genresQuery = useQuery({ queryKey: ['rank-genres'], queryFn: () => rankApi.genres() })

  const genres = (genresQuery.data as { items?: Genre[] } | undefined)?.items || []
  const genderGenres = useMemo(() => genres.filter((g) => g.gender === gender), [genres, gender])

  // 频道切换时自动选中该频道第一个品类
  const activeGenreId = genreId && genderGenres.some((g) => g.id === genreId) ? genreId : genderGenres[0]?.id || ''

  const rankQuery = useQuery({
    queryKey: ['rank-fanqie', gender, activeGenreId, rankType, top],
    queryFn: () => rankApi.fanqie({ gender, genre_id: activeGenreId, rank_type: rankType, top }),
    enabled: activeGenreId !== '',
  })

  const items = (rankQuery.data as { items?: RankItem[] } | undefined)?.items || []
  const isLoading = rankQuery.isFetching
  const activeGenreName = genderGenres.find((g) => g.id === activeGenreId)?.name || ''

  const handleGender = (g: 'male' | 'female') => {
    setGender(g)
    setGenreId('')
  }

  const refresh = () => {
    rankApi.fanqie({ gender, genre_id: activeGenreId, genre: activeGenreName, rank_type: rankType, top, refresh: 1 })
      .catch(() => {})
      .finally(() => rankQuery.refetch())
  }

  const changeArrow = (c: number) =>
    c > 0 ? <span className="inline-flex items-center gap-0.5 text-red-500"><TrendingUp className="h-3.5 w-3.5" />{c}</span>
      : c < 0 ? <span className="inline-flex items-center gap-0.5 text-green-500"><TrendingDown className="h-3.5 w-3.5" />{-c}</span>
      : <span className="text-gray-400 inline-flex items-center gap-0.5"><Minus className="h-3.5 w-3.5" />0</span>

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 dark:text-white flex items-center gap-2">
            <Flame className="h-6 w-6 text-orange-500" /> 番茄扫榜台
          </h1>
          <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
            番茄小说公开榜单 · 37 品类 × 阅读/新书双榜 · 字体混淆已解码 · 当日快照缓存
          </p>
        </div>
        <button
          onClick={refresh}
          disabled={isLoading}
          className="flex items-center gap-2 px-4 py-2 text-sm font-medium bg-primary-600 text-white rounded-lg hover:bg-primary-700 disabled:opacity-50"
        >
          {isLoading ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCw className="h-4 w-4" />}
          实时刷新
        </button>
      </div>

      {/* 筛选栏 */}
      <div className="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 p-4 flex flex-wrap items-center gap-4">
        <div className="flex rounded-lg overflow-hidden border border-gray-200 dark:border-gray-700">
          {(['male', 'female'] as const).map((g) => (
            <button
              key={g}
              onClick={() => handleGender(g)}
              className={`px-4 py-1.5 text-sm font-medium ${
                gender === g
                  ? 'bg-primary-600 text-white'
                  : 'bg-white dark:bg-gray-800 text-gray-600 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-700'
              }`}
            >
              {g === 'male' ? '男频' : '女频'}
            </button>
          ))}
        </div>

        <select
          value={activeGenreId}
          onChange={(e) => setGenreId(e.target.value)}
          className="px-3 py-1.5 text-sm bg-gray-50 dark:bg-gray-700 border border-gray-200 dark:border-gray-600 rounded-lg text-gray-900 dark:text-white"
        >
          {genderGenres.map((g) => (
            <option key={g.id} value={g.id}>{g.name}</option>
          ))}
        </select>

        <div className="flex rounded-lg overflow-hidden border border-gray-200 dark:border-gray-700">
          {(['read', 'new'] as const).map((t) => (
            <button
              key={t}
              onClick={() => setRankType(t)}
              className={`px-4 py-1.5 text-sm font-medium ${
                rankType === t
                  ? 'bg-indigo-600 text-white'
                  : 'bg-white dark:bg-gray-800 text-gray-600 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-700'
              }`}
            >
              {t === 'read' ? '阅读榜' : '新书榜'}
            </button>
          ))}
        </div>

        <select
          value={top}
          onChange={(e) => setTop(Number(e.target.value))}
          className="px-3 py-1.5 text-sm bg-gray-50 dark:bg-gray-700 border border-gray-200 dark:border-gray-600 rounded-lg text-gray-900 dark:text-white"
        >
          {[10, 20, 50].map((n) => <option key={n} value={n}>Top {n}</option>)}
        </select>

        <span className="text-xs text-gray-400 ml-auto">
          {activeGenreName} · {rankType === 'read' ? '阅读榜（30万字以上）' : '新书榜（30万字以下）'} · 今日快照
        </span>
      </div>

      {/* 榜单表 */}
      <div className="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 overflow-hidden">
        {isLoading && items.length === 0 ? (
          <div className="flex justify-center items-center h-48">
            <Loader2 className="h-8 w-8 animate-spin text-primary-600" />
          </div>
        ) : items.length === 0 ? (
          <div className="text-center py-16 text-sm text-gray-400">
            <p>暂无榜单数据</p>
            <p className="mt-1">首次进入会自动拉取，稍等片刻或点「实时刷新」</p>
          </div>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-gray-500 dark:text-gray-400 border-b border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-900/50">
                <th className="px-4 py-3 w-20">排名</th>
                <th className="px-4 py-3">书名</th>
                <th className="px-4 py-3 w-32">作者</th>
                <th className="px-4 py-3 text-right w-24">字数</th>
                <th className="px-4 py-3 text-right w-24">平台读数</th>
                <th className="px-4 py-3 w-16">状态</th>
                <th className="px-4 py-3 hidden lg:table-cell">最新章节</th>
              </tr>
            </thead>
            <tbody>
              {items.map((b) => (
                <tr key={b.book_id} className="border-b border-gray-100 dark:border-gray-700/60 hover:bg-gray-50 dark:hover:bg-gray-700/40">
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-1.5">
                      <span className={`font-bold ${b.rank <= 3 ? 'text-orange-500' : 'text-gray-700 dark:text-gray-300'}`}>
                        {b.rank}
                      </span>
                      {changeArrow(b.rank_change)}
                    </div>
                  </td>
                  <td className="px-4 py-3 font-medium text-gray-900 dark:text-white max-w-[260px] truncate" title={b.book_name}>
                    {b.book_name}
                  </td>
                  <td className="px-4 py-3 text-gray-600 dark:text-gray-300 truncate max-w-[140px]">{b.author}</td>
                  <td className="px-4 py-3 text-right text-gray-600 dark:text-gray-300">{fmtWan(b.word_count)}</td>
                  <td className="px-4 py-3 text-right text-gray-600 dark:text-gray-300">{fmtWan(b.read_count)}</td>
                  <td className="px-4 py-3">
                    <span className={`px-1.5 py-0.5 rounded text-[11px] font-medium ${
                      b.status === '连载'
                        ? 'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/40 dark:text-emerald-300'
                        : 'bg-gray-100 text-gray-600 dark:bg-gray-700 dark:text-gray-300'
                    }`}>{b.status}</span>
                  </td>
                  <td className="px-4 py-3 hidden lg:table-cell text-gray-500 dark:text-gray-400 max-w-[220px] truncate" title={b.last_chapter}>
                    {b.last_chapter || '—'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      <p className="text-xs text-gray-400">
        说明：平台公开榜单接口返回的书名/作者为字体混淆文本，本系统已做逐字解码（decode_ok）。「平台读数」为接口 read_count 原值，与官方榜规「仅排 1000 在读以上」不一致，热度判断以名次为主。
      </p>
    </div>
  )
}
