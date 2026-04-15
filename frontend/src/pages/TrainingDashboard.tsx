import React from 'react'
import { useNavigate } from 'react-router-dom'
import { trainingApi } from '../../services/api'

export const TrainingDashboard: React.FC = () => {
  const navigate = useNavigate()
  const [loading, setLoading] = React.useState(false)
  const [status, setStatus] = React.useState<React.ComponentProps<typeof trainingApi> | null>(null)

  return (
    <div className="p-6 max-w-7xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold">RL 训练中心</h1>
        <button
          className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50"
          disabled={loading}
        >
          {loading ? '运行中...' : '启动训练 Pipeline'}
        </button>
      </div>

      {/* 训练状态概览 */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
        <div className="bg-white dark:bg-gray-800 rounded-lg shadow p-5 border border-gray-200 dark:border-gray-700">
          <div className="text-sm text-gray-500 dark:text-gray-400 mb-1">训练批次</div>
          <div className="text-3xl font-bold text-gray-900 dark:text-white">0</div>
          <div className="text-xs text-green-600 mt-1">系统就绪</div>
        </div>
        <div className="bg-white dark:bg-gray-800 rounded-lg shadow p-5 border border-gray-200 dark:border-gray-700">
          <div className="text-sm text-gray-500 dark:text-gray-400 mb-1">平均奖励</div>
          <div className="text-3xl font-bold text-gray-900 dark:text-white">--</div>
          <div className="text-xs text-gray-400 mt-1">等待训练数据</div>
        </div>
        <div className="bg-white dark:bg-gray-800 rounded-lg shadow p-5 border border-gray-200 dark:border-gray-700">
          <div className="text-sm text-gray-500 dark:text-gray-400 mb-1">最佳提升</div>
          <div className="text-3xl font-bold text-blue-600">--%</div>
          <div className="text-xs text-gray-400 mt-1">Baseline: 0.64 (Qwen2.5-1.5B)</div>
        </div>
      </div>

      {/* 训练能力说明 */}
      <div className="bg-white dark:bg-gray-800 rounded-lg shadow border border-gray-200 dark:border-gray-700 mb-6">
        <div className="px-5 py-4 border-b border-gray-100 dark:border-gray-700">
          <h2 className="text-lg font-semibold text-gray-900 dark:text-white">训练模块概览</h2>
        </div>
        <div className="p-5 space-y-4">
          {[
            {
              name: '模仿学习',
              status: 'ready',
              desc: '从参考小说提取风格特征，生成训练样本（已验证：120 样本/8 场景）',
            },
            {
              name: 'SFT / LoRA 微调',
              status: 'ready',
              desc: '参数高效微调 Qwen2.5-1.5B-Instruct（LoRA r=16, 2 epochs, Loss=1.51）',
            },
            {
              name: 'GRPO 强化学习',
              status: 'pending',
              desc: 'Writer-Reader 对抗优化，组采样策略梯度下降（待实施）',
            },
            {
              name: 'Rubric 8 维评测',
              status: 'ready',
              desc: '程序化评分 + LLM 打分混合评估体系',
            },
            {
              name: 'TPO 推理时优化',
              status: 'experimental',
              desc: '生成多候选并选优（实验性）',
            },
          ].map((mod) => (
            <div key={mod.name} className="flex items-start gap-3 p-3 bg-gray-50 dark:bg-gray-900/50 rounded-lg">
              <span
                className={`mt-0.5 w-2.5 h-2.5 rounded-full flex-shrink-0 ${
                  mod.status === 'ready' ? 'bg-green-500' : mod.status === 'pending' ? 'bg-yellow-500' : 'bg-purple-500'
                }`}
              />
              <div>
                <div className="font-medium text-gray-900 dark:text-white">{mod.name}</div>
                <div className="text-sm text-gray-500 dark:text-gray-400">{mod.desc}</div>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* 最近训练记录 */}
      <div className="bg-white dark:bg-gray-800 rounded-lg shadow border border-gray-200 dark:border-gray-700">
        <div className="px-5 py-4 border-b border-gray-100 dark:border-gray-700 flex items-center justify-between">
          <h2 className="text-lg font-semibold text-gray-900 dark:text-white">历史训练</h2>
          <span className="text-xs text-gray-400">最近运行记录</span>
        </div>
        <div className="p-5">
          <div className="text-center py-8 text-gray-400">
            暂无训练记录。启动 Pipeline 后此处将显示运行历史。
          </div>
        </div>
      </div>
    </div>
  )
}
