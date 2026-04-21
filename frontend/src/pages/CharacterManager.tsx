import { useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Plus, User, Crown, Sword, Users, X, ArrowLeft, Sparkles, Edit, Save, Check, Trash2, Network } from 'lucide-react'
import { characterApi, workflowApi } from '../services/api'
import { RelationshipGraph } from '../components/RelationshipGraph'
import type { Character } from '../types'

const roleTypeMap: Record<string, { label: string; icon: typeof User; color: string }> = {
  protagonist: { label: '主角', icon: Crown, color: 'text-yellow-600 bg-yellow-100' },
  antagonist: { label: '反派', icon: Sword, color: 'text-red-600 bg-red-100' },
  supporting: { label: '配角', icon: Users, color: 'text-blue-600 bg-blue-100' },
  minor: { label: '龙套', icon: User, color: 'text-gray-600 bg-gray-100' },
}

export function CharacterManager() {
  const { novelId } = useParams<{ novelId: string }>()
  const id = parseInt(novelId || '0')
  const queryClient = useQueryClient()

  const [isCreating, setIsCreating] = useState(false)
  const [selectedCharacter, setSelectedCharacter] = useState<Character | null>(null)
  const [editingCharacter, setEditingCharacter] = useState<Character | null>(null)
  const [newCharacter, setNewCharacter] = useState({
    name: '',
    role_type: 'supporting',
    profile: {} as Record<string, unknown>,
  })
  const [viewMode, setViewMode] = useState<'list' | 'graph'>('list')

  // 获取工作流的角色设计数据
  const { data: workflowCharacters } = useQuery({
    queryKey: ['workflow-characters', id],
    queryFn: async () => {
      try {
        const result = await workflowApi.getPhaseResult(id, 'character_design')
        console.log('工作流角色数据:', result)
        
        // 处理不同的响应格式
        if (!result) return []
        
        // 如果 result 本身就是数组
        if (Array.isArray(result)) return result
        
        // 如果 result.data 是数组
        if (result.data && Array.isArray(result.data)) return result.data
        
        // 如果 result.data.characters 是数组
        if (result.data && result.data.characters && Array.isArray(result.data.characters)) {
          return result.data.characters
        }
        
        // 如果 result.data 是对象且包含 success 字段
        if (result.data && typeof result.data === 'object') {
          // 尝试解析可能的嵌套结构
          if (result.data.success && result.data.data) {
            return Array.isArray(result.data.data) ? result.data.data : (result.data.data.characters || [])
          }
        }
        
        return []
      } catch (error) {
        console.log('工作流角色数据不可用:', error)
        return []
      }
    },
    enabled: !!id,
    retry: false,
  })

  const { data: charactersData } = useQuery({
    queryKey: ['characters', id],
    queryFn: () => characterApi.list(id),
    enabled: !!id,
  })

  const updateMutation = useMutation({
    mutationFn: ({ characterId, data }: { characterId: number; data: Partial<Character> }) =>
      characterApi.update(characterId, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['characters', id] })
      queryClient.invalidateQueries({ queryKey: ['workflow-characters', id] })
      setEditingCharacter(null)
    },
  })

  const deleteMutation = useMutation({
    mutationFn: (characterId: number) => characterApi.delete(characterId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['characters', id] })
      queryClient.invalidateQueries({ queryKey: ['workflow-characters', id] })
      setSelectedCharacter(null)
    },
  })

  const createMutation = useMutation({
    mutationFn: (data: typeof newCharacter) => characterApi.create({ ...data, novel_id: id }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['characters', id] })
      queryClient.invalidateQueries({ queryKey: ['workflow-characters', id] })
      setIsCreating(false)
      setNewCharacter({ name: '', role_type: 'supporting', profile: {} })
    },
  })

  // 合并工作流角色和数据库角色
  const dbCharacters = (charactersData as any)?.items || []
  const allCharacters = [...dbCharacters]
  
  // 添加工作流中的角色（如果不存在）
  workflowCharacters?.forEach((wfChar: any) => {
    const exists = dbCharacters.some((c: Character) => c.name === wfChar.name)
    if (!exists) {
      allCharacters.push({
        id: -1, // 临时ID，标记为工作流生成的角色
        novel_id: id,
        name: wfChar.name,
        role_type: wfChar.role_type || 'supporting',
        profile: wfChar.profile || {},
        arc_progress: 0,
        first_appearance: 1,
        appearance_count: 0,
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      })
    }
  })


  const handleSaveFromWorkflow = (wfChar: any) => {
    createMutation.mutate({
      name: wfChar.name,
      role_type: wfChar.role_type || 'supporting',
      profile: wfChar.profile || {},
    })
  }

  const handleCreate = () => {
    if (newCharacter.name.trim()) {
      createMutation.mutate(newCharacter)
    }
  }

  const characters = allCharacters

  // 加载状态
  if (charactersData === undefined) {
    return (
      <div className="flex justify-center items-center h-64">
        <div className="text-gray-500 dark:text-gray-400">加载中...</div>
      </div>
    )
  }

  // 打开编辑模式时初始化编辑内容
  const openEditModal = (character: Character) => {
    setEditingCharacter(character)
  }

  return (
    <div className="space-y-6">
      {/* 返回按钮 */}
      <Link
        to={`/novel/${id}`}
        className="inline-flex items-center gap-2 text-gray-600 dark:text-gray-400 hover:text-primary-600 dark:hover:text-primary-400 transition-colors"
      >
        <ArrowLeft className="h-5 w-5" />
        返回小说详情
      </Link>

      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 dark:text-white">
            角色管理
          </h1>
          {workflowCharacters && workflowCharacters.length > 0 && (
            <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
              包含 {workflowCharacters.length} 个工作流生成的角色
            </p>
          )}
        </div>
        <div className="flex items-center gap-2">
          {/* 视图切换 */}
          <div className="flex bg-gray-100 dark:bg-gray-700 rounded-lg p-1">
            <button
              onClick={() => setViewMode('list')}
              className={`flex items-center gap-1 px-3 py-1.5 rounded-md text-sm transition-colors ${
                viewMode === 'list' 
                  ? 'bg-white dark:bg-gray-600 shadow text-gray-900 dark:text-white' 
                  : 'text-gray-600 dark:text-gray-300 hover:text-gray-900 dark:hover:text-white'
              }`}
            >
              <Users className="h-4 w-4" />
              列表
            </button>
            <button
              onClick={() => setViewMode('graph')}
              className={`flex items-center gap-1 px-3 py-1.5 rounded-md text-sm transition-colors ${
                viewMode === 'graph' 
                  ? 'bg-white dark:bg-gray-600 shadow text-gray-900 dark:text-white' 
                  : 'text-gray-600 dark:text-gray-300 hover:text-gray-900 dark:hover:text-white'
              }`}
            >
              <Network className="h-4 w-4" />
              关系图
            </button>
          </div>
          <button
            onClick={() => setIsCreating(true)}
            className="flex items-center gap-2 px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700"
          >
            <Plus className="h-5 w-5" />
            添加角色
          </button>
        </div>
      </div>

      {/* 关系图谱视图 */}
      {viewMode === 'graph' ? (
        <div className="mt-6">
          <RelationshipGraph novelId={id} />
        </div>
      ) : (
      <>
      {/* 角色卡片网格 */}
      {characters.length === 0 ? (
        <div className="text-center py-16 bg-white dark:bg-gray-800 rounded-xl border border-dashed border-gray-300 dark:border-gray-600">
          <Users className="h-12 w-12 text-gray-400 mx-auto mb-4" />
          <h3 className="text-lg font-medium text-gray-900 dark:text-white mb-2">
            还没有角色
          </h3>
          <p className="text-gray-500 dark:text-gray-400 mb-4">
            使用AI生成角色或手动创建
          </p>
          <button 
            onClick={() => setIsCreating(true)}
            className="px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700"
          >
            添加角色
          </button>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {characters.map((character: Character) => {
            const roleInfo = roleTypeMap[character.role_type] || roleTypeMap.minor
            const RoleIcon = roleInfo.icon
            const isFromWorkflow = character.id === -1

            return (
              <div
                key={character.id}
                onClick={() => setSelectedCharacter(character)}
                className="bg-white dark:bg-gray-800 rounded-xl p-6 shadow-sm border border-gray-200 dark:border-gray-700 cursor-pointer hover:shadow-md transition-all relative"
              >
                {isFromWorkflow && (
                  <div className="absolute top-2 right-2">
                    <Sparkles className="h-4 w-4 text-purple-500" />
                  </div>
                )}
                <div className="flex items-start justify-between mb-4">
                  <div className={`p-3 rounded-lg ${roleInfo.color}`}>
                    <RoleIcon className="h-6 w-6" />
                  </div>
                  <span className="text-xs font-medium px-2 py-1 rounded-full bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-400">
                    {roleInfo.label}
                  </span>
                </div>

                <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-2">
                  {character.name}
                </h3>

                {/* 基本信息 */}
                <div className="space-y-1">
                  {(character.profile as any)?.age && (
                    <p className="text-sm text-gray-500 dark:text-gray-400">
                      年龄: {String((character.profile as any).age)}岁
                    </p>
                  )}
                  {(character.profile as any)?.gender && (
                    <p className="text-sm text-gray-500 dark:text-gray-400">
                      {String((character.profile as any).gender)}
                    </p>
                  )}
                  {(character.profile as any)?.mbti && (
                    <p className="text-xs font-mono text-blue-600 dark:text-blue-400">
                      {String((character.profile as any).mbti)}
                    </p>
                  )}
                </div>

                {/* 外貌简述 */}
                {(character.profile as any)?.appearance && (
                  <p className="text-sm text-gray-600 dark:text-gray-400 line-clamp-2 mt-2">
                    {(character.profile as any).appearance}
                  </p>
                )}

                <div className="mt-4 flex items-center justify-between text-sm text-gray-500 dark:text-gray-400">
                  <span>第{character.first_appearance}章出场</span>
                  <span>{character.appearance_count}次出场</span>
                </div>

                {/* 角色弧光进度 */}
                <div className="mt-3">
                  <div className="flex justify-between text-xs text-gray-500 mb-1">
                    <span>角色成长</span>
                    <span>{Math.round(character.arc_progress * 100)}%</span>
                  </div>
                  <div className="w-full bg-gray-200 dark:bg-gray-700 rounded-full h-1.5">
                    <div
                      className="bg-primary-600 h-1.5 rounded-full"
                      style={{ width: `${character.arc_progress * 100}%` }}
                    />
                  </div>
                </div>

                {isFromWorkflow && (
                  <div className="mt-3 flex gap-2">
                    <button
                      onClick={(e) => {
                        e.stopPropagation()
                        handleSaveFromWorkflow(character)
                      }}
                      className="flex-1 flex items-center justify-center gap-1 px-2 py-1 text-xs bg-purple-100 text-purple-700 rounded hover:bg-purple-200 dark:bg-purple-900/30 dark:text-purple-400 dark:hover:bg-purple-900/50"
                    >
                      <Save className="h-3 w-3" />
                      保存到数据库
                    </button>
                  </div>
                )}
              </div>
            )
          })}
        </div>
      )}

      {/* 创建角色弹窗 */}
      {isCreating && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-white dark:bg-gray-800 rounded-xl p-6 w-full max-w-md mx-4">
            <div className="flex justify-between items-center mb-4">
              <h2 className="text-xl font-bold text-gray-900 dark:text-white">
                添加新角色
              </h2>
              <button
                onClick={() => setIsCreating(false)}
                className="p-1 hover:bg-gray-100 dark:hover:bg-gray-700 rounded"
              >
                <X className="h-5 w-5 text-gray-500" />
              </button>
            </div>

            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                  角色名称
                </label>
                <input
                  type="text"
                  value={newCharacter.name}
                  onChange={(e) => setNewCharacter({ ...newCharacter, name: e.target.value })}
                  className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
                  placeholder="输入角色名称"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                  角色类型
                </label>
                <select
                  value={newCharacter.role_type}
                  onChange={(e) => setNewCharacter({ ...newCharacter, role_type: e.target.value })}
                  className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
                >
                  <option value="protagonist">主角</option>
                  <option value="antagonist">反派</option>
                  <option value="supporting">配角</option>
                  <option value="minor">龙套</option>
                </select>
              </div>

              <div className="flex gap-3 pt-4">
                <button
                  onClick={() => setIsCreating(false)}
                  className="flex-1 px-4 py-2 border border-gray-300 dark:border-gray-600 text-gray-700 dark:text-gray-300 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-700"
                >
                  取消
                </button>
                <button
                  onClick={handleCreate}
                  disabled={createMutation.isPending}
                  className="flex-1 px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700 disabled:opacity-50"
                >
                  {createMutation.isPending ? '创建中...' : '创建'}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* 角色详情弹窗 */}
      {selectedCharacter && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-white dark:bg-gray-800 rounded-xl p-6 w-full max-w-lg mx-4 max-h-[80vh] overflow-y-auto">
            <div className="flex justify-between items-center mb-4">
              <div className="flex items-center gap-2">
                <h2 className="text-xl font-bold text-gray-900 dark:text-white">
                  {selectedCharacter.name}
                </h2>
                {selectedCharacter.id === -1 && (
                  <Sparkles className="h-4 w-4 text-purple-500" />
                )}
              </div>
              <div className="flex items-center gap-2">
                {selectedCharacter.id !== -1 && (
                  <>
                    <button
                      onClick={() => openEditModal(selectedCharacter)}
                      className="p-1 hover:bg-gray-100 dark:hover:bg-gray-700 rounded"
                      title="编辑"
                    >
                      <Edit className="h-4 w-4 text-gray-500" />
                    </button>
                    <button
                      onClick={() => {
                        if (confirm(`确定要删除角色 "${selectedCharacter.name}" 吗？此操作不可恢复。`)) {
                          deleteMutation.mutate(selectedCharacter.id)
                        }
                      }}
                      className="p-1 hover:bg-red-100 dark:hover:bg-red-900/30 rounded"
                      title="删除"
                    >
                      <Trash2 className="h-4 w-4 text-red-500" />
                    </button>
                  </>
                )}
                <button
                  onClick={() => setSelectedCharacter(null)}
                  className="p-1 hover:bg-gray-100 dark:hover:bg-gray-700 rounded"
                >
                  <X className="h-5 w-5 text-gray-500" />
                </button>
              </div>
            </div>

            <div className="space-y-4">
              <div className="flex items-center gap-2">
                <span className="text-sm text-gray-500">类型:</span>
                <span className="px-2 py-1 text-xs font-medium rounded-full bg-gray-100 dark:bg-gray-700">
                  {roleTypeMap[selectedCharacter.role_type]?.label || selectedCharacter.role_type}
                </span>
              </div>

              {selectedCharacter.profile && Object.entries(selectedCharacter.profile).length > 0 && (
                <div>
                  <h3 className="font-medium text-gray-900 dark:text-white mb-3">详细人设</h3>
                  <div className="bg-gray-50 dark:bg-gray-700 rounded-lg p-4 space-y-3">
                    {/* 基本信息 */}
                    {((selectedCharacter.profile as any).age || (selectedCharacter.profile as any).gender) && (
                      <div className="pb-3 border-b border-gray-200 dark:border-gray-600">
                        <p className="text-xs font-medium text-gray-500 mb-2">基本信息</p>
                        {(selectedCharacter.profile as any).age && (
                          <p className="text-sm text-gray-700 dark:text-gray-300">
                            年龄: {(selectedCharacter.profile as any).age}岁
                          </p>
                        )}
                        {(selectedCharacter.profile as any).gender && (
                          <p className="text-sm text-gray-700 dark:text-gray-300">
                            性别: {(selectedCharacter.profile as any).gender}
                          </p>
                        )}
                      </div>
                    )}

                    {/* 外貌描述 */}
                    {(selectedCharacter.profile as any).appearance && (
                      <div>
                        <p className="text-xs font-medium text-gray-500 mb-1">外貌</p>
                        <p className="text-sm text-gray-700 dark:text-gray-300 leading-relaxed">
                          {(selectedCharacter.profile as any).appearance}
                        </p>
                      </div>
                    )}

                    {/* 性格特征 */}
                    {(selectedCharacter.profile as any).personality && (
                      <div>
                        <p className="text-xs font-medium text-gray-500 mb-1">性格</p>
                        <p className="text-sm text-gray-700 dark:text-gray-300 leading-relaxed">
                          {(selectedCharacter.profile as any).personality}
                        </p>
                      </div>
                    )}

                    {/* MBTI类型 */}
                    {(selectedCharacter.profile as any).mbti && (
                      <div>
                        <p className="text-xs font-medium text-gray-500 mb-1">MBTI类型</p>
                        <span className="inline-block px-2 py-1 text-xs font-mono bg-blue-100 text-blue-700 rounded dark:bg-blue-900/30 dark:text-blue-400">
                          {(selectedCharacter.profile as any).mbti}
                        </span>
                      </div>
                    )}

                    {/* 背景故事 */}
                    {(selectedCharacter.profile as any).background && (
                      <div>
                        <p className="text-xs font-medium text-gray-500 mb-1">背景</p>
                        <p className="text-sm text-gray-700 dark:text-gray-300 leading-relaxed">
                          {(selectedCharacter.profile as any).background}
                        </p>
                      </div>
                    )}

                    {/* 目标 */}
                    {(selectedCharacter.profile as any).goals && Array.isArray((selectedCharacter.profile as any).goals) && (selectedCharacter.profile as any).goals.length > 0 && (
                      <div>
                        <p className="text-xs font-medium text-gray-500 mb-1">目标</p>
                        <ul className="text-sm text-gray-700 dark:text-gray-300 list-disc list-inside space-y-1">
                          {(selectedCharacter.profile as any).goals.map((goal: string, i: number) => (
                            <li key={i}>{goal}</li>
                          ))}
                        </ul>
                      </div>
                    )}

                    {/* 恐惧 */}
                    {(selectedCharacter.profile as any).fears && Array.isArray((selectedCharacter.profile as any).fears) && (selectedCharacter.profile as any).fears.length > 0 && (
                      <div>
                        <p className="text-xs font-medium text-gray-500 mb-1">恐惧</p>
                        <ul className="text-sm text-gray-700 dark:text-gray-300 list-disc list-inside space-y-1">
                          {(selectedCharacter.profile as any).fears.map((fear: string, i: number) => (
                            <li key={i}>{fear}</li>
                          ))}
                        </ul>
                      </div>
                    )}

                    {/* 技能 */}
                    {(selectedCharacter.profile as any).skills && Array.isArray((selectedCharacter.profile as any).skills) && (selectedCharacter.profile as any).skills.length > 0 && (
                      <div>
                        <p className="text-xs font-medium text-gray-500 mb-1">技能</p>
                        <div className="flex flex-wrap gap-1">
                          {(selectedCharacter.profile as any).skills.map((skill: string, i: number) => (
                            <span key={i} className="text-xs px-2 py-0.5 bg-purple-100 text-purple-700 rounded dark:bg-purple-900/30 dark:text-purple-400">
                              {skill}
                            </span>
                          ))}
                        </div>
                      </div>
                    )}

                    {/* 人际关系 */}
                    {(selectedCharacter.profile as any).relationships && typeof (selectedCharacter.profile as any).relationships === 'object' && Object.keys((selectedCharacter.profile as any).relationships).length > 0 && (
                      <div>
                        <p className="text-xs font-medium text-gray-500 mb-1">人际关系</p>
                        <div className="text-sm text-gray-700 dark:text-gray-300 space-y-1">
                          {Object.entries((selectedCharacter.profile as any).relationships).map(([name, relation]) => (
                            <div key={name} className="flex">
                              <span className="font-medium w-24 shrink-0">{name}:</span>
                              <span className="text-gray-600 dark:text-gray-400">{String(relation)}</span>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                </div>
              )}

              {selectedCharacter.current_status && (
                <div>
                  <h3 className="font-medium text-gray-900 dark:text-white mb-2">当前状态</h3>
                  <p className="text-sm text-gray-600 dark:text-gray-400 bg-gray-50 dark:bg-gray-700 rounded-lg p-4">
                    {selectedCharacter.current_status}
                  </p>
                </div>
              )}

              <div className="grid grid-cols-3 gap-4 pt-4 border-t border-gray-200 dark:border-gray-700">
                <div className="text-center">
                  <p className="text-2xl font-bold text-primary-600">
                    {selectedCharacter.first_appearance}
                  </p>
                  <p className="text-xs text-gray-500">首次出场</p>
                </div>
                <div className="text-center">
                  <p className="text-2xl font-bold text-primary-600">
                    {selectedCharacter.appearance_count}
                  </p>
                  <p className="text-xs text-gray-500">出场次数</p>
                </div>
                <div className="text-center">
                  <p className="text-2xl font-bold text-primary-600">
                    {Math.round(selectedCharacter.arc_progress * 100)}%
                  </p>
                  <p className="text-xs text-gray-500">角色成长</p>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* 编辑角色弹窗 */}
      {editingCharacter && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-white dark:bg-gray-800 rounded-xl p-6 w-full max-w-2xl mx-4 max-h-[80vh] overflow-y-auto">
            <div className="flex justify-between items-center mb-4">
              <h2 className="text-xl font-bold text-gray-900 dark:text-white">
                编辑角色: {editingCharacter.name}
              </h2>
              <button
                onClick={() => setEditingCharacter(null)}
                className="p-1 hover:bg-gray-100 dark:hover:bg-gray-700 rounded"
              >
                <X className="h-5 w-5 text-gray-500" />
              </button>
            </div>

            <div className="space-y-4">
              {/* 基本信息组 */}
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                    年龄
                  </label>
                  <input
                    type="text"
                    value={(editingCharacter.profile as any)?.age || ''}
                    onChange={(e) => setEditingCharacter({
                      ...editingCharacter,
                      profile: { ...(editingCharacter.profile as any), age: e.target.value }
                    })}
                    className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white text-sm"
                    placeholder="年龄"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                    性别
                  </label>
                  <select
                    value={(editingCharacter.profile as any)?.gender || ''}
                    onChange={(e) => setEditingCharacter({
                      ...editingCharacter,
                      profile: { ...(editingCharacter.profile as any), gender: e.target.value }
                    })}
                    className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white text-sm"
                  >
                    <option value="">请选择</option>
                    <option value="男">男</option>
                    <option value="女">女</option>
                    <option value="其他">其他</option>
                  </select>
                </div>
              </div>

              {/* 外貌 */}
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                  外貌描述
                </label>
                <textarea
                  value={(editingCharacter.profile as any)?.appearance || ''}
                  onChange={(e) => setEditingCharacter({
                    ...editingCharacter,
                    profile: { ...(editingCharacter.profile as any), appearance: e.target.value }
                  })}
                  rows={3}
                  className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white text-sm resize-none"
                  placeholder="角色的外貌特征"
                />
              </div>

              {/* 性格 */}
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                  性格特征
                </label>
                <textarea
                  value={(editingCharacter.profile as any)?.personality || ''}
                  onChange={(e) => setEditingCharacter({
                    ...editingCharacter,
                    profile: { ...(editingCharacter.profile as any), personality: e.target.value }
                  })}
                  rows={3}
                  className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white text-sm resize-none"
                  placeholder="角色的性格特点"
                />
              </div>

              {/* MBTI */}
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                  MBTI类型
                </label>
                <input
                  type="text"
                  value={(editingCharacter.profile as any)?.mbti || ''}
                  onChange={(e) => setEditingCharacter({
                    ...editingCharacter,
                    profile: { ...(editingCharacter.profile as any), mbti: e.target.value.toUpperCase() }
                  })}
                  className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white text-sm font-mono"
                  placeholder="例如: INTJ, ENFP"
                  maxLength={4}
                />
              </div>

              {/* 背景故事 */}
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                  背景故事
                </label>
                <textarea
                  value={(editingCharacter.profile as any)?.background || ''}
                  onChange={(e) => setEditingCharacter({
                    ...editingCharacter,
                    profile: { ...(editingCharacter.profile as any), background: e.target.value }
                  })}
                  rows={4}
                  className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white text-sm resize-none"
                  placeholder="角色的成长经历和背景"
                />
              </div>

              {/* 目标 */}
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                  目标（每行一个）
                </label>
                <textarea
                  value={Array.isArray((editingCharacter.profile as any)?.goals)
                    ? (editingCharacter.profile as any).goals.join('\n')
                    : (editingCharacter.profile as any)?.goals || ''
                  }
                  onChange={(e) => setEditingCharacter({
                    ...editingCharacter,
                    profile: {
                      ...(editingCharacter.profile as any),
                      goals: e.target.value.split('\n').filter(g => g.trim())
                    }
                  })}
                  rows={3}
                  className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white text-sm resize-none"
                  placeholder="角色想要达成的目标，每行一个"
                />
              </div>

              {/* 恐惧 */}
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                  恐惧（每行一个）
                </label>
                <textarea
                  value={Array.isArray((editingCharacter.profile as any)?.fears)
                    ? (editingCharacter.profile as any).fears.join('\n')
                    : (editingCharacter.profile as any)?.fears || ''
                  }
                  onChange={(e) => setEditingCharacter({
                    ...editingCharacter,
                    profile: {
                      ...(editingCharacter.profile as any),
                      fears: e.target.value.split('\n').filter(f => f.trim())
                    }
                  })}
                  rows={3}
                  className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white text-sm resize-none"
                  placeholder="角色害怕的事物，每行一个"
                />
              </div>

              {/* 技能 */}
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                  技能（用逗号分隔）
                </label>
                <input
                  type="text"
                  value={Array.isArray((editingCharacter.profile as any)?.skills)
                    ? (editingCharacter.profile as any).skills.join(', ')
                    : (editingCharacter.profile as any)?.skills || ''
                  }
                  onChange={(e) => setEditingCharacter({
                    ...editingCharacter,
                    profile: {
                      ...(editingCharacter.profile as any),
                      skills: e.target.value.split(',').map(s => s.trim()).filter(s => s)
                    }
                  })}
                  className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white text-sm"
                  placeholder="例如: 武力, 谋略, 医术"
                />
              </div>

              <div className="flex gap-3 pt-4">
                <button
                  onClick={() => setEditingCharacter(null)}
                  className="flex-1 px-4 py-2 border border-gray-300 dark:border-gray-600 text-gray-700 dark:text-gray-300 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-700"
                >
                  取消
                </button>
                <button
                  onClick={() => {
                    if (editingCharacter) {
                      updateMutation.mutate({
                        characterId: editingCharacter.id,
                        data: { ...editingCharacter }
                      })
                    }
                  }}
                  disabled={updateMutation.isPending}
                  className="flex-1 px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700 disabled:opacity-50 flex items-center justify-center gap-2"
                >
                  {updateMutation.isPending ? (
                    <span>保存中...</span>
                  ) : (
                    <>
                      <Check className="h-4 w-4" />
                      保存更改
                    </>
                  )}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
      </>
      )}
    </div>
  )
}
