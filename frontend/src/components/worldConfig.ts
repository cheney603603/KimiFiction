// 世界实体展示配置：图谱 / 地图 / 知识库 共用
// 配色与「实体管理」页面保持一致

export interface WorldKindMeta {
  label: string
  color: string
  fields: { key: string; label: string }[]
}

export const WORLD_KIND_META: Record<string, WorldKindMeta> = {
  character: {
    label: '角色',
    color: '#f59e0b',
    fields: [
      { key: 'age', label: '年龄' },
      { key: 'gender', label: '性别' },
      { key: 'appearance', label: '外貌' },
      { key: 'personality', label: '性格' },
      { key: 'background', label: '背景故事' },
      { key: 'goals', label: '目标' },
      { key: 'skills', label: '技能' },
      { key: 'fears', label: '恐惧' },
      { key: 'current_location', label: '当前位置' },
      { key: 'health_status', label: '健康状态' },
      { key: 'mood', label: '心情' },
      { key: 'cultivation_level', label: '修为/等级' },
    ],
  },
  faction: {
    label: '势力',
    color: '#3b82f6',
    fields: [
      { key: 'leader', label: '领袖' },
      { key: 'members', label: '成员' },
      { key: 'territory', label: '领地' },
      { key: 'strength', label: '实力' },
      { key: 'ideology', label: '理念/宗旨' },
      { key: 'enemies', label: '敌对势力' },
      { key: 'allies', label: '盟友' },
      { key: 'resources', label: '资源' },
    ],
  },
  location: {
    label: '地点',
    color: '#10b981',
    fields: [
      { key: 'type', label: '类型' },
      { key: 'climate', label: '气候' },
      { key: 'terrain', label: '地形' },
      { key: 'atmosphere', label: '氛围' },
      { key: 'significance', label: '重要性' },
      { key: 'connected_locations', label: '关联地点' },
      { key: 'inhabitants', label: '居民' },
      { key: 'region', label: '所属区域' },
    ],
  },
  item: {
    label: '物品',
    color: '#a855f7',
    fields: [
      { key: 'type', label: '类型' },
      { key: 'origin', label: '来源' },
      { key: 'appearance', label: '外观' },
      { key: 'function', label: '功能' },
      { key: 'power_level', label: '威力等级' },
      { key: 'owner', label: '持有者' },
      { key: 'restrictions', label: '限制条件' },
    ],
  },
  skill: {
    label: '技能',
    color: '#06b6d4',
    fields: [
      { key: 'type', label: '类型' },
      { key: 'level', label: '等级' },
      { key: 'attributes', label: '属性' },
      { key: 'effects', label: '效果' },
      { key: 'origin', label: '来历' },
      { key: 'limitations', label: '限制' },
    ],
  },
}

// 地图上势力版图配色调色板
export const FACTION_PALETTE = [
  '#3b82f6', '#8b5cf6', '#ef4444', '#f97316',
  '#06b6d4', '#ec4899', '#84cc16', '#f59e0b',
  '#14b8a6', '#eab308', '#6366f1', '#f43f5e',
]

export function factionColor(index: number): string {
  return FACTION_PALETTE[index % FACTION_PALETTE.length]
}

// 通用：把任意值渲染成可读文本（数组转标签串，对象转 JSON）
export function valueToText(value: unknown): string {
  if (value === null || value === undefined) return ''
  if (Array.isArray(value)) return value.map(v => String(v)).join('、')
  if (typeof value === 'object') return JSON.stringify(value)
  return String(value)
}