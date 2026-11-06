import { Routes, Route, Navigate } from 'react-router-dom'
import { Layout } from './components/Layout'
import { Dashboard } from './pages/Dashboard'
import { NovelDetail } from './pages/NovelDetail'
import { ChapterReader } from './pages/ChapterReader'
import { ChapterWriter } from './pages/ChapterWriter'
import { CharacterManager } from './pages/CharacterManager'
import { EntityManager } from './pages/EntityManager'
import { EntityGraph } from './pages/EntityGraph'
import { NovelMap } from './pages/NovelMap'
import { KnowledgeBase } from './pages/KnowledgeBase'
import { OutlineEditor } from './pages/OutlineEditor'
import { WorkflowChat } from './pages/WorkflowChat'
import { WorkflowPage } from './pages/WorkflowPage'
import { LLMSettings } from './pages/LLMSettings'
import { Usage } from './pages/Usage'
import { Rank } from './pages/Rank'
import { Login } from './pages/Login'
import { Register } from './pages/Register'
// 多智能体协作与评测页面
import { AgentWorkflow } from './pages/AgentWorkflow'
import { Evaluation } from './pages/Evaluation'
import EvaluationOptimizer from './pages/EvaluationOptimizer'
import SnapshotsPage from './pages/SnapshotsPage'

// 检查是否已登录
const isAuthenticated = () => {
  return !!localStorage.getItem('access_token')
}

// 受保护的路由组件
const ProtectedRoute = ({ children }: { children: React.ReactNode }) => {
  if (!isAuthenticated()) {
    return <Navigate to="/login" replace />
  }
  return <>{children}</>
}

function App() {
  return (
    <Routes>
      {/* 公开路由 */}
      <Route path="/login" element={<Login />} />
      <Route path="/register" element={<Register />} />

      {/* 受保护路由 */}
      <Route
        path="/"
        element={
          <ProtectedRoute>
            <Layout>{undefined}</Layout>
          </ProtectedRoute>
        }
      >
        <Route index element={<Dashboard />} />
        <Route path="novel/:novelId" element={<NovelDetail />} />
        <Route path="novel/:novelId/read/:chapterNumber?" element={<ChapterReader />} />
        <Route path="novel/:novelId/write" element={<ChapterWriter />} />
        <Route path="novel/:novelId/characters" element={<CharacterManager />} />
        <Route path="novel/:novelId/entities" element={<EntityManager />} />
        <Route path="novel/:novelId/graph" element={<EntityGraph />} />
        <Route path="novel/:novelId/map" element={<NovelMap />} />
        <Route path="novel/:novelId/knowledge" element={<KnowledgeBase />} />
        <Route path="novel/:novelId/outline" element={<OutlineEditor />} />
        <Route path="novel/:novelId/workflow" element={<WorkflowChat />} />
        <Route path="novel/:novelId/workflow/new" element={<WorkflowPage />} />
        <Route path="settings/llm" element={<LLMSettings />} />
        <Route path="usage" element={<Usage />} />
        <Route path="rank" element={<Rank />} />

        {/* 多智能体协作与评测 */}
        <Route path="workflow/graph" element={<AgentWorkflow />} />
        <Route path="evaluation" element={<Evaluation />} />
        <Route path="evaluation/optimizer" element={<EvaluationOptimizer />} />
        <Route path="novel/:novelId/snapshots" element={<SnapshotsPage />} />
      </Route>

      {/* 默认重定向 */}
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}

export default App
