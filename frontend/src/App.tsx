import { Routes, Route, Navigate } from 'react-router-dom'
import { Layout } from './components/Layout'
import { Dashboard } from './pages/Dashboard'
import { NovelDetail } from './pages/NovelDetail'
import { ChapterReader } from './pages/ChapterReader'
import { ChapterWriter } from './pages/ChapterWriter'
import { CharacterManager } from './pages/CharacterManager'
import { OutlineEditor } from './pages/OutlineEditor'
import { WorkflowChat } from './pages/WorkflowChat'
import { WorkflowPage } from './pages/WorkflowPage'
import { LLMSettings } from './pages/LLMSettings'
import { Login } from './pages/Login'
import { Register } from './pages/Register'
// 新的多智能体协作和RL训练可视化页面
import { AgentWorkflow } from './pages/AgentWorkflow'
import { TrainingDashboard } from './pages/TrainingDashboard'
import { RLVisualization } from './pages/RLVisualization'
import { Evaluation } from './pages/Evaluation'

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
        <Route path="novel/:novelId/outline" element={<OutlineEditor />} />
        <Route path="novel/:novelId/workflow" element={<WorkflowChat />} />
        <Route path="novel/:novelId/workflow/new" element={<WorkflowPage />} />
        <Route path="settings/llm" element={<LLMSettings />} />

        {/* 新增：多智能体协作与RL训练 */}
        <Route path="workflow/graph" element={<AgentWorkflow />} />
        <Route path="training" element={<TrainingDashboard />} />
        <Route path="training/:batchId" element={<RLVisualization />} />
        <Route path="evaluation" element={<Evaluation />} />
      </Route>

      {/* 默认重定向 */}
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}

export default App
