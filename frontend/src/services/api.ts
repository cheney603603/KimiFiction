import axios, { type AxiosInstance, type AxiosRequestConfig } from 'axios'
import type {
  WorkflowStatus,
  WorkflowGraphProgress,
  TrainingBatch,
  TrainingReport,
  TrainingEpisode,
  TrainingStatus,
  RubricEvaluation,
  StartTrainingRequest,
} from '../types'

type ApiInstance = Omit<AxiosInstance, 'get' | 'post' | 'put' | 'delete' | 'patch'> & {
  get<T = any, D = any>(url: string, config?: AxiosRequestConfig<D>): Promise<T>
  post<T = any, D = any>(url: string, data?: D, config?: AxiosRequestConfig<D>): Promise<T>
  put<T = any, D = any>(url: string, data?: D, config?: AxiosRequestConfig<D>): Promise<T>
  delete<T = any, D = any>(url: string, config?: AxiosRequestConfig<D>): Promise<T>
  patch<T = any, D = any>(url: string, data?: D, config?: AxiosRequestConfig<D>): Promise<T>
}

const API_BASE_URL = (import.meta as any).env?.VITE_API_URL || '/api/v1'

export const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
  timeout: 120000,  // 增加到120秒，因为AI生成可能需要较长时间
}) as ApiInstance

// 从localStorage获取token
const getToken = () => localStorage.getItem('access_token')

// 请求拦截器
api.interceptors.request.use(
  (config) => {
    // 添加认证token
    const token = getToken()
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }
    return config
  },
  (error) => {
    return Promise.reject(error)
  }
)

// 响应拦截器
api.interceptors.response.use(
  (response) => response.data,
  (error) => {
    if (error.response?.status === 401) {
      // 未授权，清除token并跳转到登录页
      localStorage.removeItem('access_token')
      localStorage.removeItem('user')
      window.location.href = '/login'
    }
    return Promise.reject(error)
  }
)

// 认证相关API
export const authApi = {
  register: (data: { username: string; email: string; password: string; nickname?: string }) =>
    api.post('/auth/register', data),
  
  login: (data: { username: string; password: string }) =>
    api.post('/auth/login', data),
  
  getMe: () =>
    api.get('/auth/me'),
  
  updateMe: (data: Partial<{ nickname: string; email: string; avatar: string }>) =>
    api.put('/auth/me', data),
  
  changePassword: (data: { old_password: string; new_password: string }) =>
    api.post('/auth/change-password', data),
  
  refresh: () =>
    api.post('/auth/refresh'),
}

// 小说相关API
export const novelApi = {
  list: (params?: { skip?: number; limit?: number; status?: string }) =>
    api.get('/novels', { params }),
  
  get: (id: number) =>
    api.get(`/novels/${id}`),
  
  create: (data: { title: string; genre?: string; style_prompt?: string }) =>
    api.post('/novels', data),
  
  update: (id: number, data: Partial<{ title: string; genre: string; status: string }>) =>
    api.put(`/novels/${id}`, data),
  
  delete: (id: number) =>
    api.delete(`/novels/${id}`),
  
  getStats: (id: number) =>
    api.get(`/novels/${id}/stats`),

  hardDelete: (id: number) =>
    api.delete(`/novels/${id}/hard`),
}

// 章节相关API
export const chapterApi = {
  list: (novelId: number, params?: { skip?: number; limit?: number }) =>
    api.get(`/chapters/novel/${novelId}`, { params }),
  
  get: (id: number) =>
    api.get(`/chapters/${id}`),
  
  getByNumber: (novelId: number, chapterNumber: number) =>
    api.get(`/chapters/novel/${novelId}/chapter/${chapterNumber}`),
  
  create: (data: {
    novel_id: number
    chapter_number: number
    title: string
    content: string
    summary?: string
  }) => api.post('/chapters', data),
  
  update: (id: number, data: Partial<{ title: string; content: string; status: string }>) =>
    api.put(`/chapters/${id}`, data),
  
  delete: (id: number) =>
    api.delete(`/chapters/${id}`),
  
  generate: (data: {
    novel_id: number
    chapter_number?: number
    outline_guidance?: string
  }) => api.post('/chapters/generate', data),
  
  getTaskStatus: (taskId: string) =>
    api.get(`/chapters/task/${taskId}`),
}

// 角色相关API（兼容旧版）
export const characterApi = {
  list: (novelId: number, roleType?: string) =>
    api.get(`/characters/novel/${novelId}`, { params: { role_type: roleType } }),
  
  get: (id: number) =>
    api.get(`/characters/${id}`),
  
  create: (data: {
    novel_id: number
    name: string
    role_type?: string
    profile?: Record<string, unknown>
  }) => api.post('/characters', data),
  
  update: (id: number, data: Partial<{ name: string; role_type: string; profile: Record<string, unknown> }>) =>
    api.put(`/characters/${id}`, data),
  
  delete: (id: number) =>
    api.delete(`/characters/${id}`),
  
  getTimeline: (id: number) =>
    api.get(`/characters/${id}/timeline`),
}

// 实体管理API（新版）
export const entityApi = {
  list: (novelId: number, entityType?: string) =>
    api.get(`/entities/novel/${novelId}`, { params: { entity_type: entityType } }),
  
  get: (entityId: string) =>
    api.get(`/entities/${entityId}`),
  
  create: (data: {
    novel_id: number
    canonical_name: string
    entity_type: string
    aliases?: string[]
    state_vector?: Record<string, unknown>
    narrative_summary?: string
  }) => api.post('/entities', data),
  
  update: (entityId: string, data: Partial<{
    canonical_name: string
    entity_type: string
    aliases: string[]
    state_vector: Record<string, unknown>
    narrative_summary: string
  }>) => api.put(`/entities/${entityId}`, data),
  
  delete: (entityId: string) =>
    api.delete(`/entities/${entityId}`),
  
  // 关系API
  createRelationship: (data: {
    novel_id: number
    source_id: string
    target_id: string
    relation_type: string
  }) => api.post('/entities/relationships', data),
  
  listRelationships: (novelId: number) =>
    api.get(`/entities/novel/${novelId}/relationships`),
}

// 大纲相关API
export const outlineApi = {
  list: (novelId: number) =>
    api.get(`/outlines/novel/${novelId}`),
  
  get: (id: number) =>
    api.get(`/outlines/${id}`),
  
  create: (data: {
    novel_id: number
    volume_number: number
    volume_title: string
    arcs?: unknown[]
  }) => api.post('/outlines', data),
  
  update: (id: number, data: Partial<{ volume_title: string; arcs: unknown[] }>) =>
    api.put(`/outlines/${id}`, data),
  
  delete: (id: number) =>
    api.delete(`/outlines/${id}`),
  
  generate: (data: {
    novel_id: number
    total_volumes?: number
    chapters_per_volume?: number
  }) => api.post('/outlines/generate', data),
}

// 工作流相关API
export const workflowApi = {
  // 兼容旧版
  start: (data: { title: string; initial_idea?: string; preferred_genre?: string }) =>
    api.post('/workflow/start', data),
  
  getState: (novelId: number) =>
    api.get(`/workflow/state/${novelId}`),
  
  analyzeGenre: (userInput: string) =>
    api.post('/workflow/analyze-genre', { user_input: userInput }),
  
  submitInput: (novelId: number, message: string, context?: Record<string, unknown>) =>
    api.post(`/workflow/user-input/${novelId}`, { message, context }),
  
  generateCharacters: (novelId: number) =>
    api.post(`/workflow/generate-characters/${novelId}`),
  
  generateOutline: (novelId: number) =>
    api.post(`/workflow/generate-outline/${novelId}`),
  
  startWriting: (novelId: number, autoMode?: boolean, targetChapters?: number) =>
    api.post(`/workflow/start-writing/${novelId}`, { auto_mode: autoMode, target_chapters: targetChapters }),
  
  pause: (novelId: number) =>
    api.post(`/workflow/pause/${novelId}`),
  
  resume: (novelId: number) =>
    api.post(`/workflow/resume/${novelId}`),
  
  // 新版API
  getProgress: (novelId: number) =>
    api.get(`/workflow/progress/${novelId}`),
  
  getPhaseResult: (novelId: number, phase: string) =>
    api.get(`/workflow/phase-result/${novelId}/${phase}`),
  
  getPhasePromptInfo: (novelId: number, phase: string) =>
    api.get(`/workflow/phase-prompt/${novelId}/${phase}`),
  
  togglePhaseCompletion: (novelId: number, phase: string, inputData?: Record<string, unknown>) =>
    api.post(`/workflow/phase-toggle/${novelId}/${phase}`, { phase, input_data: inputData }),
  
  switchPhase: (novelId: number, phase: string) =>
    api.post(`/workflow/phase-switch/${novelId}`, { phase }),
  
  executePhase: (novelId: number, data: { phase: string; input_data?: Record<string, unknown>; timeout?: number }) =>
    api.post(`/workflow/phase/${novelId}`, data),
  
  writeChapter: (novelId: number, data: {
    chapter_number: number
    outline?: Record<string, unknown>
    auto_mode?: boolean
    timeout?: number
    writing_style?: string
    env_description_level?: string
    dialogue_ratio?: number
    notes?: string
  }) =>
    api.post(`/workflow/chapter/${novelId}`, data),
  
  reviseChapter: (novelId: number, data: { chapter_number: number; feedback: string; scope: 'chapter' | 'framework' }) =>
    api.post(`/workflow/revise/${novelId}`, data),
  
  confirmAction: (novelId: number, data: { confirmation: string; response?: string }) =>
    api.post(`/workflow/confirm/${novelId}`, data),
  
  createSnapshot: (novelId: number, reason?: string) =>
    api.post(`/workflow/snapshot/${novelId}`, null, { params: { reason } }),
  
  restoreSnapshot: (workflowId: string, snapshotId: string) =>
    api.post(`/workflow/snapshot/${workflowId}/restore/${snapshotId}`),
  
  // 章节细纲 CRUD
  listChapterOutlines: (novelId: number) =>
    api.get(`/workflow/chapter-outlines/${novelId}`),

  getChapterOutline: (novelId: number, chapterNumber: number) =>
    api.get(`/workflow/chapter-outlines/${novelId}/${chapterNumber}`),

  updateChapterOutline: (novelId: number, chapterNumber: number, data: Record<string, unknown>) =>
    api.put(`/workflow/chapter-outlines/${novelId}/${chapterNumber}`, data),

  batchUpdateChapterOutlines: (novelId: number, chapterOutlines: unknown[]) =>
    api.put(`/workflow/chapter-outlines/${novelId}`, { chapter_outlines: chapterOutlines }),

  deleteChapterOutline: (novelId: number, chapterNumber: number) =>
    api.delete(`/workflow/chapter-outlines/${novelId}/${chapterNumber}`),

  // WebSocket连接
  connectWebSocket: (novelId: number) => {
    const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const wsUrl = `${wsProtocol}//${window.location.host}/api/v1/workflow/ws/${novelId}`
    return new WebSocket(wsUrl)
  },
  
  // 工作流日志
  getWorkflowLogs: (workflowId: string, limit?: number) =>
    api.get(`/workflow/logs/${workflowId}`, { params: { limit } }),
  
  // 任务进度查询（用于异步任务轮询）
  getTaskProgress: (taskId: string) =>
    api.get(`/workflow/task-progress/${taskId}`),
}

// LLM配置API
export const llmConfigApi = {
  // 保存LLM配置到后端
  saveConfig: (config: {
    provider: string
    apiKey?: string
    baseUrl?: string
    model?: string
    responseTime?: number
    timeout?: number
  }) => api.post('/llm/config', config),

  // 获取当前超时时间
  getTimeout: () => api.get('/llm/config/timeout'),

  // 获取当前配置
  getCurrentConfig: () => api.get('/llm/config/current'),

  // 测试连接（通过后端代理）
  testConnection: (config: {
    provider: string
    apiKey?: string
    baseUrl?: string
    model?: string
  }) => api.post('/llm/config/test', config),
}

// 记忆相关API
export const memoryApi = {
  list: (novelId: number, params?: { node_type?: string; unresolved_only?: boolean }) =>
    api.get(`/memory/nodes/novel/${novelId}`, { params }),
  
  get: (id: number) =>
    api.get(`/memory/nodes/${id}`),
  
  create: (data: {
    novel_id: number
    node_type: string
    title: string
    content: string
    chapter_range: string
  }) => api.post('/memory/nodes', data),
  
  update: (id: number, data: Partial<{ title: string; content: string; is_resolved: boolean }>) =>
    api.put(`/memory/nodes/${id}`, data),
  
  delete: (id: number) =>
    api.delete(`/memory/nodes/${id}`),
  
  search: (data: {
    novel_id: number
    query: string
    top_k?: number
  }) => api.post('/memory/search', data),
  
  consolidate: (novelId: number, chapterThreshold?: number) =>
    api.post(`/memory/consolidate/${novelId}`, null, { params: chapterThreshold ? { chapter_threshold: chapterThreshold } : {} }),
  
  buildContext: (novelId: number, chapterNumber: number) =>
    api.get(`/memory/context/${novelId}`, { params: { chapter_number: chapterNumber } }),
  
  getStats: (novelId: number) =>
    api.get(`/memory/stats/${novelId}`),
}

// 任务相关API
export const taskApi = {
  getStatus: (taskId: string) =>
    api.get(`/tasks/${taskId}`),
}

// 导出相关API
export const exportApi = {
  exportTxt: (novelId: number, includeToc: boolean = true) =>
    api.get(`/export/novel/${novelId}/txt`, {
      params: { include_toc: includeToc },
      responseType: 'blob',
    }),
  
  exportMarkdown: (novelId: number) =>
    api.get(`/export/novel/${novelId}/markdown`, {
      responseType: 'blob',
    }),
  
  exportJson: (novelId: number) =>
    api.get(`/export/novel/${novelId}/json`, {
      responseType: 'blob',
    }),
  
  exportCharacters: (novelId: number, format: 'markdown' | 'json' = 'markdown') =>
    api.get(`/export/novel/${novelId}/characters`, {
      params: { format },
      responseType: 'blob',
    }),
  
  exportOutline: (novelId: number) =>
    api.get(`/export/novel/${novelId}/outline`, {
      responseType: 'blob',
    }),
}

// ─────────────────────────────────────────────────────────────
// 工作流状态图相关API（合并到上方 workflowApi）
// ─────────────────────────────────────────────────────────────
export const workflowGraphApi = {
  getStatus: (workflowId: string) =>
    api.get<WorkflowStatus>(`/workflow/status/${workflowId}`),

  getProgress: (novelId: number) =>
    api.get<WorkflowGraphProgress>(`/workflow/progress/${novelId}`),

  startWorkflow: (data: { novel_id: number; user_input?: string }) =>
    api.post('/workflow/start', data),
}

// ─────────────────────────────────────────────────────────────
// 采样评测 API
// ─────────────────────────────────────────────────────────────
export const sampledEvalApi = {
  run: (data: {
    text: string
    num_blocks: number
    max_bytes_per_block: number
    eval_type: string
    genre?: string
  }) => api.post('/training/evaluation/run-sampled', data),
}

// ─────────────────────────────────────────────────────────────
// 评测辅助 API
// ─────────────────────────────────────────────────────────────
export const evaluationApi = {
  getReferences: () => api.get('/training/evaluation/references'),
  listResults: (limit?: number) => api.get('/training/evaluation/results', { params: { limit: limit || 20 } }),
  // 获取章节八维评分
  getChapterEvaluation: (novelId: number, chapterNumber: number) =>
    api.get(`/training/evaluation/chapter/${novelId}/${chapterNumber}`),
  // 运行章节八维评分
  runChapterEvaluation: (novelId: number, chapterNumber: number, genre?: string, numBlocks?: number) =>
    api.post(`/training/evaluation/chapter/${novelId}/${chapterNumber}/run`, null, {
      params: { genre, num_blocks: numBlocks || 3 }
    }),
  // 读取参考小说内容
  getReferenceContent: (filename: string) =>
    api.get(`/training/evaluation/reference/${encodeURIComponent(filename)}`),
  // 获取采样评测历史记录列表（分页）
  getHistory: (page?: number, pageSize?: number) =>
    api.get('/training/evaluation/history', { params: { page: page || 1, page_size: pageSize || 15 } }),
  // 获取单条历史记录详情
  getHistoryDetail: (historyId: number) =>
    api.get(`/training/evaluation/history/${historyId}`),
}

// ─────────────────────────────────────────────────────────────
// RL训练相关API
// ─────────────────────────────────────────────────────────────
export const trainingApi = {
  // 批次管理
  listBatches: (params?: { novel_id?: number; status?: string; limit?: number }) =>
    api.get<TrainingBatch[]>('/training/batches', { params }),

  getBatchReport: (batchId: number) =>
    api.get<TrainingReport>(`/training/batch/${batchId}/report`),

  getBatchEpisodes: (batchId: number, params?: { chapter_number?: number; limit?: number }) =>
    api.get<TrainingEpisode[]>(`/training/batch/${batchId}/episodes`, { params }),

  getTrainingStatus: () =>
    api.get<TrainingStatus>('/training/status'),

  // Rubric评测
  listEvaluations: (params: { novel_id: number; eval_type?: string; chapter_number?: number; limit?: number }) =>
    api.get<RubricEvaluation[]>('/training/evaluations', { params }),

  getEvaluation: (evaluationId: number) =>
    api.get<RubricEvaluation>(`/training/evaluation/${evaluationId}`),

  // 训练控制
  startTraining: (data: StartTrainingRequest) =>
    api.post('/training/start', data),
}

// ─────────────────────────────────────────────────────────────
// Pipeline API（完整训练流程）
// ─────────────────────────────────────────────────────────────
export const pipelineApi = {
  // 启动Pipeline（异步）
  start: (data: {
    novel_id: number
    project_path?: string
    run_imitation?: boolean
    run_lora?: boolean
    run_grpo?: boolean
    num_imitation_samples?: number
    lora_epochs?: number
    grpo_iterations?: number
    test_prompts?: string[]
  }) => api.post('/training-pipeline/start', data),

  // 获取Pipeline状态
  getStatus: (pipelineId: string) =>
    api.get(`/training-pipeline/status/${pipelineId}`),

  // 获取Pipeline结果
  getResult: (pipelineId: string) =>
    api.get(`/training-pipeline/result/${pipelineId}`),

  // 获取对比详情
  getComparisonDetail: (pipelineId: string, testCase?: number) =>
    api.get(`/training-pipeline/comparison/${pipelineId}`, { params: testCase !== undefined ? { test_case: testCase } : {} }),

  // 同步运行Pipeline（小规模测试）
  runSync: (data: {
    novel_id: number
    project_path?: string
    run_imitation?: boolean
    run_lora?: boolean
    run_grpo?: boolean
    num_imitation_samples?: number
    lora_epochs?: number
    grpo_iterations?: number
  }) => api.post('/training-pipeline/run-sync', data),

  // 列出所有Pipeline
  list: () =>
    api.get('/training-pipeline/list'),

  // 删除Pipeline记录
  delete: (pipelineId: string) =>
    api.delete(`/training-pipeline/${pipelineId}`),
}

// 评分优化分析API
export const evaluationOptimizerApi = {
  // 列出参考小说
  listReferenceNovels: () =>
    api.get('/training/evaluation/reference-novels'),

  // 分析规则
  analyzeRules: (data: {
    good_novel_files: string[]
    bad_novel_files: string[]
    blocks_per_novel?: number
    max_bytes_per_block?: number
    genre?: string
  }) => api.post('/training/evaluation/analyze-rules', data),

  // 流式分析规则
  analyzeRulesStream: async (
    data: {
      good_novel_files: string[]
      bad_novel_files: string[]
      blocks_per_novel?: number
      max_bytes_per_block?: number
      genre?: string
    },
    onProgress: (progress: any) => void
  ) => {
    const response = await fetch(`${API_BASE_URL}/training/evaluation/analyze-rules/stream`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${getToken() || ''}`,
      },
      body: JSON.stringify(data),
    })

    if (!response.ok) {
      throw new Error('分析请求失败')
    }

    const reader = response.body?.getReader()
    if (!reader) throw new Error('无法读取响应')

    const decoder = new TextDecoder()
    let buffer = ''

    while (true) {
      const { done, value } = await reader.read()
      if (done) break

      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n')
      buffer = lines.pop() || ''

      for (const line of lines) {
        if (line.trim()) {
          try {
            const data = JSON.parse(line)
            onProgress(data)
          } catch (e) {
            console.error('解析进度数据失败:', line)
          }
        }
      }
    }
  },

  // 保存优化历史
  saveHistory: (data: {
    description: string
    good_novels: string[]
    bad_novels: string[]
    blocks_per_novel: number
    total_samples: number
    rule_changes: any[]
    dimension_changes: any[]
    applied: boolean
  }) => api.post('/training/evaluation/optimization-history', data),

  // 获取优化历史列表
  listHistory: (params?: { page?: number; page_size?: number }) =>
    api.get('/training/evaluation/optimization-history', { params }),

  // 获取单条历史详情
  getHistoryDetail: (id: string) =>
    api.get(`/training/evaluation/optimization-history/${id}`),

  // 应用优化
  applyHistory: (id: string) =>
    api.post(`/training/evaluation/optimization-history/${id}/apply`),

  // 迭代优化
  optimizeRulesIterative: async (
    data: {
      good_novel_files: string[]
      bad_novel_files: string[]
      blocks_per_novel: number
      max_bytes_per_block: number
      genre: string
      max_iterations: number
      discrimination_threshold: number
      convergence_window: number
      convergence_threshold: number
    },
    onProgress: (data: any) => void
  ) => {
    const response = await fetch(`${API_BASE_URL}/training/evaluation/optimize-rules/iterative`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${getToken() || ''}`,
      },
      body: JSON.stringify(data),
    })

    if (!response.ok) {
      throw new Error('迭代优化请求失败')
    }

    const reader = response.body?.getReader()
    if (!reader) throw new Error('无法读取响应')

    const decoder = new TextDecoder()
    let buffer = ''

    while (true) {
      const { done, value } = await reader.read()
      if (done) break

      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n')
      buffer = lines.pop() || ''

      for (const line of lines) {
        if (line.trim()) {
          try {
            const data = JSON.parse(line)
            onProgress(data)
          } catch (e) {
            console.error('解析进度数据失败:', line)
          }
        }
      }
    }
  },

  // 确认规则变更
  confirmRuleChanges: (data: {
    session_id: string
    confirmed_changes: string[]
    rejected_changes: string[]
  }) => api.post('/training/evaluation/optimize-rules/confirm', data),

  // 列出备份
  listBackups: () => api.get('/training/evaluation/optimize-rules/backups'),

  // 恢复备份
  restoreBackup: (data: { backup_name: string }) =>
    api.post('/training/evaluation/optimize-rules/restore', data),
}
