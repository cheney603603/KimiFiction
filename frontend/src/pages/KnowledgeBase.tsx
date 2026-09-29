import { useMemo, useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { Library, ArrowLeft, Search, BookOpen, Network } from 'lucide-react'
import { worldApi } from '../services/api'
import type { WorldData } from '../types'
import { WORLD_KIND_META } from '../components/worldConfig'
import { NovelNav } from '../components/NovelNav'
import { entityMeta } from './sharedEntityMeta'
import { EntityDetailPanel, type DetailNeighbor } from '../components/EntityDetailPanel'

const GROUP_ORDER = ['character', 'faction', 'location', 'item', 'skill', 'memory', 'arc']

function groupLabel(group: string): string {
  if (group === 'memory') return '记忆'
  if (group === 'arc') return '大纲'
  return WORLD_KIND_META[group]?.label || group
}

interface KbItem {
  id: string
  kind: string
  group: string
  title: string
  aliases?: string[]
  summary?: string
  state: Record<string, unknown>
  metas: { label: string; value: string }[]
  corp: string
}

export function KnowledgeBase() {
  const { novelId } = useParams<{ novelId: string }>()
  const id = parseInt(novelId || '0')
  const [search, setSearch] = useState('')
  const [selectedId, setSelectedId] = useState<string | null>(null)

  const { data: world, isLoading } = useQuery({
    queryKey: ['world', id],
    queryFn: () => worldApi.get(id),
    enabled: !!id,
  })

  const kb = useMemo(() => buildKb(world), [world])
  const itemsById = useMemo(() => new Map(kb.map(i => [i.id, i])), [kb])

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase()
    if (!q) return kb
    return kb.filter(i => i.corp.includes(q))
  }, [kb, search])

  const grouped = useMemo(() => {
    const g = new Map<string, KbItem[]>()
    for (const it of filtered) {
      if (!g.has(it.group)) g.set(it.group, [])
      g.get(it.group)!.push(it)
    }
    for (const list of g.values()) {
      list.sort((a, b) => a.title.localeCompare(b.title, 'zh'))
    }
    return g
  }, [filtered])

  // 无选择时默认显示第一条（零决策，始终有内容可看）
  const current = selectedId ? itemsById.get(selectedId) : undefined
  const detailItem = current || filtered[0]

  const groupsToShow = GROUP_ORDER.filter(g => grouped.has(g))
  const totalCount = kb.length

  const neighbors = useMemo(() => {
    if (!detailItem) return []
    const out: DetailNeighbor[] = []
    const seen = new Set<string>()
    const push = (id: string) => {
      const n = itemsById.get(id)
      if (!n || seen.has(id)) return
      seen.add(id)
      out.push({
        id,
        label: n.title,
        color: entityMeta(n.kind).color,
        relation: undefined,
      })
    }
    if (detailItem.group === 'memory') {
      for (const name of world?.memory_nodes.find(m => `mem:${m.id}` === detailItem.id)?.related_characters || []) {
        const hit = kb.find(i => (i.group === 'character' || i.group === 'faction') && i.title === name)
        if (hit) push(hit.id)
      }
      for (const name of world?.memory_nodes.find(m => `mem:${m.id}` === detailItem.id)?.related_locations || []) {
        const hit = kb.find(i => i.group === 'location' && i.title === name)
        if (hit) push(hit.id)
      }
    } else {
      for (const e of graphEdges(world, detailItem.id)) {
        push(e)
      }
    }
    return out
  }, [detailItem, itemsById, kb, world])

  return (
    <div className="space-y-5">
      <div className="flex items-center gap-3 flex-wrap">
        <Link
          to={`/novel/${id}`}
          className="inline-flex items-center gap-1.5 text-sm text-gray-500 dark:text-gray-400 hover:text-primary-600 dark:hover:text-primary-400 transition-colors"
        >
          <ArrowLeft className="h-4 w-4" /> 返回
        </Link>
        <NovelNav />
      </div>

      <div>
        <h1 className="text-2xl font-bold text-gray-900 dark:text-white flex items-center gap-2">
          <Library className="h-6 w-6 text-primary-600" />
          世界观知识库
        </h1>
        <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
          角色、势力、地点、物品、技能、记忆与伏笔的统一检索，共 {totalCount} 条
        </p>
      </div>

      {/* 统计条 */}
      <div className="flex flex-wrap gap-2">
        {allItemsGroups(kb).map(g => (
          <span
            key={g.label}
            className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-medium bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 text-gray-600 dark:text-gray-300"
          >
            <span className="w-2 h-2 rounded-full" style={{ background: g.color }} />
            {g.label} {g.count}
          </span>
        ))}
      </div>

      {/* 搜索 */}
      <div className="relative">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400" />
        <input
          value={search}
          onChange={e => setSearch(e.target.value)}
          placeholder="搜索全部世界设定（名称、别名、摘要、内容）…"
          className="w-full pl-10 pr-4 py-2 rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 text-sm text-gray-900 dark:text-white placeholder-gray-400 dark:placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-primary-500"
        />
      </div>

      {isLoading ? (
        <div className="flex items-center justify-center h-64 text-gray-400">
          <BookOpen className="h-8 w-8 animate-pulse mr-2" /> 加载中…
        </div>
      ) : filtered.length === 0 ? (
        <div className="text-center py-16 bg-white dark:bg-gray-800 rounded-xl border border-dashed border-gray-300 dark:border-gray-600">
          <Network className="w-12 h-12 mx-auto mb-3 text-gray-400" />
          <p className="text-gray-500">没有匹配的内容，试试其他关键词</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-[minmax(0,340px)_minmax(0,1fr)] gap-4 items-start">
          {/* 左侧列表 */}
          <div className="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 overflow-hidden">
            <div className="max-h-[640px] overflow-y-auto divide-y divide-gray-100 dark:divide-gray-700/60">
              {groupsToShow.map(group => (
                <div key={group}>
                  <div className="sticky top-0 z-10 bg-white dark:bg-gray-800 px-4 py-1.5 text-xs font-semibold text-gray-500 dark:text-gray-400 border-b border-gray-100 dark:border-gray-700/60">
                    {groupLabel(group)} · {grouped.get(group)!.length}
                  </div>
                  {grouped.get(group)!.map(item => (
                    <button
                      key={item.id}
                      onClick={() => setSelectedId(item.id)}
                      className={`w-full text-left px-4 py-2.5 transition-colors ${
                        detailItem?.id === item.id
                          ? 'bg-primary-50 dark:bg-primary-900/30'
                          : 'hover:bg-gray-50 dark:hover:bg-gray-700/40'
                      }`}
                    >
                      <div className="flex items-center gap-2 min-w-0">
                        <span
                          className="shrink-0 w-2 h-2 rounded-full"
                          style={{ background: entityMeta(item.kind).color }}
                        />
                        <span className="truncate text-sm font-medium text-gray-900 dark:text-gray-100">
                          {item.title}
                        </span>
                      </div>
                      {item.summary && (
                        <p className="pl-4 text-xs text-gray-400 dark:text-gray-500 truncate mt-0.5">
                          {item.summary}
                        </p>
                      )}
                    </button>
                  ))}
                </div>
              ))}
            </div>
          </div>

          {/* 右侧详情 */}
          {detailItem && (
            <EntityDetailPanel
              kind={detailItem.kind}
              kindLabel={entityMeta(detailItem.kind).label}
              color={entityMeta(detailItem.kind).color}
              name={detailItem.title}
              aliases={detailItem.aliases}
              summary={detailItem.summary}
              state={detailItem.state}
              fields={entityMeta(detailItem.kind).fields}
              metas={detailItem.metas}
              neighbors={neighbors}
              onNeighborClick={setSelectedId}
            />
          )}
        </div>
      )}
    </div>
  )
}

function buildKb(world?: WorldData): KbItem[] {
  if (!world) return []
  const items: KbItem[] = []

  const push = (
    id: string,
    kind: string,
    group: string,
    title: string,
    aliases: string[] | undefined,
    summary: string | undefined,
    state: Record<string, unknown>,
    metas: { label: string; value: string }[],
  ) => {
    const corp = [title, ...(aliases || []), summary || '', ...metas.map(m => m.value), ...Object.values(state).join(' ')]
      .join(' ')
      .toLowerCase()
    items.push({ id, kind, group, title, aliases, summary, state, metas, corp })
  }

  for (const c of world.characters) {
    const profile = c.profile || {}
    const state: Record<string, unknown> = {}
    for (const [k, v] of Object.entries(profile)) if (k !== 'relationships') state[k] = v
    push(
      `char:${c.id}`,
      'character',
      'character',
      c.name,
      undefined,
      profile.background ? String(profile.background) : undefined,
      state,
      [
        { label: '类型', value: entityMeta('character').label },
        { label: '出场', value: `第${c.first_appearance}章` },
        { label: '出现次数', value: String(c.appearance_count) },
      ],
    )
  }

  // 角色以 characters 表为准，同名实体角色不再重复列出（避免知识库角色数虚高）
  const dbCharNames = new Set(world.characters.map(c => c.name))

  for (const e of world.entities) {
    if (e.entity_type === 'character' && dbCharNames.has(e.canonical_name)) continue
    const kind = e.entity_type === 'character' ? 'character' : e.entity_type
    push(
      `ent:${e.entity_id}`,
      kind,
      e.entity_type,
      e.canonical_name,
      e.aliases || [],
      e.narrative_summary,
      e.state_vector || {},
      e.last_mentioned_chapter_number ? [{ label: '最后提及', value: `第${e.last_mentioned_chapter_number}章` }] : [],
    )
  }

  for (const m of world.memory_nodes) {
    push(
      `mem:${m.id}`,
      'memory',
      'memory',
      m.title,
      undefined,
      m.content,
      {},
      [
        { label: '章节', value: m.chapter_range },
        { label: '重要性', value: `${Math.round((m.importance_score || 0) * 100)}%` },
        ...(m.is_resolved ? [{ label: '状态', value: '已回收' }] : []),
      ],
    )
    // 追加到 corp：搜索命中记忆的关联字段
  }

  world.outlines.forEach((o, vi) => {
    ;(o.arcs || []).forEach((arc: any, ai: number) => {
      const range = arc.start_chapter && arc.end_chapter ? `第${arc.start_chapter}-${arc.end_chapter}章` : ''
      push(
        `arc:${vi}-${ai}`,
        'arc',
        'arc',
        arc.title || arc.arc_id || `剧情弧 ${ai + 1}`,
        undefined,
        arc.description,
        arc.key_events ? { 关键事件: arc.key_events } : {},
        range ? [{ label: '章节', value: range }] : [],
      )
    })
  })

  return items
}

function graphEdges(world: WorldData | undefined, itemId: string): string[] {
  if (!world) return []
  const out: string[] = []
  const hit = new Set<string>()
  const add = (x: string) => {
    if (!hit.has(x)) {
      hit.add(x)
      out.push(x)
    }
  }
  for (const r of world.relationships) {
    if (`ent:${r.source_id}` === itemId) add(`ent:${r.target_id}`)
    if (`ent:${r.target_id}` === itemId) add(`ent:${r.source_id}`)
  }
  for (const ce of world.character_edges) {
    if (`char:${ce.source}` === itemId) add(`char:${ce.target}`)
    if (`char:${ce.target}` === itemId) add(`char:${ce.source}`)
  }
  // 角色 ↔ 同名实体桥接
  const entByName = new Map(world.entities.map(e => [e.canonical_name, e]))
  const charByName = new Map(world.characters.map(c => [c.name, c]))
  if (itemId.startsWith('char:')) {
    const c = world.characters.find(x => `char:${x.id}` === itemId)
    const e = c && entByName.get(c.name)
    if (e) add(`ent:${e.entity_id}`)
  } else if (itemId.startsWith('ent:')) {
    const e = world.entities.find(x => `ent:${x.entity_id}` === itemId)
    const c = e && charByName.get(e.canonical_name)
    if (c) add(`char:${c.id}`)
  }
  return out
}

function allItemsGroups(kb: KbItem[]) {
  const counts = new Map<string, number>()
  for (const i of kb) counts.set(i.group, (counts.get(i.group) || 0) + 1)
  return GROUP_ORDER.filter(g => counts.has(g)).map(g => ({
    label: groupLabel(g),
    count: counts.get(g)!,
    color: g === 'memory' ? '#f43f5e' : g === 'arc' ? '#f97316' : WORLD_KIND_META[g]?.color || '#8b5cf6',
  }))
}