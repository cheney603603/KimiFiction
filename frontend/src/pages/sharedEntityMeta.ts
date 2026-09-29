import { WORLD_KIND_META } from '../components/worldConfig'

const EXTRA_META: Record<string, { label: string; color: string }> = {
  memory: { label: '记忆', color: '#f43f5e' },
  arc: { label: '大纲', color: '#f97316' },
}

export function entityMeta(kind: string): {
  label: string
  color: string
  fields: { key: string; label: string }[]
} {
  const extra = EXTRA_META[kind]
  if (extra) return { label: extra.label, color: extra.color, fields: [] }
  return (
    WORLD_KIND_META[kind] || {
      label: kind,
      color: '#8b5cf6',
      fields: [],
    }
  )
}