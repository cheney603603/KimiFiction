import React from 'react'

export const AgentWorkflow: React.FC = () => {
  return (
    <div className="p-6 max-w-7xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold">多智能体协作工作流</h1>
      </div>

      {/* 工作流图 */}
      <div className="bg-white dark:bg-gray-800 rounded-lg shadow border border-gray-200 dark:border-gray-700 p-6 mb-6">
        <h2 className="font-semibold text-gray-900 dark:text-white mb-4">ReAct 状态图</h2>

        {/* 节点可视化 */}
        <div className="flex flex-wrap gap-3 justify-center py-8">
          {[
            { name: '需求分析', phase: 'demand_analysis', status: 'pending' },
            { name: '世界观构建', phase: 'world_building', status: 'pending' },
            { name: '角色设计', phase: 'character_design', status: 'pending' },
            { name: '冲突设计', phase: 'plot_design', status: 'pending' },
            { name: '大纲生成', phase: 'outline_draft', status: 'pending' },
            { name: '细纲撰写', phase: 'outline_detail', status: 'pending' },
            { name: '章节写作', phase: 'chapter_writing', status: 'pending' },
            { name: '章节审核', phase: 'chapter_review', status: 'pending' },
          ].map((node, idx) => (
            <React.Fragment key={node.phase}>
              <div
                className={`
                  px-4 py-3 rounded-lg border text-sm min-w-[120px] text-center
                  ${node.status === 'running'
                    ? 'border-blue-500 bg-blue-50 text-blue-700 animate-pulse'
                    : node.status === 'success'
                      ? 'border-green-500 bg-green-50 text-green-700'
                      : node.status === 'failed'
                        ? 'border-red-500 bg-red-50 text-red-700'
                        : 'border-gray-300 bg-white text-gray-600'
                  }
                `}
              >
                <div className="font-medium">{node.name}</div>
                <div className="text-xs opacity-60 mt-0.5">{node.phase}</div>
              </div>
              {idx < 7 && (
                <svg className="w-5 h-5 self-center text-gray-300 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                </svg>
              )}
            </React.Fragment>
          ))}
        </div>
      </div>

      {/* Agent 配置信息 */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <div className="bg-white dark:bg-gray-800 rounded-lg shadow border border-gray-200 dark:border-gray-700 p-5">
          <h3 className="font-semibold text-gray-900 dark:text-white mb-4">Agent ReAct 步数配置</h3>
          <div className="space-y-2 text-sm">
            {[
              ['GenreAnalyzerAgent', 2],
              ['UnifiedWorldBuilderAgent', 5],
              ['UnifiedCharacterDesignerAgent', 4],
              ['UnifiedPlotDesignerAgent', 5],
              ['UnifiedOutlineGeneratorAgent', 5],
              ['ChapterWriterAgent', 3],
              ['ReaderAgent / ReviewerAgent', 3],
            ].map(([name, steps]) => (
              <div key={String(name)} className="flex justify-between py-1.5 border-b border-gray-100 dark:border-gray-700 last:border-0">
                <span className="text-gray-600 dark:text-gray-400">{name}</span>
                <span className="font-mono text-blue-600">{steps} 步</span>
              </div>
            ))}
          </div>
        </div>

        <div className="bg-white dark:bg-gray-800 rounded-lg shadow border border-gray-200 dark:border-gray-700 p-5">
          <h3 className="font-semibold text-gray-900 dark:text-white mb-4">LangGraph 集成状态</h3>
          <div className="space-y-3">
            <div className="flex items-center gap-2">
              <span className={`w-2.5 h-2.5 rounded-full ${'bg-yellow-500'}`} />
              <span className="text-sm text-gray-600 dark:text-gray-400">
                LangGraph：检测中...
              </span>
            </div>
            <div className="text-xs text-gray-400 mt-2">
              工作流图支持状态持久化和断点续写。当前使用简化实现，
              安装 langgraph 后自动启用完整功能。
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
