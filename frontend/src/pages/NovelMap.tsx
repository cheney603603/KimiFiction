import { useMemo, useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Map as MapIcon, ArrowLeft, Crosshair, Plus, X, Save, Sparkles } from 'lucide-react'
import { worldApi, entityApi } from '../services/api'
import type { WorldData, WorldEntity } from '../types'
import { ForceGraph, KIND_COLORS, type GraphNodeInput, type GraphEdgeInput } from '../components/ForceGraph'
import { NovelNav } from '../components/NovelNav'
import { entityMeta } from './sharedEntityMeta'
import { factionColor } from '../components/worldConfig'
import { EntityDetailPanel } from '../components/EntityDetailPanel'

export function NovelMap() {
  const { novelId } = useParams<{ novelId: string }>()
  const id = parseInt(novelId || '0')

  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [showAddLocation, setShowAddLocation] = useState(false)
  const queryClient = useQueryClient()

  const { data: world, isLoading } = useQuery({
    queryKey: ['world', id],
    queryFn: () => worldApi.get(id),
    enabled: !!id,
  })

  const map = useMemo(() => buildMap(world), [world])

  const selected = selectedId ? map.nodeById.get(selectedId) : undefined
  const neighbors = useMemo(() => {
    if (!selectedId) return []
    const out: { id: string; label: string; color?: string; relation?: string }[] = []
    const seen = new Set<string>()
    for (const e of map.edges) {
      if (e.source !== selectedId && e.target !== selectedId) continue
      const other = e.source === selectedId ? e.target : e.source
      if (seen.has(other)) continue
      seen.add(other)
      const n = map.nodeById.get(other)
      if (n) {
        out.push({ id: other, label: n.label, color: n.color, relation: e.relation })
      }
    }
    return out
  }, [map, selectedId])

  const refresh = () => queryClient.invalidateQueries({ queryKey: ['world', id] })

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

      <div className="flex items-center justify-between gap-4 flex-wrap">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 dark:text-white flex items-center gap-2">
            <MapIcon className="h-6 w-6 text-emerald-500" />
            小说地图
          </h1>
          <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
            地点与势力的版图关系：势力按领地自动着色，无需手动摆放
          </p>
        </div>
        <button
          onClick={() => setShowAddLocation(true)}
          className="inline-flex items-center gap-1.5 px-3 py-2 rounded-lg text-sm bg-primary-600 text-white hover:bg-primary-500 transition-colors"
        >
          <Plus className="h-4 w-4" /> 添加地点
        </button>
      </div>

      {/* 势力图例（自动生成） */}
      {map.factions.length > 0 && (
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-xs text-gray-500 dark:text-gray-400 flex items-center gap-1">
            <Crosshair className="h-3.5 w-3.5" /> 势力版图：
          </span>
          {map.factions.map(f => (
            <span
              key={f.id}
              className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium text-white"
              style={{ background: f.color }}
            >
              {f.label}
              {f.territoryCount > 0 && <span className="opacity-80">·{f.territoryCount}地</span>}
            </span>
          ))}
        </div>
      )}

      {isLoading ? (
        <div className="flex items-center justify-center h-96 text-gray-400">
          <Sparkles className="h-8 w-8 animate-pulse mr-2" /> 加载中…
        </div>
      ) : (
        <div className="relative">
          <ForceGraph
            nodeInputs={map.nodes}
            edgeInputs={map.edges}
            selectedId={selectedId}
            onSelect={setSelectedId}
            height={600}
            emptyState={
              <div className="text-center py-16">
                <MapIcon className="w-12 h-12 mx-auto mb-3 text-gray-400" />
                <p className="text-gray-500 mb-3">还没有地点。添加第一个地点，地图会自动生成</p>
                <button
                  onClick={() => setShowAddLocation(true)}
                  className="inline-flex items-center gap-1.5 px-4 py-2 rounded-lg bg-primary-600 text-white text-sm hover:bg-primary-500"
                >
                  <Plus className="h-4 w-4" /> 添加第一个地点
                </button>
              </div>
            }
          />
          {selected && (
            <div className="absolute right-3 top-3 z-10">
              <EntityDetailPanel
                kind={selected.kind}
                kindLabel={entityMeta(selected.kind).label}
                color={selected.color || KIND_COLORS[selected.kind] || '#10b981'}
                name={selected.label}
                aliases={selected.dataAliases}
                summary={selected.summary}
                state={selected.state}
                fields={entityMeta(selected.kind).fields}
                metas={selected.metas}
                neighbors={neighbors}
                onNeighborClick={setSelectedId}
                onClose={() => setSelectedId(null)}
              />
            </div>
          )}
        </div>
      )}

      {showAddLocation && (
        <AddLocationModal
          novelId={id}
          onClose={() => setShowAddLocation(false)}
          onSaved={() => {
            setShowAddLocation(false)
            refresh()
          }}
        />
      )}
    </div>
  )
}

interface MapNodeMeta {
  label: string
  kind: string
  color?: string
  dataAliases?: string[]
  summary?: string
  state: Record<string, unknown>
  metas: { label: string; value: string }[]
}

interface MapResult {
  nodes: GraphNodeInput[]
  edges: GraphEdgeInput[]
  nodeById: Map<string, MapNodeMeta>
  factions: { id: string; label: string; color: string; territoryCount: number }[]
}

function buildMap(world?: WorldData): MapResult {
  if (!world) {
    return { nodes: [], edges: [], nodeById: new Map<string, MapNodeMeta>(), factions: [] }
  }

  const locations = world.entities.filter(e => e.entity_type === 'location')
  const factions = world.entities.filter(e => e.entity_type === 'faction')

  const nodes: GraphNodeInput[] = []
  const nodeById = new Map<string, MapNodeMeta>()
  const locByKey = new Map<string, WorldEntity>(locations.map(l => [keyOf(l), l]))
  const nameToLoc = new Map<string, WorldEntity>()
  for (const l of locations) {
    nameToLoc.set(l.canonical_name.trim().toLowerCase(), l)
    for (const a of l.aliases || []) nameToLoc.set(a.trim().toLowerCase(), l)
  }

  // 势力配色（按出现顺序稳定）
  const factionColorMap = new Map<string, string>()
  factions.forEach((f, i) => factionColorMap.set(f.entity_id, factionColor(i)))

  // 地点归属势力：faction.territory 或 location.region 匹配
  const ownerOf = new Map<string, WorldEntity>()
  const factionTerritories = new Map<string, string[]>()
  for (const f of factions) {
    const terr: string[] = []
    const raw = f.state_vector?.territory
    if (raw) {
      const parts = Array.isArray(raw) ? raw.map(String) : String(raw).split(/[,，、]/)
      terr.push(...parts.map(p => p.trim()).filter(Boolean))
    }
    factionTerritories.set(f.entity_id, terr)
    for (const loc of locations) {
      if (territoryMatch(loc, terr) || regionMatch(loc, f)) {
        ownerOf.set(loc.entity_id, f)
      }
    }
  }

  for (const f of factions) {
    const color = factionColorMap.get(f.entity_id)!
    const payload = {
      label: f.canonical_name,
      kind: 'faction',
      color,
      dataAliases: f.aliases || [],
      summary: f.narrative_summary,
      state: f.state_vector || {},
      metas: typeMeta(f),
    }
    nodes.push({
      id: `fac:${f.entity_id}`,
      label: f.canonical_name,
      kind: 'faction',
      color,
      sublabel: `${factionTerritories.get(f.entity_id)?.length || 0} 处领地`,
      data: { kind: 'faction', state: f.state_vector || {}, summary: f.narrative_summary, aliases: f.aliases || [], metas: typeMeta(f) },
    })
    nodeById.set(`fac:${f.entity_id}`, payload)
  }

  for (const loc of locations) {
    const owner = ownerOf.get(loc.entity_id)
    const color = owner ? factionColorMap.get(owner.entity_id) : KIND_COLORS.location
    const payload = {
      label: loc.canonical_name,
      kind: 'location',
      color,
      dataAliases: loc.aliases || [],
      summary: loc.narrative_summary,
      state: loc.state_vector || {},
      metas: typeMeta(loc),
    }
    nodes.push({
      id: `loc:${loc.entity_id}`,
      label: loc.canonical_name,
      kind: 'location',
      color,
      sublabel: loc.state_vector?.type ? String(loc.state_vector.type) : undefined,
      data: { kind: 'location', state: loc.state_vector || {}, summary: loc.narrative_summary, aliases: loc.aliases || [], metas: typeMeta(loc) },
    })
    nodeById.set(`loc:${loc.entity_id}`, payload)
  }

  const edges: GraphEdgeInput[] = []
  const edgeKey = new Set<string>()
  const addEdge = (a: string, b: string, relation?: string) => {
    const key = [a, b].sort().join('@@')
    if (edgeKey.has(key) || a === b) return
    edgeKey.add(key)
    edges.push({ id: `m-${key}`, source: a, target: b, relation })
  }

  // 实体关系中的地点-地点边
  for (const r of world.relationships) {
    if (locByKey.has(r.source_id) && locByKey.has(r.target_id)) {
      addEdge(`loc:${r.source_id}`, `loc:${r.target_id}`, r.relation_type)
    }
  }
  // connected_locations 字段
  for (const loc of locations) {
    const conn = loc.state_vector?.connected_locations
    if (!conn) continue
    const parts = Array.isArray(conn) ? conn.map(String) : String(conn).split(/[,，、]/)
    for (const p of parts) {
      const target = nameToLoc.get(p.trim().toLowerCase()) || nameToLoc.get(p.trim())
      if (target) addEdge(`loc:${loc.entity_id}`, `loc:${target.entity_id}`, '相连')
    }
  }
  // 势力 → 领地控制边
  for (const fid of factionTerritories.keys()) {
    for (const loc of locations) {
      if (ownerOf.get(loc.entity_id)?.entity_id === fid) {
        addEdge(`fac:${fid}`, `loc:${loc.entity_id}`, '控制')
      }
    }
  }

  return {
    nodes,
    edges,
    nodeById,
    factions: factions.map(f => {
      const color = factionColorMap.get(f.entity_id)!
      const owned = locations.filter(l => ownerOf.get(l.entity_id)?.entity_id === f.entity_id).length
      return { id: `fac:${f.entity_id}`, label: f.canonical_name, color, territoryCount: owned }
    }),
  }
}

function keyOf(l: WorldEntity): string {
  return l.entity_id
}

function territoryMatch(loc: WorldEntity, territories: string[]): boolean {
  const locName = loc.canonical_name.trim().toLowerCase()
  const aliasNames = (loc.aliases || []).map(a => a.trim().toLowerCase())
  for (const t of territories) {
    const tl = t.trim().toLowerCase()
    if (!tl) continue
    if (locName === tl || aliasNames.includes(tl)) return true
    // 反向包含：领地写了大区域名，地点名包含它（如「青云城」⊂「青云府」）
    if (locName.includes(tl) && tl.length >= 2) return true
  }
  return false
}

function regionMatch(loc: WorldEntity, faction: WorldEntity): boolean {
  const region = loc.state_vector?.region
  if (!region) return false
  return String(region).trim() === faction.canonical_name.trim()
}

function typeMeta(e: WorldEntity) {
  const metas: { label: string; value: string }[] = []
  if (e.last_mentioned_chapter_number) {
    metas.push({ label: '最后提及', value: `第${e.last_mentioned_chapter_number}章` })
  }
  return metas
}

// ─── 快速添加地点（最小决策：只需名称与一句话描述）───
function AddLocationModal({
  novelId,
  onClose,
  onSaved,
}: {
  novelId: number
  onClose: () => void
  onSaved: () => void
}) {
  const [name, setName] = useState('')
  const [summary, setSummary] = useState('')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')

  const save = async () => {
    if (!name.trim()) return
    setSaving(true)
    setError('')
    try {
      await entityApi.create({
        novel_id: novelId,
        canonical_name: name.trim(),
        entity_type: 'location',
        aliases: [],
        state_vector: {},
        narrative_summary: summary.trim() || undefined,
      })
      onSaved()
    } catch (e: any) {
      setError(e?.response?.data?.detail || e?.message || '创建失败')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4" onClick={onClose}>
      <div
        className="bg-white dark:bg-gray-800 rounded-xl p-5 w-full max-w-md shadow-xl border border-gray-200 dark:border-gray-700"
        onClick={e => e.stopPropagation()}
      >
        <div className="flex items-center justify-between mb-4">
          <h3 className="font-bold text-gray-900 dark:text-white flex items-center gap-2">
            <MapIcon className="h-5 w-5 text-emerald-500" /> 添加地点
          </h3>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600 dark:hover:text-gray-200">
            <X className="h-5 w-5" />
          </button>
        </div>
        <div className="space-y-3">
          <div>
            <label className="block text-sm text-gray-500 dark:text-gray-400 mb-1">地点名称 *</label>
            <input
              value={name}
              autoFocus
              onChange={e => setName(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && save()}
              placeholder="例如：青云宗山门"
              className="w-full px-3 py-2 rounded-lg border border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-white text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
            />
          </div>
          <div>
            <label className="block text-sm text-gray-500 dark:text-gray-400 mb-1">一句话描述</label>
            <textarea
              value={summary}
              onChange={e => setSummary(e.target.value)}
              rows={2}
              placeholder="可选，用于显示在地图上"
              className="w-full px-3 py-2 rounded-lg border border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-white text-sm resize-none focus:outline-none focus:ring-2 focus:ring-primary-500"
            />
          </div>
          {error && <p className="text-sm text-red-500">{error}</p>}
          <div className="flex justify-end gap-2 pt-1">
            <button
              onClick={onClose}
              className="px-4 py-2 text-sm text-gray-500 hover:text-gray-700 dark:hover:text-gray-200"
            >
              取消
            </button>
            <button
              onClick={save}
              disabled={!name.trim() || saving}
              className="inline-flex items-center gap-1.5 px-4 py-2 rounded-lg bg-emerald-600 text-white text-sm hover:bg-emerald-500 disabled:opacity-40"
            >
              <Save className="h-4 w-4" /> {saving ? '保存中…' : '保存'}
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}