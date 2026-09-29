import { Link, useLocation, useParams } from 'react-router-dom'
import {
  Home, Network, Map as MapIcon, Library, Users, Boxes, FileText, PenLine, BookOpen, History,
} from 'lucide-react'

const TABS = [
  { path: '', label: '概览', icon: Home },
  { path: '/graph', label: '实体图谱', icon: Network },
  { path: '/map', label: '小说地图', icon: MapIcon },
  { path: '/knowledge', label: '知识库', icon: Library },
  { path: '/characters', label: '角色', icon: Users },
  { path: '/entities', label: '实体', icon: Boxes },
  { path: '/outline', label: '大纲', icon: FileText },
  { path: '/write', label: '写作', icon: PenLine },
  { path: '/read', label: '阅读', icon: BookOpen },
  { path: '/snapshots', label: '快照', icon: History },
]

export function NovelNav() {
  const { novelId } = useParams<{ novelId: string }>()
  const location = useLocation()
  const base = `/novel/${novelId}`

  const isActive = (path: string) => {
    if (!path) {
      return location.pathname === base
    }
    return location.pathname === base + path || location.pathname.startsWith(base + path + '/')
  }

  return (
    <nav className="flex items-center gap-1 overflow-x-auto pb-1 -mb-1">
      {TABS.map(tab => {
        const active = isActive(tab.path)
        return (
          <Link
            key={tab.path || 'overview'}
            to={base + tab.path}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm whitespace-nowrap transition-colors ${
              active
                ? 'bg-primary-100 text-primary-700 dark:bg-primary-900/40 dark:text-primary-300'
                : 'text-gray-600 hover:bg-gray-100 dark:text-gray-300 dark:hover:bg-gray-700/60'
            }`}
          >
            <tab.icon className="h-4 w-4" />
            {tab.label}
          </Link>
        )
      })}
    </nav>
  )
}