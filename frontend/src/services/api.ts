import axios from 'axios'

const API_BASE_URL = (import.meta as any).env?.VITE_API_URL || 'http://localhost:8080/api/v1'

export const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
  timeout: 120000,  // 增加到120秒，因为AI生成可能需要较长时间
})

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

// 角色相关API
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
