// 小说相关类型
export interface Novel {
  id: number
  title: string
  genre?: string
  style_prompt?: string
  total_chapters: number
  current_chapter: number
  total_words: number
  status: 'planning' | 'writing' | 'paused' | 'completed'
  target_chapters: number
  words_per_chapter: number
  created_at: string
  updated_at: string
}

export interface NovelStats {
  novel_id: number
  title: string
  total_chapters: number
  total_words: number
  avg_words_per_chapter: number
  character_count: number
  completion_percentage: number
  status: string
}

// 章节相关类型
export interface Chapter {
  id: number
  novel_id: number
  chapter_number: number
  title: string
  content: string
  summary?: string
  key_events?: string[]
  characters_present?: string[]
  word_count: number
  status: 'draft' | 'review' | 'published'
  quality_score?: number
  created_at: string
  updated_at: string
}

export interface ChapterListItem {
  id: number
  novel_id: number
  chapter_number: number
  title: string
  summary?: string
  word_count: number
  status: string
  created_at: string
}

// 角色相关类型
export interface Character {
  id: number
  novel_id: number
  name: string
  role_type: 'protagonist' | 'antagonist' | 'supporting' | 'minor'
  profile: Record<string, unknown>
  current_status?: string
  arc_progress: number
  first_appearance: number
  last_appearance?: number
  appearance_count: number
  created_at: string
  updated_at: string
}

// 大纲相关类型
export interface Arc {
  arc_id: string
  title: string
  description: string
  start_chapter: number
  end_chapter: number
  key_events: string[]
  conflict?: string
  resolution?: string
}

export interface Outline {
  id: number
  novel_id: number
  volume_number: number
  volume_title: string
  arcs: Arc[]
  key_points?: string
  target_chapters: number
  actual_chapters: number
  summary?: string
  created_at: string
  updated_at: string
}

// 记忆节点相关类型
export interface MemoryNode {
  id: number
  novel_id: number
  node_type: 'plot_point' | 'character_moment' | 'world_building' | 'mystery' | 'conflict' | 'relationship'
  title: string
  content: string
  chapter_range: string
  specific_chapter?: number
  importance_score: number
  related_characters: string[]
  related_locations: string[]
  is_resolved: boolean
  resolved_chapter?: number
  created_at: string
  updated_at: string
}

// 工作流相关类型
export interface AgentMessage {
  role: 'system' | 'agent' | 'user'
  content: string
  message_type: 'text' | 'suggestion' | 'decision_point' | 'question'
  metadata?: Record<string, unknown>
  timestamp: string
}

export interface WorkflowState {
  novel_id: number
  current_state: string
  messages: AgentMessage[]
  waiting_for_user: boolean
  progress: {
    genre_confirmed: boolean
    plot_discussed: boolean
    characters_designed: boolean
    outline_generated: boolean
    writing_started: boolean
  }
  can_proceed: boolean
  suggestions?: string[]
}

export interface GenreAnalysis {
  suggested_genre: string
  sub_genres: string[]
  style_keywords: string[]
  tropes: string[]
  target_audience: string
  similar_works: string[]
  reasoning: string
}

// 列表响应类型
export interface ListResponse<T> {
  items: T[]
  total: number
  skip?: number
  limit?: number
}

// ===== 新版工作流相关类型 =====

// 工作流阶段
export type WorkflowPhase = 
  | 'demand_analysis'      // 需求分析
  | 'world_building'         // 世界观构建
  | 'character_design'      // 角色设计
  | 'outline_draft'         // 剧情大纲
  | 'plot_design'           // 冲突伏笔设计（在大纲之后）
  | 'outline_detail'         // 章节细纲
  | 'chapter_writing'        // 章节写作
  | 'chapter_review'         // 章节审核
  | 'chapter_revision'       // 章节修改
  | 'framework_adjustment'   // 框架调整
  | 'waiting_confirm'        // 等待确认
  | 'paused'                // 已暂停
  | 'completed'             // 已完成
  | 'error'                // 错误

// 工作流进度
export interface WorkflowProgress {
  workflow_id: string
  current_phase: WorkflowPhase
  phase_display: string
  progress_percent: number
  completed_phases: string[]
  current_chapter: number
  target_chapters: number
  completed_chapters: number
  is_waiting: boolean
  is_paused: boolean
  last_error?: string
}

// 任务执行结果
export interface TaskResult {
  success: boolean
  phase: string
  data?: Record<string, unknown>
  error?: string
  warning?: string
}

// 章节写作请求
export interface ChapterWriteRequest {
  chapter_number: number
  outline?: Record<string, unknown>
  auto_mode?: boolean
}

// 章节修订请求
export interface ChapterRevisionRequest {
  chapter_number: number
  feedback: string
  scope: 'chapter' | 'framework'
}

// 快照信息
export interface WorkflowSnapshot {
  snapshot_id: string
  workflow_id: string
  reason: string
  created_at: string
}

// WebSocket消息类型
export type WSMessageType = 
  | 'state_update'
  | 'phase_changed'
  | 'task_started'
  | 'task_completed'
  | 'task_failed'
  | 'chapter_generated'
  | 'waiting_confirmation'
  | 'user_confirmed'
  | 'error'
  | 'pong'
  | 'progress'

export interface WSMessage {
  type: WSMessageType
  data?: Record<string, unknown>
  timestamp: number
  message?: string
}

// 阶段配置
export interface PhaseConfig {
  id: WorkflowPhase
  name: string
  icon: string
  color: string
  description: string
}

// 创作设定
export interface NovelSettings {
  genre: string
  main_selling_points: string[]
  protagonist: string
  target_words: string
  style_reference?: string
}

// 世界观设定
export interface WorldSetting {
  world_name: string
  overview: string
  genre_type: string
  power_systems: PowerSystem[]
  social_structure: SocialStructure
  geography: Geography
  history: History
  culture: Culture
  key_rules: KeyRule[]
  conflicts: Conflict[]
  unique_features: string[]
}

// 角色设定
export interface CharacterProfile {
  name: string
  role_type: 'protagonist' | 'antagonist' | 'supporting' | 'minor'
  profile: {
    age?: string
    gender?: string
    appearance?: string
    personality?: string
    mbti?: string
    background?: string
    goals?: string[]
    fears?: string[]
    skills?: string[]
    relationships?: Record<string, string>
  }
  arc_description?: string
  current_status?: string
}

// 故事线设定
export interface PlotSetting {
  core_conflicts: CoreConflict[]
  foreshadowing_plan: Foreshadowing[]
  mystery_system: Mystery[]
  chapter_hooks: ChapterHook[]
  plot_rhythm: PlotRhythm
  character_arcs: CharacterArc[]
}

// 工作流执行日志
export interface WorkflowLog {
  timestamp: number
  time: string
  level: 'info' | 'warning' | 'error' | 'success'
  message: string
  step: string
  extra?: Record<string, unknown>
}
