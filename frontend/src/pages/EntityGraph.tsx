import { useMemo, useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { Search, Network, ArrowLeft, Boxes, Sparkles } from 'lucide-react'
import { worldApi } from '../services/api'
import type { WorldData, Character, WorldEntity } from '../types'
import { ForceGraph, KIND_COLORS, type GraphNodeInput, type GraphEdgeInput } from '../components/ForceGraph'
import { NovelNav } from '../components/NovelNav'
import { entityMeta } from './sharedEntityMeta'
import { EntityDetailPanel } from '../components/EntityDetailPanel'

const ROLE_LABEL: Record<string, string> = {
  protagonist: '主角',
  antagonist: '反派',
  supporting: '配角',
  minor: '龙套',
}

export function EntityGraph() {
  const { novelId } = useParams<{ novelId: string }>()
  const id = parseInt(novelId || '0')

  const [activeKinds, setActiveKinds] = useState<Set<string> | null>(null)
  const [search, setSearch] = useState('')
  const [selectedId, setSelectedId] = useState<string | null>(null)

  const { data: world, isLoading } = useQuery({
    queryKey: ['world', id],
    queryFn: () => worldApi.get(id),
    enabled: !!id,
  })

  // 基础节点/边（不经筛选，用于详情邻居查询保持完整上下文）
  const graph = useMemo(() => buildGraph(world), [world])
  const kindCounts = useMemo(() => {
    const m: Record<string, number> = {}
    for (const n of graph.nodes) m[n.kind] = (m[n.kind] || 0) + 1
    return m
  }, [graph])

  // 首次渲染后自动选中全部类型；筛选只降级，不额外决策
  const effectiveKinds = activeKinds ?? new Set(Object.keys(kindCounts).filter(k => kindCounts[k] > 0))

  const filteredNodes = useMemo(() => {
    const q = search.trim().toLowerCase()
    return graph.nodes.filter(n => {
      if (!effectiveKinds.has(n.kind)) return false
      if (!q) return true
      const hay = [n.label, ...(n.data.aliases || []), n.data.summary || ''].join(' ').toLowerCase()
      return hay.includes(q)
    })
  }, [graph, effectiveKinds, search])

  const filteredEdges = useMemo(() => {
    const ids = new Set(filteredNodes.map(n => n.id))
    return graph.edges.filter(e => ids.has(e.source) && ids.has(e.target))
  }, [graph, filteredNodes])

  const selected = selectedId ? graph.nodeById.get(selectedId) : undefined
  const neighbors = useMemo(() => {
    if (!selectedId) return []
    const out: { id: string; label: string; color?: string; relation?: string }[] = []
    const seen = new Set<string>()
    for (const e of graph.edges) {
      if (e.source === selectedId || e.target === selectedId) {
        const other = e.source === selectedId ? e.target : e.source
        if (seen.has(other)) continue
        seen.add(other)
        const otherNode = graph.nodeById.get(other)
        if (otherNode) {
          out.push({
            id: other,
            label: otherNode.label,
            color: KIND_COLORS[otherNode.kind],
            relation: e.relation,
          })
        }
      }
    }
    return out
  }, [graph, selectedId])

  // 切换类型筛选
  const toggleKind = (kind: string) => {
    setActiveKinds(prev => {
      const base = prev ?? new Set(Object.keys(kindCounts).filter(k => kindCounts[k] > 0))
      const next = new Set(base)
      if (next.has(kind)) next.delete(kind)
      else next.add(kind)
      return next
    })
  }

  const allKinds = Object.keys(kindCounts).filter(k => kindCounts[k] > 0)

  return (
    <div className="space-y-5">
      <div className="flex items-center gap-3 flex-wrap">
        <Link
          to={`/novel/${id}`}
          className="inline-flex items-center gap-1.5 text-sm text-gray-500 dark:text-gray-400 hover:text-primary-600 dark:hover:text-primary-400 transition-colors"
        >
          <ArrowLeft className="h-4 w-4" />
          返回
        </Link>
        <NovelNav />
      </div>

      <div className="flex items-center justify-between gap-4 flex-wrap">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 dark:text-white flex items-center gap-2">
            <Network className="h-6 w-6 text-primary-600" />
            实体图谱
          </h1>
          <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
            角色与势力的关系网自动布局，点击任意节点查看详情与关联
          </p>
        </div>
        <Link
          to={`/novel/${id}/entities`}
          className="inline-flex items-center gap-1.5 px-3 py-2 rounded-lg text-sm bg-gray-100 dark:bg-gray-800 text-gray-700 dark:text-gray-200 hover:bg-gray-200 dark:hover:bg-gray-700 transition-colors"
        >
          <Boxes className="h-4 w-4" />
          实体管理
        </Link>
      </div>

      {/* 工具栏：搜索 + 类型筛选（默认全选） */}
      <div className="flex flex-col gap-3">
        <div className="relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400" />
          <input
            value={search}
            onChange={e => setSearch(e.target.value)}
            placeholder="搜索名称、别名、摘要…"
            className="w-full pl-10 pr-4 py-2 rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 text-sm text-gray-900 dark:text-white placeholder-gray-400 dark:placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-primary-500"
          />
        </div>
        {allKinds.length > 1 && (
          <div className="flex flex-wrap gap-2">
            {allKinds.map(kind => {
              const meta = entityMeta(kind)
              const on = effectiveKinds.has(kind)
              return (
                <button
                  key={kind}
                  onClick={() => toggleKind(kind)}
                  className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium border transition-colors ${
                    on
                      ? 'text-white border-transparent'
                      : 'border-gray-300 dark:border-gray-600 text-gray-500 dark:text-gray-400 hover:border-gray-400'
                  }`}
                  style={{ background: on ? meta.color : 'transparent' }}
                >
                  <span className="w-2 h-2 rounded-full" style={{ background: on ? '#fff' : meta.color }} />
                  {meta.label} {kindCounts[kind]}
                </button>
              )
            })}
          </div>
        )}
      </div>

      {isLoading ? (
        <div className="flex items-center justify-center h-96 text-gray-400">
          <Sparkles className="h-8 w-8 animate-pulse mr-2" /> 加载中…
        </div>
      ) : (
        <div className="relative">
          <ForceGraph
            nodeInputs={filteredNodes}
            edgeInputs={filteredEdges}
            selectedId={selectedId}
            onSelect={setSelectedId}
            height={600}
            emptyState={
              <div className="text-center py-16">
                <Network className="w-12 h-12 mx-auto mb-3 text-gray-400" />
                {search ? (
                  <p className="text-gray-500">没有匹配的实体</p>
                ) : (
                  <>
                    <p className="text-gray-500 mb-3">还没有世界观数据</p>
                    <Link
                      to={`/novel/${id}/entities`}
                      className="inline-flex items-center gap-1.5 px-4 py-2 rounded-lg bg-primary-600 text-white text-sm hover:bg-primary-500"
                    >
                      <Sparkles className="h-4 w-4" /> 去「实体管理」创建
                    </Link>
                  </>
                )}
              </div>
            }
          />
          {selected && (
            <div className="absolute right-3 top-3 z-10">
              <EntityDetailPanel
                kind={selected.kind}
                kindLabel={entityMeta(selected.kind).label}
                color={KIND_COLORS[selected.kind] || '#8b5cf6'}
                name={selected.label}
                aliases={selected.data.aliases}
                summary={selected.data.summary}
                state={selected.data.state}
                fields={entityMeta(selected.kind).fields}
                metas={selected.data.metas}
                neighbors={neighbors}
                onNeighborClick={setSelectedId}
                onClose={() => setSelectedId(null)}
              />
            </div>
          )}
        </div>
      )}

      <p className="text-xs text-gray-400 dark:text-gray-500">
        节点可拖动 · 悬停高亮关联 · 滚轮缩放 · 双击空白处适应视图
      </p>
    </div>
  )
}

interface GraphResult {
  nodes: GraphNodeInput[]
  edges: GraphEdgeInput[]
  nodeById: Map<string, { label: string; kind: string; data?: any }>
}

function buildGraph(world?: WorldData): GraphResult {
  if (!world) return { nodes: [], edges: [], nodeById: new Map() }

  const nodes: GraphNodeInput[] = []
  const nodeById = new Map<string, { label: string; kind: string; data?: any }>()

  const pushNode = (n: GraphNodeInput) => {
    nodes.push(n)
    nodeById.set(n.id, { label: n.label, kind: n.kind, data: n.data })
  }

  for (const c of world.characters) {
    pushNode({
      id: `char:${c.id}`,
      label: c.name,
      kind: 'character',
      sublabel: [ROLE_LABEL[c.role_type] || c.role_type, `第${c.first_appearance}章`].filter(Boolean).join(' · '),
      data: { kind: 'character', ...charState(c) },
    })
  }

  for (const e of world.entities) {
    const kind = e.entity_type === 'character' ? 'character' : e.entity_type
    pushNode({
      id: `ent:${e.entity_id}`,
      label: e.canonical_name,
      kind,
      sublabel: e.last_mentioned_chapter_number ? `第${e.last_mentioned_chapter_number}章` : undefined,
      data: { kind: e.entity_type, ...entState(e) },
    })
  }

  const edges: GraphEdgeInput[] = []
  const edgeKey = new Set<string>()
  const addEdge = (source: string, target: string, relation?: string) => {
    const key = `${source}@@${target}`
    if (edgeKey.has(key) || source === target) return
    edgeKey.add(key)
    edges.push({ id: `e-${key}`, source, target, relation })
  }

  for (const r of world.relationships) {
    addEdge(`ent:${r.source_id}`, `ent:${r.target_id}`, r.relation_type)
  }
  for (let i = 0; i < world.character_edges.length; i++) {
    const ce = world.character_edges[i]
    addEdge(`char:${ce.source}`, `char:${ce.target}`, ce.relation || '关联')
  }
  // 角色表与实体表同名 → 建立“同一存在”的桥接边，让两张网合并成一张
  const entityByName = new Map(world.entities.map(e => [e.canonical_name, e]))
  for (const c of world.characters) {
    const matched = entityByName.get(c.name)
    if (matched) addEdge(`char:${c.id}`, `ent:${matched.entity_id}`, '同一人物')
  }

  // 过滤：实体抽取会把章节里出现的路人甲也建出 character 实体（黄毛、收债头子等），
  // 这些零关联的角色会淹没有关角色管理页的 8 位正式角色。
  // 规则：character 实体只有「有实体关系边」或「与角色表同名」才上图，其余丢弃。
  const charsDbNames = new Set(world.characters.map(c => c.name))
  const entityCharUsed = new Set<string>()
  for (const e of edges) {
    if (e.source.startsWith('ent:')) entityCharUsed.add(e.source)
    if (e.target.startsWith('ent:')) entityCharUsed.add(e.target)
  }
  const keptNodes = nodes.filter(n => {
    if (n.kind !== 'character' || n.id.startsWith('char:')) return true
    const isBridged = charsDbNames.has(n.label)
    return isBridged || entityCharUsed.has(n.id)
  })
  const keptIds = new Set(keptNodes.map(n => n.id))
  const keptEdges = edges.filter(e => keptIds.has(e.source) && keptIds.has(e.target))

  return { nodes: keptNodes, edges: keptEdges, nodeById }
}

function charState(c: Character) {
  const profile = c.profile || {}
  const state: Record<string, unknown> = {}
  for (const [k, v] of Object.entries(profile)) {
    if (k !== 'relationships' && k !== 'name') state[k] = v
  }
  if (!('role' in state)) state.role_type = c.role_type
  return {
    state,
    aliases: [] as string[],
    summary: profile.background ? String(profile.background) : undefined,
    metas: [
      { label: '出场', value: `第${c.first_appearance}章` },
      { label: '出现次数', value: String(c.appearance_count) },
    ],
  }
}

function entState(e: WorldEntity) {
  return {
    state: e.state_vector || {},
    aliases: e.aliases || [],
    summary: e.narrative_summary,
    metas: e.last_mentioned_chapter_number
      ? [{ label: '最后提及', value: `第${e.last_mentioned_chapter_number}章` }]
      : [],
  }
}