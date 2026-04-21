import { useEffect, useRef, useState } from 'react'
import { Network, X } from 'lucide-react'

interface CharacterNode {
  id: string
  name: string
  role: string
  color: string
  firstAppearance: number
  profile: Record<string, unknown>
}

interface RelationshipEdge {
  source: string
  target: string
  relation: string
}

interface RelationshipGraphProps {
  novelId: number
}

export function RelationshipGraph({ novelId }: RelationshipGraphProps) {
  const canvasRef = useRef<HTMLDivElement>(null)
  const [data, setData] = useState<{ nodes: CharacterNode[]; edges: RelationshipEdge[] } | null>(null)
  const [loading, setLoading] = useState(true)
  const [selectedNode, setSelectedNode] = useState<CharacterNode | null>(null)
  const [positions, setPositions] = useState<Record<string, { x: number; y: number }>>({})
  
  // 加载关系数据
  useEffect(() => {
    async function fetchData() {
      try {
        const response = await fetch(`/api/v1/characters/novel/${novelId}/relationships`, {
          headers: {
            'Authorization': `Bearer ${localStorage.getItem('token')}`
          }
        })
        const result = await response.json()
        setData(result)
        
        // 初始化节点位置（圆形布局）
        if (result.nodes?.length) {
          const centerX = 400
          const centerY = 300
          const radius = Math.min(250, 50 * result.nodes.length)
          
          const newPositions: Record<string, { x: number; y: number }> = {}
          result.nodes.forEach((node: CharacterNode, i: number) => {
            const angle = (2 * Math.PI * i) / result.nodes.length
            newPositions[node.id] = {
              x: centerX + radius * Math.cos(angle),
              y: centerY + radius * Math.sin(angle)
            }
          })
          setPositions(newPositions)
        }
      } catch (error) {
        console.error('Failed to load relationships:', error)
      } finally {
        setLoading(false)
      }
    }
    
    fetchData()
  }, [novelId])
  
  // 关系类型翻译
  const relationLabels: Record<string, string> = {
    'friend': '朋友',
    'enemy': '敌人',
    'family': '家人',
    'lover': '恋人',
    'master': '师父',
    'disciple': '徒弟',
    'rival': '对手',
    'ally': '盟友',
    'betrayer': '背叛者',
    'Stranger': '陌生人',
  }
  
  if (loading) {
    return (
      <div className="flex items-center justify-center h-96">
        <div className="text-gray-500">加载中...</div>
      </div>
    )
  }
  
  if (!data || data.nodes.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center h-96 text-gray-500">
        <Network className="w-16 h-16 mb-4 opacity-50" />
        <p>暂无角色关系数据</p>
        <p className="text-sm mt-2">请先创建角色并设置关系</p>
      </div>
    )
  }
  
  return (
    <div className="relative">
      {/* 图例 */}
      <div className="absolute top-4 left-4 bg-white p-3 rounded-lg shadow-md z-10">
        <div className="text-sm font-medium mb-2">角色类型</div>
        <div className="space-y-1 text-xs">
          <div className="flex items-center gap-2">
            <div className="w-3 h-3 rounded-full" style={{ backgroundColor: '#F59E0B' }}></div>
            <span>主角</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-3 h-3 rounded-full" style={{ backgroundColor: '#EF4444' }}></div>
            <span>反派</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-3 h-3 rounded-full" style={{ backgroundColor: '#3B82F6' }}></div>
            <span>配角</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-3 h-3 rounded-full" style={{ backgroundColor: '#6B7280' }}></div>
            <span>龙套</span>
          </div>
        </div>
      </div>
      
      {/* 关系图画布 */}
      <div 
        ref={canvasRef}
        className="relative w-full h-[600px] bg-gray-50 rounded-lg overflow-hidden border"
      >
        <svg className="w-full h-full">
          {/* 绘制边 */}
          {data.edges.map((edge, i) => {
            const sourcePos = positions[edge.source]
            const targetPos = positions[edge.target]
            if (!sourcePos || !targetPos) return null
            
            return (
              <g key={`edge-${i}`}>
                <line
                  x1={sourcePos.x}
                  y1={sourcePos.y}
                  x2={targetPos.x}
                  y2={targetPos.y}
                  stroke="#9CA3AF"
                  strokeWidth="2"
                  strokeDasharray={edge.relation === 'enemy' ? '5,5' : undefined}
                />
                {/* 关系标签 */}
                <text
                  x={(sourcePos.x + targetPos.x) / 2}
                  y={(sourcePos.y + targetPos.y) / 2 - 5}
                  textAnchor="middle"
                  fontSize="10"
                  fill="#6B7280"
                  bgColor="white"
                >
                  {relationLabels[edge.relation] || edge.relation}
                </text>
              </g>
            )
          })}
          
          {/* 绘制节点 */}
          {data.nodes.map((node) => {
            const pos = positions[node.id]
            if (!pos) return null
            
            return (
              <g 
                key={node.id}
                onClick={() => setSelectedNode(node)}
                className="cursor-pointer"
              >
                <circle
                  cx={pos.x}
                  cy={pos.y}
                  r="24"
                  fill={node.color}
                  stroke="white"
                  strokeWidth="3"
                  className="hover:opacity-80 transition-opacity"
                />
                <text
                  x={pos.x}
                  y={pos.y + 40}
                  textAnchor="middle"
                  fontSize="12"
                  fontWeight="500"
                >
                  {node.name}
                </text>
                <text
                  x={pos.x}
                  y={pos.y + 54}
                  textAnchor="middle"
                  fontSize="10"
                  fill="#6B7280"
                >
                  出场: 第{node.firstAppearance}章
                </text>
              </g>
            )
          })}
        </svg>
      </div>
      
      {/* 选中角色详情 */}
      {selectedNode && (
        <div className="absolute top-4 right-4 w-64 bg-white rounded-lg shadow-lg p-4 z-20">
          <div className="flex justify-between items-start mb-3">
            <h3 className="font-bold text-lg">{selectedNode.name}</h3>
            <button 
              onClick={() => setSelectedNode(null)}
              className="text-gray-400 hover:text-gray-600"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
          
          <div className="space-y-2 text-sm">
            <div className="flex items-center gap-2">
              <span className="text-gray-500">类型:</span>
              <span 
                className="px-2 py-0.5 rounded text-white text-xs"
                style={{ backgroundColor: selectedNode.color }}
              >
                {selectedNode.role === 'protagonist' ? '主角' : 
                 selectedNode.role === 'antagonist' ? '反派' :
                 selectedNode.role === 'supporting' ? '配角' : '龙套'}
              </span>
            </div>
            
            <div className="text-gray-500">
              首次出场: 第{selectedNode.firstAppearance}章
            </div>
            
            {selectedNode.profile && Object.keys(selectedNode.profile).length > 0 && (
              <div className="mt-3 pt-3 border-t">
                <div className="text-gray-500 mb-1">人设信息</div>
                {Object.entries(selectedNode.profile).filter(([k]) => k !== 'relationships').map(([key, value]) => (
                  <div key={key} className="text-xs">
                    <span className="text-gray-400">{key}:</span> {String(value)}
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}
      
      {/* 统计信息 */}
      <div className="absolute bottom-4 left-4 bg-white px-4 py-2 rounded-lg shadow text-sm">
        <span className="text-gray-500">共 </span>
        <span className="font-bold">{data.nodes.length}</span>
        <span className="text-gray-500"> 个角色，</span>
        <span className="font-bold">{data.edges.length}</span>
        <span className="text-gray-500"> 条关系</span>
      </div>
    </div>
  )
}
