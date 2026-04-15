import React from 'react'
import { useParams } from 'react-router-dom'

export const RLVisualization: React.FC = () => {
  const { batchId } = useParams<{ batchId: string }>()

  return (
    <div className="p-6 max-w-7xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold">训练可视化</h1>
          {batchId && <p className="text-sm text-gray-500 mt-1">批次 ID: {batchId}</p>}
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* 奖励曲线 */}
        <div className="bg-white dark:bg-gray-800 rounded-lg shadow border border-gray-200 dark:border-gray-700 p-5">
          <h3 className="font-semibold text-gray-900 dark:text-white mb-4">奖励曲线 (Reward Curve)</h3>
          <div className="h-64 flex items-center justify-center bg-gray-50 dark:bg-gray-900/50 rounded border border-dashed border-gray-300">
            <span className="text-gray-400">训练完成后显示奖励变化趋势</span>
          </div>
        </div>

        {/* 维度对比 */}
        <div className="bg-white dark:bg-gray-800 rounded-lg shadow border border-gray-200 dark:border-gray-700 p-5">
          <h3 className="font-semibold text-gray-900 dark:text-white mb-4">8 维评分对比</h3>
          <div className="space-y-2">
            {[
              'plot_consistency', 'style_matching', 'logic_rationality',
              'character_consistency', 'world_consistency', 'narrative_flow',
              'emotional_impact', 'hook_strength',
            ].map((dim) => (
              <div key={dim} className="flex items-center gap-2">
                <span className="text-xs text-gray-500 w-32 truncate">{dim}</span>
                <div className="flex-1 h-4 bg-gray-100 dark:bg-gray-700 rounded-full overflow-hidden">
                  <div
                    className="h-full bg-gradient-to-r from-blue-500 to-green-500 rounded-full"
                    style={{ width: `${Math.random() * 60 + 40}%` }}
                  />
                </div>
                <span className="text-xs text-gray-400 w-10 text-right">{(Math.random() * 0.5 + 0.5).toFixed(2)}</span>
              </div>
            ))}
          </div>
        </div>

        {/* Episode 详情 */}
        <div className="lg:col-span-2 bg-white dark:bg-gray-800 rounded-lg shadow border border-gray-200 dark:border-gray-700 p-5">
          <h3 className="font-semibold text-gray-900 dark:text-white mb-4">Episode 记录</h3>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-gray-200 dark:border-gray-700">
                  <th className="text-left py-2 px-3 text-gray-500">#</th>
                  <th className="text-left py-2 px-3 text-gray-500">章节</th>
                  <th className="text-left py-2 px-3 text-gray-500">轮次</th>
                  <th className="text-right py-2 px-3 text-gray-500">奖励</th>
                  <th className="text-right py-2 px-3 text-gray-500">Reader 分数</th>
                </tr>
              </thead>
              <tbody>
                <tr>
                  <td colSpan={5} className="py-8 text-center text-gray-400">
                    暂无 Episode 数据
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  )
}
