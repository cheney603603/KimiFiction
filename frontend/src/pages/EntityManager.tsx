import { useState, useCallback } from 'react'
import { useParams, Link } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  Plus, X, ArrowLeft, Sparkles, Edit, Save, Trash2, User, Users,
  MapPin, Package, ChevronDown, ChevronUp, Network, Search,
  CheckSquare, Square, Share2, AlertCircle, CheckCircle
} from 'lucide-react'
import { entityApi } from '../services/api'

// ─── 类型定义 ───────────────────────────────────────────────
interface Entity {
  id: number
  entity_id: string
  novel_id: number
  canonical_name: string
  aliases: string[]
  entity_type: 'character' | 'faction' | 'skill' | 'item' | 'location'
  state_vector: Record<string, any>
  narrative_summary?: string
  last_mentioned_chapter_number?: number
  created_at: string
  updated_at: string
}

type EntityCategory = 'character' | 'faction' | 'location' | 'item'

// ─── Toast 组件 ─────────────────────────────────────────────
type ToastType = 'success' | 'error'
interface Toast { id: number; type: ToastType; message: string }

let toastId = 0

// ─── 分类配置 ───────────────────────────────────────────────
const CATEGORY_CONFIG: Record<EntityCategory, {
  label: string
  icon: typeof User
  color: string
  bgColor: string
  borderColor: string
  fields: { key: string; label: string; type: 'text' | 'textarea' | 'tags' }[]
}> = {
  character: {
    label: '生物 / 角色',
    icon: User,
    color: 'text-amber-400',
    bgColor: 'bg-amber-900/20',
    borderColor: 'border-amber-800',
    fields: [
      { key: 'age', label: '年龄', type: 'text' },
      { key: 'gender', label: '性别', type: 'text' },
      { key: 'appearance', label: '外貌', type: 'textarea' },
      { key: 'personality', label: '性格', type: 'textarea' },
      { key: 'background', label: '背景故事', type: 'textarea' },
      { key: 'goals', label: '目标', type: 'tags' },
      { key: 'skills', label: '技能', type: 'tags' },
      { key: 'fears', label: '恐惧', type: 'tags' },
      { key: 'current_location', label: '当前位置', type: 'text' },
      { key: 'health_status', label: '健康状态', type: 'text' },
      { key: 'mood', label: '心情', type: 'text' },
      { key: 'cultivation_level', label: '修为/等级', type: 'text' },
    ],
  },
  faction: {
    label: '群体 / 势力',
    icon: Users,
    color: 'text-blue-400',
    bgColor: 'bg-blue-900/20',
    borderColor: 'border-blue-800',
    fields: [
      { key: 'leader', label: '领袖', type: 'text' },
      { key: 'members', label: '成员', type: 'tags' },
      { key: 'territory', label: '领地', type: 'text' },
      { key: 'strength', label: '实力', type: 'text' },
      { key: 'ideology', label: '理念/宗旨', type: 'textarea' },
      { key: 'enemies', label: '敌对势力', type: 'tags' },
      { key: 'allies', label: '盟友', type: 'tags' },
      { key: 'resources', label: '资源', type: 'tags' },
    ],
  },
  location: {
    label: '场景 / 空间',
    icon: MapPin,
    color: 'text-emerald-400',
    bgColor: 'bg-emerald-900/20',
    borderColor: 'border-emerald-800',
    fields: [
      { key: 'type', label: '类型', type: 'text' },
      { key: 'climate', label: '气候', type: 'text' },
      { key: 'terrain', label: '地形', type: 'textarea' },
      { key: 'atmosphere', label: '氛围', type: 'textarea' },
      { key: 'significance', label: '重要性', type: 'textarea' },
      { key: 'connected_locations', label: '关联地点', type: 'tags' },
      { key: 'inhabitants', label: '居民', type: 'tags' },
    ],
  },
  item: {
    label: '物品 / 道具',
    icon: Package,
    color: 'text-purple-400',
    bgColor: 'bg-purple-900/20',
    borderColor: 'border-purple-800',
    fields: [
      { key: 'type', label: '类型', type: 'text' },
      { key: 'origin', label: '来源', type: 'text' },
      { key: 'appearance', label: '外观', type: 'textarea' },
      { key: 'function', label: '功能', type: 'textarea' },
      { key: 'power_level', label: '威力等级', type: 'text' },
      { key: 'owner', label: '持有者', type: 'text' },
      { key: 'restrictions', label: '限制条件', type: 'tags' },
    ],
  },
}

// ─── Toast 提示组件 ─────────────────────────────────────────
function ToastContainer({ toasts, onRemove }: {
  toasts: Toast[]
  onRemove: (id: number) => void
}) {
  if (toasts.length === 0) return null
  return (
    <div className="fixed top-4 right-4 z-[100] flex flex-col gap-2">
      {toasts.map(t => (
        <div
          key={t.id}
          className={`flex items-center gap-2 px-4 py-3 rounded-lg shadow-lg text-sm font-medium animate-slide-in ${
            t.type === 'success'
              ? 'bg-green-900/90 text-green-300 border border-green-700'
              : 'bg-red-900/90 text-red-300 border border-red-700'
          }`}
        >
          {t.type === 'success' ? <CheckCircle className="h-4 w-4" /> : <AlertCircle className="h-4 w-4" />}
          {t.message}
          <button onClick={() => onRemove(t.id)} className="ml-2 opacity-60 hover:opacity-100">
            <X className="h-3 w-3" />
          </button>
        </div>
      ))}
    </div>
  )
}

// ─── 实体卡片组件 ───────────────────────────────────────────
function EntityCard({
  entity,
  category,
  selected,
  onToggleSelect,
  onEdit,
  onDelete,
}: {
  entity: Entity
  category: EntityCategory
  selected: boolean
  onToggleSelect: (id: string) => void
  onEdit: (e: Entity) => void
  onDelete: (id: string) => void
}) {
  const [expanded, setExpanded] = useState(false)
  const config = CATEGORY_CONFIG[category]
  const Icon = config.icon
  const state = entity.state_vector || {}

  return (
    <div className={`rounded-xl border ${config.borderColor} ${config.bgColor} overflow-hidden transition-all ${
      selected ? 'ring-2 ring-indigo-500' : ''
    }`}>
      {/* 卡片头部 */}
      <div className="p-4 flex items-start justify-between">
        <div className="flex items-center gap-3">
          <button
            onClick={() => onToggleSelect(entity.entity_id)}
            className="text-gray-500 hover:text-indigo-400 transition-colors flex-shrink-0"
          >
            {selected ? <CheckSquare className="h-5 w-5 text-indigo-400" /> : <Square className="h-5 w-5" />}
          </button>
          <div className={`p-2 rounded-lg bg-gray-800 ${config.color}`}>
            <Icon className="h-5 w-5" />
          </div>
          <div>
            <h3 className="font-bold text-white">{entity.canonical_name}</h3>
            {entity.aliases && entity.aliases.length > 0 && (
              <p className="text-xs text-gray-500">别名: {entity.aliases.join(', ')}</p>
            )}
          </div>
        </div>
        <div className="flex items-center gap-1">
          <button
            onClick={() => onEdit(entity)}
            className="p-1.5 text-gray-400 hover:text-indigo-400 transition-colors"
          >
            <Edit className="h-4 w-4" />
          </button>
          <button
            onClick={() => onDelete(entity.entity_id)}
            className="p-1.5 text-gray-400 hover:text-red-400 transition-colors"
          >
            <Trash2 className="h-4 w-4" />
          </button>
          <button
            onClick={() => setExpanded(!expanded)}
            className="p-1.5 text-gray-400 hover:text-gray-200 transition-colors"
          >
            {expanded ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
          </button>
        </div>
      </div>

      {/* 摘要 */}
      {entity.narrative_summary && (
        <div className="px-4 pb-2">
          <p className="text-sm text-gray-400 line-clamp-2">{entity.narrative_summary}</p>
        </div>
      )}

      {/* 展开详情 */}
      {expanded && (
        <div className="px-4 pb-4 space-y-2">
          {config.fields.map(field => {
            const value = state[field.key]
            if (!value || (Array.isArray(value) && value.length === 0)) return null
            return (
              <div key={field.key} className="text-sm">
                <span className="text-gray-500">{field.label}:</span>{' '}
                {Array.isArray(value) ? (
                  <span className="flex flex-wrap gap-1 mt-1">
                    {value.map((v: string, i: number) => (
                      <span key={i} className="px-2 py-0.5 bg-gray-800 rounded text-xs text-gray-300">
                        {v}
                      </span>
                    ))}
                  </span>
                ) : (
                  <span className="text-gray-300">{value}</span>
                )}
              </div>
            )
          })}
          {entity.last_mentioned_chapter_number && (
            <p className="text-xs text-gray-600 mt-2">
              最后提及: 第{entity.last_mentioned_chapter_number}章
            </p>
          )}
        </div>
      )}
    </div>
  )
}

// ─── 编辑/创建表单 ──────────────────────────────────────────
function EntityForm({
  entity,
  category,
  onSave,
  onCancel,
}: {
  entity?: Entity
  category: EntityCategory
  onSave: (data: any) => void
  onCancel: () => void
}) {
  const config = CATEGORY_CONFIG[category]
  const [form, setForm] = useState<Record<string, any>>({
    canonical_name: entity?.canonical_name || '',
    aliases: entity?.aliases?.join(', ') || '',
    narrative_summary: entity?.narrative_summary || '',
    ...((entity?.state_vector || {}) as Record<string, any>),
  })

  const handleSubmit = () => {
    const state_vector: Record<string, any> = {}
    config.fields.forEach(field => {
      const value = form[field.key]
      if (value) {
        if (field.type === 'tags') {
          state_vector[field.key] = String(value).split(/[,，]/).map(s => s.trim()).filter(Boolean)
        } else {
          state_vector[field.key] = value
        }
      }
    })

    onSave({
      canonical_name: form.canonical_name,
      aliases: form.aliases.split(/[,，]/).map((s: string) => s.trim()).filter(Boolean),
      narrative_summary: form.narrative_summary,
      state_vector,
    })
  }

  return (
    <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50 p-4">
      <div className="bg-gray-900 rounded-xl border border-gray-700 w-full max-w-lg max-h-[80vh] overflow-y-auto">
        <div className="p-4 border-b border-gray-800 flex items-center justify-between">
          <h3 className="font-bold text-white">
            {entity ? '编辑' : '新建'}{config.label}
          </h3>
          <button onClick={onCancel} className="text-gray-400 hover:text-white">
            <X className="h-5 w-5" />
          </button>
        </div>

        <div className="p-4 space-y-4">
          <div>
            <label className="block text-sm text-gray-400 mb-1">名称 *</label>
            <input
              value={form.canonical_name}
              onChange={e => setForm({ ...form, canonical_name: e.target.value })}
              className="w-full px-3 py-2 bg-gray-800 border border-gray-700 rounded-lg text-white"
              placeholder="实体名称"
            />
          </div>

          <div>
            <label className="block text-sm text-gray-400 mb-1">别名（逗号分隔）</label>
            <input
              value={form.aliases}
              onChange={e => setForm({ ...form, aliases: e.target.value })}
              className="w-full px-3 py-2 bg-gray-800 border border-gray-700 rounded-lg text-white"
              placeholder="别名1, 别名2"
            />
          </div>

          <div>
            <label className="block text-sm text-gray-400 mb-1">叙事摘要</label>
            <textarea
              value={form.narrative_summary}
              onChange={e => setForm({ ...form, narrative_summary: e.target.value })}
              rows={3}
              className="w-full px-3 py-2 bg-gray-800 border border-gray-700 rounded-lg text-white resize-none"
              placeholder="简要描述该实体..."
            />
          </div>

          {config.fields.map(field => (
            <div key={field.key}>
              <label className="block text-sm text-gray-400 mb-1">{field.label}</label>
              {field.type === 'textarea' ? (
                <textarea
                  value={form[field.key] || ''}
                  onChange={e => setForm({ ...form, [field.key]: e.target.value })}
                  rows={2}
                  className="w-full px-3 py-2 bg-gray-800 border border-gray-700 rounded-lg text-white resize-none"
                />
              ) : (
                <input
                  value={form[field.key] || ''}
                  onChange={e => setForm({ ...form, [field.key]: e.target.value })}
                  className="w-full px-3 py-2 bg-gray-800 border border-gray-700 rounded-lg text-white"
                  placeholder={field.type === 'tags' ? '用逗号分隔' : ''}
                />
              )}
            </div>
          ))}
        </div>

        <div className="p-4 border-t border-gray-800 flex justify-end gap-2">
          <button
            onClick={onCancel}
            className="px-4 py-2 text-gray-400 hover:text-white"
          >
            取消
          </button>
          <button
            onClick={handleSubmit}
            disabled={!form.canonical_name.trim()}
            className="px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-500 disabled:opacity-50"
          >
            <Save className="h-4 w-4 inline mr-1" />
            保存
          </button>
        </div>
      </div>
    </div>
  )
}

// ─── 主组件 ─────────────────────────────────────────────────
export function EntityManager() {
  const { novelId } = useParams<{ novelId: string }>()
  const id = parseInt(novelId || '0')
  const queryClient = useQueryClient()

  const [activeCategory, setActiveCategory] = useState<EntityCategory>('character')
  const [showForm, setShowForm] = useState(false)
  const [editingEntity, setEditingEntity] = useState<Entity | null>(null)
  const [searchQuery, setSearchQuery] = useState('')
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set())
  const [toasts, setToasts] = useState<Toast[]>([])

  const addToast = useCallback((type: ToastType, message: string) => {
    const id = ++toastId
    setToasts(prev => [...prev, { id, type, message }])
    setTimeout(() => {
      setToasts(prev => prev.filter(t => t.id !== id))
    }, 3000)
  }, [])

  const removeToast = useCallback((id: number) => {
    setToasts(prev => prev.filter(t => t.id !== id))
  }, [])

  // 获取实体列表
  const { data: entitiesData, isLoading } = useQuery({
    queryKey: ['entities', id, activeCategory],
    queryFn: () => entityApi.list(id, activeCategory),
    enabled: !!id,
  })

  const entities: Entity[] = (entitiesData as any)?.items || []
  const filteredEntities = searchQuery.trim()
    ? entities.filter(e =>
        e.canonical_name.toLowerCase().includes(searchQuery.toLowerCase()) ||
        (e.aliases || []).some(a => a.toLowerCase().includes(searchQuery.toLowerCase())) ||
        (e.narrative_summary || '').toLowerCase().includes(searchQuery.toLowerCase())
      )
    : entities

  // 创建实体
  const createMutation = useMutation({
    mutationFn: (data: any) => entityApi.create({ novel_id: id, entity_type: activeCategory, ...data }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['entities', id, activeCategory] })
      setShowForm(false)
      addToast('success', '实体创建成功')
    },
    onError: (err: any) => {
      addToast('error', `创建失败: ${err?.response?.data?.detail || err.message || '未知错误'}`)
    },
  })

  // 更新实体
  const updateMutation = useMutation({
    mutationFn: ({ entityId, data }: { entityId: string; data: any }) => entityApi.update(entityId, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['entities', id, activeCategory] })
      setEditingEntity(null)
      addToast('success', '实体更新成功')
    },
    onError: (err: any) => {
      addToast('error', `更新失败: ${err?.response?.data?.detail || err.message || '未知错误'}`)
    },
  })

  // 删除实体
  const deleteMutation = useMutation({
    mutationFn: (entityId: string) => entityApi.delete(entityId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['entities', id, activeCategory] })
      addToast('success', '实体已删除')
    },
    onError: (err: any) => {
      addToast('error', `删除失败: ${err?.response?.data?.detail || err.message || '未知错误'}`)
    },
  })

  // 批量删除
  const batchDeleteMutation = useMutation({
    mutationFn: (ids: string[]) =>
      entityApi.batchDelete(ids),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['entities', id] })
      setSelectedIds(new Set())
      addToast('success', `已批量删除 ${selectedIds.size} 个实体`)
    },
    onError: (err: any) => {
      addToast('error', `批量删除失败: ${err?.response?.data?.detail || err.message || '未知错误'}`)
    },
  })

  const handleSave = (data: any) => {
    if (editingEntity) {
      updateMutation.mutate({ entityId: editingEntity.entity_id, data })
    } else {
      createMutation.mutate(data)
    }
  }

  const toggleSelect = (entityId: string) => {
    setSelectedIds(prev => {
      const next = new Set(prev)
      if (next.has(entityId)) {
        next.delete(entityId)
      } else {
        next.add(entityId)
      }
      return next
    })
  }

  const toggleSelectAll = () => {
    if (selectedIds.size === filteredEntities.length) {
      setSelectedIds(new Set())
    } else {
      setSelectedIds(new Set(filteredEntities.map(e => e.entity_id)))
    }
  }

  const handleBatchDelete = () => {
    const count = selectedIds.size
    if (count === 0) return
    if (!confirm(`确定删除选中的 ${count} 个实体吗？此操作不可撤销。`)) return
    batchDeleteMutation.mutate(Array.from(selectedIds))
  }

  return (
    <div className="max-w-6xl mx-auto p-6">
      <ToastContainer toasts={toasts} onRemove={removeToast} />

      {/* 头部 */}
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-4">
          <Link
            to={`/novel/${id}`}
            className="inline-flex items-center gap-2 text-gray-400 hover:text-indigo-400 transition-colors"
          >
            <ArrowLeft className="h-4 w-4" />
            返回小说详情
          </Link>
          <h1 className="text-2xl font-bold text-white">实体管理</h1>
        </div>
        <div className="flex items-center gap-2">
          <Link
            to={`/novel/${id}/characters`}
            className="flex items-center gap-2 px-3 py-2 text-sm text-gray-400 bg-gray-800 rounded-lg hover:bg-gray-700 transition-colors"
          >
            <Share2 className="h-4 w-4" />
            角色管理
          </Link>
          <button
            onClick={() => {
              setEditingEntity(null)
              setShowForm(true)
            }}
            className="flex items-center gap-2 px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-500"
          >
            <Plus className="h-4 w-4" />
            新建实体
          </button>
        </div>
      </div>

      {/* 搜索 + 批量操作栏 */}
      <div className="flex items-center gap-3 mb-4">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-500" />
          <input
            value={searchQuery}
            onChange={e => setSearchQuery(e.target.value)}
            placeholder="搜索实体名称、别名、摘要..."
            className="w-full pl-10 pr-4 py-2 bg-gray-800 border border-gray-700 rounded-lg text-white text-sm placeholder-gray-500 focus:outline-none focus:border-indigo-500"
          />
        </div>
        {selectedIds.size > 0 && (
          <div className="flex items-center gap-2">
            <span className="text-sm text-gray-400">已选 {selectedIds.size} 项</span>
            <button
              onClick={handleBatchDelete}
              className="flex items-center gap-1 px-3 py-2 bg-red-800 text-red-200 rounded-lg hover:bg-red-700 text-sm"
            >
              <Trash2 className="h-4 w-4" />
              批量删除
            </button>
          </div>
        )}
      </div>

      {/* 分类标签 */}
      <div className="flex gap-2 mb-6 flex-wrap">
        {(Object.keys(CATEGORY_CONFIG) as EntityCategory[]).map(cat => {
          const config = CATEGORY_CONFIG[cat]
          const Icon = config.icon
          const isActive = activeCategory === cat
          return (
            <button
              key={cat}
              onClick={() => setActiveCategory(cat)}
              className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                isActive
                  ? `${config.bgColor} ${config.color} border ${config.borderColor}`
                  : 'bg-gray-800 text-gray-400 hover:bg-gray-700'
              }`}
            >
              <Icon className="h-4 w-4" />
              {config.label}
            </button>
          )
        })}
      </div>

      {/* 全选工具栏（有数据时显示） */}
      {filteredEntities.length > 0 && (
        <div className="flex items-center gap-2 mb-3 px-1">
          <button
            onClick={toggleSelectAll}
            className="flex items-center gap-1.5 text-xs text-gray-500 hover:text-gray-300 transition-colors"
          >
            {selectedIds.size === filteredEntities.length ? <CheckSquare className="h-3.5 w-3.5" /> : <Square className="h-3.5 w-3.5" />}
            {selectedIds.size === filteredEntities.length ? '取消全选' : `全选 (${filteredEntities.length})`}
          </button>
          {searchQuery && (
            <span className="text-xs text-gray-600">
              筛选出 {filteredEntities.length} / {entities.length} 个
            </span>
          )}
        </div>
      )}

      {/* 实体列表 */}
      {isLoading ? (
        <div className="text-center py-12 text-gray-500">
          <Sparkles className="h-8 w-8 mx-auto mb-3 animate-pulse" />
          加载中...
        </div>
      ) : filteredEntities.length === 0 ? (
        <div className="text-center py-12 bg-gray-900 rounded-xl border border-gray-800">
          <Network className="h-12 w-12 mx-auto mb-4 text-gray-600" />
          {searchQuery ? (
            <>
              <p className="text-gray-400 mb-2">未找到匹配的实体</p>
              <p className="text-sm text-gray-600">试试其他搜索词</p>
            </>
          ) : (
            <>
              <p className="text-gray-400 mb-2">暂无{CATEGORY_CONFIG[activeCategory].label}</p>
              <p className="text-sm text-gray-600">点击右上角"新建实体"按钮添加</p>
            </>
          )}
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {filteredEntities.map(entity => (
            <EntityCard
              key={entity.entity_id}
              entity={entity}
              category={activeCategory}
              selected={selectedIds.has(entity.entity_id)}
              onToggleSelect={toggleSelect}
              onEdit={e => {
                setEditingEntity(e)
                setShowForm(true)
              }}
              onDelete={id => {
                if (confirm(`确定删除「${entity.canonical_name}」吗？`)) {
                  deleteMutation.mutate(id)
                }
              }}
            />
          ))}
        </div>
      )}

      {/* 表单弹窗 */}
      {showForm && (
        <EntityForm
          entity={editingEntity || undefined}
          category={activeCategory}
          onSave={handleSave}
          onCancel={() => {
            setShowForm(false)
            setEditingEntity(null)
          }}
        />
      )}
    </div>
  )
}