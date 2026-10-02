import { useEffect, useMemo, useState, useCallback } from 'react'
import {
  ReactFlow, ReactFlowProvider, useReactFlow, Background, BackgroundVariant, Controls,
  Handle, Position, MarkerType, type Node, type Edge, type NodeProps, type NodeChange, type XYPosition,
} from '@xyflow/react'
import { forceSimulation, forceLink, forceManyBody, forceCenter, forceCollide } from 'd3-force'
import { User, Users, MapPin, Package, Zap, BookMarked, Sparkles } from 'lucide-react'
import '@xyflow/react/dist/style.css'

// 节点/边的基础输入结构（页面层负责把业务数据映射成这种结构）
export interface GraphNodeInput<T = any> {
  id: string
  label: string
  kind: string
  sublabel?: string
  color?: string
  data: T
}

export interface GraphEdgeInput {
  id: string
  source: string
  target: string
  relation?: string
}

// 默认按类型配色（与实体管理风格一致）
export const KIND_COLORS: Record<string, string> = {
  character: '#f59e0b',
  faction: '#3b82f6',
  location: '#10b981',
  item: '#a855f7',
  skill: '#06b6d4',
  region: '#6366f1',
}

const KIND_ICONS: Record<string, typeof User> = {
  character: User,
  faction: Users,
  location: MapPin,
  item: Package,
  skill: Zap,
  region: BookMarked,
}

interface WorldNodeData {
  label: string
  sublabel?: string
  kind: string
  color?: string
  summary?: string
  [key: string]: unknown
}

// d3-force 一次性自动布局：加载即排好，用户无需任何操作
function computeLayout(
  nodeInputs: GraphNodeInput[],
  edgeInputs: GraphEdgeInput[],
): Node<WorldNodeData>[] {
  const width = 900
  const height = 560

  const simNodes = nodeInputs.map(n => ({
    id: n.id,
    kind: n.kind,
    data: {
      label: n.label,
      sublabel: n.sublabel,
      kind: n.kind,
      color: n.color || KIND_COLORS[n.kind] || '#8b5cf6',
    } as WorldNodeData,
  }))

  const simLinks = edgeInputs.map(e => ({ source: e.source, target: e.target }))

  // 高连接度节点放中心，孤立/配角节点放外围
  const degree = new Map<string, number>()
  for (const e of edgeInputs) {
    degree.set(e.source, (degree.get(e.source) || 0) + 1)
    degree.set(e.target, (degree.get(e.target) || 0) + 1)
  }
  const isHubbed = (id: string) => (degree.get(id) || 0) >= 3

  const radius = Math.min(width, height) / 2 - 60
  simNodes.forEach((n, i) => {
    const r = isHubbed(n.id) ? radius * 0.35 : radius
    const angle = (2 * Math.PI * i) / Math.max(simNodes.length, 1)
    ;(n as any).x = width / 2 + r * Math.cos(angle)
    ;(n as any).y = height / 2 + r * Math.sin(angle)
  })

  const sim = forceSimulation(simNodes as any)
    .force(
      'link',
      forceLink(simLinks as any)
        .id((d: any) => d.id)
        .distance(110)
        .strength(0.6),
    )
    .force('charge', forceManyBody().strength(-260))
    .force('center', forceCenter(width / 2, height / 2))
    .force('collide', forceCollide(46).strength(0.8))
  sim.stop()
  for (let i = 0; i < 220 && sim.alpha() > 0.001; i++) sim.tick()
  sim.tick()

  const ls = new Map(simNodes.map(n => [n.id, n]))
  return simNodes.map(n => {
    const final = ls.get(n.id)!
    return {
      id: n.id,
      type: 'world',
      position: { x: (final as any).x ?? width / 2, y: (final as any).y ?? height / 2 },
      data: n.data,
      draggable: true,
    }
  })
}

interface ForceGraphProps {
  nodeInputs: GraphNodeInput[]
  edgeInputs: GraphEdgeInput[]
  selectedId?: string | null
  onSelect?: (id: string | null) => void
  height?: number
  emptyState?: React.ReactNode
  fitPadding?: number
}

export function ForceGraph(props: ForceGraphProps) {
  return (
    <ReactFlowProvider>
      <ForceGraphInner {...props} />
    </ReactFlowProvider>
  )
}

function WorldNodeComponent({ data }: NodeProps<Node<WorldNodeData>>) {
  const color = data.color || KIND_COLORS[data.kind] || '#8b5cf6'
  const Icon = KIND_ICONS[data.kind] || Sparkles
  // 自定义节点必须提供 Handle，否则 React Flow 找不到边的锚点、整条边都不渲染。
  // 四个方向各一对 source/target，透明且不可连接，贴合在圆形图标边缘。
  const handleProps = {
    className: '!opacity-0 !pointer-events-none !h-2 !w-2',
    style: { background: 'transparent', border: 'none', position: 'absolute' } as any,
    isConnectable: false,
  }
  return (
    <div className="flex flex-col items-center w-28 fg-node select-none">
      <div
        className="relative flex items-center justify-center rounded-full w-12 h-12 border-2 border-white dark:border-gray-900 shadow-md"
        style={{ background: color }}
      >
        <Icon className="w-6 h-6 text-white" />
        <Handle type="source" position={Position.Top} {...handleProps} />
        <Handle type="target" position={Position.Top} {...handleProps} />
        <Handle type="source" position={Position.Bottom} {...handleProps} />
        <Handle type="target" position={Position.Bottom} {...handleProps} />
        <Handle type="source" position={Position.Left} {...handleProps} />
        <Handle type="target" position={Position.Left} {...handleProps} />
        <Handle type="source" position={Position.Right} {...handleProps} />
        <Handle type="target" position={Position.Right} {...handleProps} />
      </div>
      <div className="mt-1 max-w-full truncate px-2 py-0.5 rounded-md bg-white/95 dark:bg-gray-900/95 text-xs font-medium text-gray-900 dark:text-gray-100 shadow-sm border border-gray-200 dark:border-gray-700">
        {data.label}
      </div>
      {data.sublabel && (
        <div className="text-[10px] text-gray-500 dark:text-gray-400 leading-tight mt-0.5">
          {data.sublabel}
        </div>
      )}
    </div>
  )
}

function ForceGraphInner({
  nodeInputs,
  edgeInputs,
  selectedId,
  onSelect,
  height = 560,
  emptyState,
  fitPadding = 0.18,
}: ForceGraphProps) {
  const [hovered, setHovered] = useState<string | null>(null)
  const [drag, setDrag] = useState<Record<string, XYPosition>>({})
  const rf = useReactFlow()

  // 节点集变化（搜索/筛选/新建）时自动重新布局
  const layoutKey = nodeInputs
    .map(n => n.id)
    .join(',')
    .concat('|')
    .concat(edgeInputs.map(e => `${e.source}>${e.target}`).join(','))

  // 重新布局时清空手动拖动位置
  useEffect(() => {
    setDrag({})
  }, [layoutKey])

  const positions = useMemo(() => computeLayout(nodeInputs, edgeInputs), [layoutKey])

  const posById = new Map(positions.map(p => [p.id, p]))

  // 支持用户手动拖拽（仅期间生效，重新布局后恢复自动排版）
  const onNodesChange = useCallback(
    (changes: NodeChange[]) => {
      for (const c of changes) {
        if (c.type === 'position' && c.position) {
          setDrag(prev => ({ ...prev, [c.id]: c.position! }))
        }
      }
    },
    [],
  )

  // 拖拽结束后自动重新取景，避免节点被拖出可视区后“消失”
  const onNodeDragStop = useCallback(() => {
    requestAnimationFrame(() => {
      rf.fitView({ padding: fitPadding, duration: 260 })
    })
  }, [rf, fitPadding])

  const nodes: Node<WorldNodeData>[] = useMemo(
    () =>
      nodeInputs.map(n => {
        const connected = hovered ? isConnectedTo(hovered, n.id, edgeInputs) || n.id === hovered : true
        return {
          id: n.id,
          type: 'world',
          position: drag[n.id] || posById.get(n.id)?.position || { x: 450, y: 280 },
          data: {
            label: n.label,
            sublabel: n.sublabel,
            kind: n.kind,
            color: n.color || KIND_COLORS[n.kind],
            summary: n.data?.summary,
          },
          selected: selectedId === n.id,
          className: hovered && !connected ? 'fg-dim' : undefined,
        }
      }),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [nodeInputs, positions, selectedId, hovered, drag],
  )

  const edges: Edge[] = useMemo(
    () =>
      edgeInputs.map((e, i) => ({
        id: e.id || `e-${i}`,
        source: e.source,
        target: e.target,
        label: e.relation,
        labelStyle: { fontSize: 10, fill: '#a1a1aa', pointerEvents: 'none' },
        labelBgStyle: { fill: 'rgba(24,24,27,0.8)', fillOpacity: 0.85 },
        labelBgPadding: [3, 2] as [number, number],
        labelBgBorderRadius: 3,
        markerEnd: { type: MarkerType.ArrowClosed, width: 13, height: 13, color: '#a1a1aa' },
        style: { stroke: '#a1a1aa', strokeWidth: 1.2 },
        className: hovered ? (isConnectedTo(hovered, e.source, edgeInputs) ? '' : 'fg-edge-dim') : undefined,
      })),
    [edgeInputs, hovered],
  )

  useEffect(() => {
    requestAnimationFrame(() => {
      rf.fitView({ padding: fitPadding, duration: 260 })
    })
  }, [layoutKey])

  if (nodeInputs.length === 0) {
    return (
      <div
        style={{ height }}
        className="flex items-center justify-center rounded-xl border border-dashed border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800"
      >
        {emptyState}
      </div>
    )
  }

  return (
    <div
      style={{ height }}
      className="relative rounded-xl border border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-900 overflow-hidden"
    >
      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={onNodesChange}
        onNodeDragStop={onNodeDragStop}
        onNodeClick={(_, node) => onSelect?.(node.id)}
        onPaneClick={() => {
          onSelect?.(null)
          setHovered(null)
        }}
        onNodeMouseEnter={(_, node) => setHovered(node.id)}
        onNodeMouseLeave={() => setHovered(null)}
        fitView
        fitViewOptions={{ padding: fitPadding }}
        minZoom={0.15}
        maxZoom={2.5}
        proOptions={{ hideAttribution: true }}
        nodeTypes={nodeTypes}
      >
        <Background variant={BackgroundVariant.Dots} gap={22} size={1.5} />
        <Controls className="[&>button]:!bg-white [&>button]:dark:!bg-gray-800 [&>button]:!border-gray-300 [&>button]:dark:!border-gray-600" />
      </ReactFlow>
    </div>
  )
}

function isConnectedTo(a: string, b: string, edges: GraphEdgeInput[]) {
  return edges.some(e => (e.source === a && e.target === b) || (e.source === b && e.target === a))
}

const nodeTypes = { world: WorldNodeComponent }