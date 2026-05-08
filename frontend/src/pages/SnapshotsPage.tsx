import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { 
  Clock, RotateCcw, GitCommit, MessageSquare, 
  Database, AlertTriangle,
  Eye, Trash2, X
} from 'lucide-react';
const API_BASE = '/api/v1';

interface Snapshot {
  snapshot_id: string;
  type: string;
  created_at: string;
  description: string;
  has_llm_call: boolean;
}

interface LLMCallInfo {
  call_id: string;
  timestamp: string;
  agent_name: string;
  model: string;
  input_preview: string;
  output_preview: string;
  tokens_used?: number;
  duration_ms?: number;
  error?: string;
}

interface SnapshotDetail {
  snapshot_id: string;
  novel_id: number;
  type: string;
  created_at: string;
  description: string;
  llm_call?: LLMCallInfo;
  database_state?: {
    chapter_count: number;
    entity_count: number;
    latest_chapter_number?: number;
  };
  git_commit?: string;
  git_dirty_files: string[];
}

export default function SnapshotsPage() {
  const { novelId } = useParams<{ novelId: string }>();
  const navigate = useNavigate();
  const [novelTitle, setNovelTitle] = useState<string>('');
  const [snapshots, setSnapshots] = useState<Snapshot[]>([]);
  const [selectedSnapshot, setSelectedSnapshot] = useState<SnapshotDetail | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showRollbackConfirm, setShowRollbackConfirm] = useState(false);
  const [showFullLLMCall, setShowFullLLMCall] = useState(false);
  const [fullLLMCall, setFullLLMCall] = useState<any>(null);
  const [filterType, setFilterType] = useState<string>('');

  useEffect(() => {
    if (novelId) {
      loadNovelInfo();
      loadSnapshots();
    }
  }, [novelId, filterType]);

  const loadNovelInfo = async () => {
    try {
      const res = await fetch(`${API_BASE}/novels/${novelId}`);
      if (res.ok) {
        const data = await res.json();
        setNovelTitle(data.title || '');
      }
    } catch (e) {
      console.error('加载小说信息失败:', e);
    }
  };

  const loadSnapshots = async () => {
    setLoading(true);
    try {
      const url = `${API_BASE}/snapshots/novel/${novelId}${filterType ? `?snapshot_type=${filterType}` : ''}`;
      const response = await fetch(url);
      if (!response.ok) throw new Error('加载失败');
      const data = await response.json();
      setSnapshots(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : '未知错误');
    } finally {
      setLoading(false);
    }
  };

  const viewSnapshotDetail = async (snapshotId: string) => {
    try {
      const response = await fetch(`${API_BASE}/snapshots/novel/${novelId}/${snapshotId}`);
      if (!response.ok) throw new Error('加载详情失败');
      const data = await response.json();
      setSelectedSnapshot(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : '未知错误');
    }
  };

  const viewFullLLMCall = async (snapshotId: string) => {
    try {
      const response = await fetch(`${API_BASE}/snapshots/novel/${novelId}/${snapshotId}/llm-call/full`);
      if (!response.ok) throw new Error('加载失败');
      const data = await response.json();
      setFullLLMCall(data);
      setShowFullLLMCall(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : '未知错误');
    }
  };

  const rollback = async () => {
    if (!selectedSnapshot) return;
    try {
      const response = await fetch(`${API_BASE}/snapshots/novel/${novelId}/rollback`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ snapshot_id: selectedSnapshot.snapshot_id, confirm: true })
      });
      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || '回滚失败');
      }
      const result = await response.json();
      alert(`回滚成功！\n${result.message}`);
      setShowRollbackConfirm(false);
      setSelectedSnapshot(null);
      loadSnapshots();
    } catch (err) {
      setError(err instanceof Error ? err.message : '回滚失败');
    }
  };

  const deleteSnapshot = async (snapshotId: string) => {
    if (!confirm('确定要删除这个快照吗？')) return;
    try {
      const response = await fetch(`${API_BASE}/snapshots/novel/${novelId}/${snapshotId}`, { method: 'DELETE' });
      if (!response.ok) throw new Error('删除失败');
      loadSnapshots();
      if (selectedSnapshot?.snapshot_id === snapshotId) setSelectedSnapshot(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : '删除失败');
    }
  };

  const createManualSnapshot = async () => {
    const description = prompt('请输入快照描述：');
    if (!description) return;
    try {
      const response = await fetch(
        `${API_BASE}/snapshots/novel/${novelId}/manual?description=${encodeURIComponent(description)}`,
        { method: 'POST' }
      );
      if (!response.ok) throw new Error('创建失败');
      loadSnapshots();
      alert('手动快照创建成功！');
    } catch (err) {
      setError(err instanceof Error ? err.message : '创建失败');
    }
  };

  const formatTime = (isoString: string) => new Date(isoString).toLocaleString('zh-CN');

  const getTypeLabel = (type: string) => ({
    'llm_call': 'LLM调用', 'chapter_start': '章节开始',
    'chapter_end': '章节完成', 'manual': '手动快照', 'auto': '自动快照'
  })[type] || type;

  const getTypeColor = (type: string) => ({
    'llm_call': 'bg-blue-100 text-blue-800', 'chapter_start': 'bg-green-100 text-green-800',
    'chapter_end': 'bg-purple-100 text-purple-800', 'manual': 'bg-orange-100 text-orange-800',
    'auto': 'bg-gray-100 text-gray-800'
  })[type] || 'bg-gray-100 text-gray-800';

  return (
    <div className="min-h-screen bg-gray-50 p-6">
      <div className="max-w-7xl mx-auto">
        <div className="mb-6">
          <div className="flex items-center gap-2 text-sm text-gray-500 mb-2">
            <span className="cursor-pointer hover:text-blue-600" onClick={() => navigate(`/novels/${novelId}`)}>
              {novelTitle || '小说'}
            </span>
            <span>/</span>
            <span>快照管理</span>
          </div>
          <div className="flex justify-between items-center">
            <h1 className="text-2xl font-bold text-gray-900">系统快照与回滚</h1>
            <button onClick={createManualSnapshot} className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700">
              <GitCommit className="w-4 h-4" /> 创建手动快照
            </button>
          </div>
          <p className="text-gray-600 mt-2">每次LLM调用都会自动创建快照，您可以查看历史调用、对比差异，或回滚到任意状态。</p>
        </div>

        {error && <div className="mb-4 p-4 bg-red-50 border border-red-200 rounded-lg text-red-700">{error}</div>}

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <div className="lg:col-span-1">
            <div className="bg-white rounded-lg shadow">
              <div className="p-4 border-b">
                <div className="flex items-center justify-between mb-3">
                  <h2 className="font-semibold text-gray-900">快照列表</h2>
                  <select value={filterType} onChange={(e) => setFilterType(e.target.value)} className="text-sm border rounded px-2 py-1">
                    <option value="">全部类型</option>
                    <option value="llm_call">LLM调用</option>
                    <option value="chapter_start">章节开始</option>
                    <option value="chapter_end">章节完成</option>
                    <option value="manual">手动快照</option>
                  </select>
                </div>
                <div className="text-sm text-gray-500">共 {snapshots.length} 个快照</div>
              </div>
              
              <div className="max-h-[600px] overflow-y-auto">
                {loading ? <div className="p-8 text-center text-gray-500">加载中...</div> :
                 snapshots.length === 0 ? <div className="p-8 text-center text-gray-500">暂无快照</div> :
                  <div className="divide-y">
                    {snapshots.map((snapshot) => (
                      <div key={snapshot.snapshot_id} onClick={() => viewSnapshotDetail(snapshot.snapshot_id)}
                           className={`p-4 cursor-pointer hover:bg-gray-50 transition-colors ${selectedSnapshot?.snapshot_id === snapshot.snapshot_id ? 'bg-blue-50 border-l-4 border-blue-500' : ''}`}>
                        <div className="flex items-start justify-between">
                          <div className="flex-1 min-w-0">
                            <div className="flex items-center gap-2 mb-1">
                              <span className={`text-xs px-2 py-0.5 rounded ${getTypeColor(snapshot.type)}`}>{getTypeLabel(snapshot.type)}</span>
                              {snapshot.has_llm_call && <MessageSquare className="w-3 h-3 text-blue-500" />}
                            </div>
                            <p className="text-sm text-gray-900 truncate">{snapshot.description}</p>
                            <p className="text-xs text-gray-500 mt-1"><Clock className="w-3 h-3 inline mr-1" />{formatTime(snapshot.created_at)}</p>
                          </div>
                          <button onClick={(e) => { e.stopPropagation(); deleteSnapshot(snapshot.snapshot_id); }} className="p-1 text-gray-400 hover:text-red-500">
                            <Trash2 className="w-4 h-4" />
                          </button>
                        </div>
                      </div>
                    ))}
                  </div>
                }
              </div>
            </div>
          </div>

          <div className="lg:col-span-2">
            {selectedSnapshot ? (
              <div className="bg-white rounded-lg shadow">
                <div className="p-6 border-b">
                  <div className="flex items-start justify-between">
                    <div>
                      <div className="flex items-center gap-3 mb-2">
                        <span className={`text-sm px-3 py-1 rounded ${getTypeColor(selectedSnapshot.type)}`}>{getTypeLabel(selectedSnapshot.type)}</span>
                        <span className="text-sm text-gray-500 font-mono">{selectedSnapshot.snapshot_id}</span>
                      </div>
                      <h3 className="text-lg font-semibold text-gray-900">{selectedSnapshot.description}</h3>
                      <p className="text-sm text-gray-500 mt-1"><Clock className="w-4 h-4 inline mr-1" />{formatTime(selectedSnapshot.created_at)}</p>
                    </div>
                    <button onClick={() => setShowRollbackConfirm(true)} className="flex items-center gap-2 px-4 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700">
                      <RotateCcw className="w-4 h-4" /> 回滚到此状态
                    </button>
                  </div>
                </div>

                {selectedSnapshot.database_state && (
                  <div className="p-6 border-b">
                    <h4 className="font-semibold text-gray-900 mb-4 flex items-center gap-2"><Database className="w-5 h-5" /> 数据库状态</h4>
                    <div className="grid grid-cols-3 gap-4">
                      <div className="bg-gray-50 p-4 rounded-lg">
                        <div className="text-2xl font-bold text-blue-600">{selectedSnapshot.database_state.chapter_count}</div>
                        <div className="text-sm text-gray-600">章节数</div>
                      </div>
                      <div className="bg-gray-50 p-4 rounded-lg">
                        <div className="text-2xl font-bold text-green-600">{selectedSnapshot.database_state.entity_count}</div>
                        <div className="text-sm text-gray-600">实体数</div>
                      </div>
                      <div className="bg-gray-50 p-4 rounded-lg">
                        <div className="text-2xl font-bold text-purple-600">{selectedSnapshot.database_state.latest_chapter_number || '-'}</div>
                        <div className="text-sm text-gray-600">最新章节</div>
                      </div>
                    </div>
                  </div>
                )}

                {selectedSnapshot.llm_call && (
                  <div className="p-6 border-b">
                    <h4 className="font-semibold text-gray-900 mb-4 flex items-center gap-2"><MessageSquare className="w-5 h-5" /> LLM调用详情</h4>
                    <div className="space-y-4">
                      <div className="grid grid-cols-4 gap-4 text-sm">
                        <div><span className="text-gray-500">Agent:</span><span className="ml-2 font-medium">{selectedSnapshot.llm_call.agent_name}</span></div>
                        <div><span className="text-gray-500">模型:</span><span className="ml-2 font-medium">{selectedSnapshot.llm_call.model}</span></div>
                        <div><span className="text-gray-500">耗时:</span><span className="ml-2 font-medium">{selectedSnapshot.llm_call.duration_ms}ms</span></div>
                        <div><span className="text-gray-500">Token:</span><span className="ml-2 font-medium">{selectedSnapshot.llm_call.tokens_used || '-'}</span></div>
                      </div>

                      <div className="bg-gray-50 rounded-lg p-4">
                        <div className="flex items-center justify-between mb-2">
                          <span className="text-sm font-medium text-gray-700">输入预览</span>
                          <button onClick={() => viewFullLLMCall(selectedSnapshot.snapshot_id)} className="text-sm text-blue-600 hover:text-blue-800 flex items-center gap-1">
                            <Eye className="w-4 h-4" /> 查看完整输入输出
                          </button>
                        </div>
                        <pre className="text-sm text-gray-600 whitespace-pre-wrap max-h-32 overflow-y-auto">{selectedSnapshot.llm_call.input_preview}</pre>
                      </div>

                      <div className="bg-gray-50 rounded-lg p-4">
                        <span className="text-sm font-medium text-gray-700">输出预览</span>
                        <pre className="text-sm text-gray-600 whitespace-pre-wrap max-h-32 overflow-y-auto mt-2">{selectedSnapshot.llm_call.output_preview}</pre>
                      </div>

                      {selectedSnapshot.llm_call.error && (
                        <div className="bg-red-50 border border-red-200 rounded-lg p-4">
                          <span className="text-sm font-medium text-red-700">错误:</span>
                          <p className="text-sm text-red-600 mt-1">{selectedSnapshot.llm_call.error}</p>
                        </div>
                      )}
                    </div>
                  </div>
                )}

                {selectedSnapshot.git_commit && (
                  <div className="p-6">
                    <h4 className="font-semibold text-gray-900 mb-2 flex items-center gap-2"><GitCommit className="w-5 h-5" /> Git状态</h4>
                    <div className="text-sm text-gray-600">
                      <p>Commit: <code className="bg-gray-100 px-2 py-1 rounded">{selectedSnapshot.git_commit.slice(0, 8)}</code></p>
                      {selectedSnapshot.git_dirty_files.length > 0 && <p className="mt-1 text-orange-600">有 {selectedSnapshot.git_dirty_files.length} 个未提交文件</p>}
                    </div>
                  </div>
                )}
              </div>
            ) : (
              <div className="bg-white rounded-lg shadow p-12 text-center text-gray-500">
                <Clock className="w-16 h-16 mx-auto mb-4 text-gray-300" />
                <p>选择一个快照查看详情</p>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* 回滚确认弹窗 */}
      {showRollbackConfirm && selectedSnapshot && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg p-6 max-w-md w-full mx-4">
            <div className="flex items-center gap-3 mb-4">
              <AlertTriangle className="w-8 h-8 text-red-500" />
              <h3 className="text-lg font-semibold text-gray-900">确认回滚？</h3>
            </div>
            <p className="text-gray-600 mb-4">
              您即将回滚到 <strong>{formatTime(selectedSnapshot.created_at)}</strong> 的状态。
            </p>
            <div className="bg-red-50 border border-red-200 rounded-lg p-4 mb-6">
              <p className="text-sm text-red-700">
                <strong>警告：</strong>此操作将删除该时间点之后创建的所有章节和数据，且无法撤销！
              </p>
            </div>
            <div className="flex gap-3">
              <button onClick={() => setShowRollbackConfirm(false)} className="flex-1 px-4 py-2 border border-gray-300 rounded-lg hover:bg-gray-50">
                取消
              </button>
              <button onClick={rollback} className="flex-1 px-4 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700">
                确认回滚
              </button>
            </div>
          </div>
        </div>
      )}

      {/* 完整LLM调用弹窗 */}
      {showFullLLMCall && fullLLMCall && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg max-w-4xl w-full mx-4 max-h-[90vh] flex flex-col">
            <div className="flex items-center justify-between p-4 border-b">
              <h3 className="text-lg font-semibold text-gray-900">完整LLM调用记录</h3>
              <button onClick={() => setShowFullLLMCall(false)} className="p-1 hover:bg-gray-100 rounded">
                <X className="w-5 h-5" />
              </button>
            </div>
            <div className="flex-1 overflow-y-auto p-4 space-y-4">
              <div className="grid grid-cols-2 gap-4 text-sm">
                <div><span className="text-gray-500">Call ID:</span> <code className="bg-gray-100 px-2 py-1 rounded">{fullLLMCall.call_id}</code></div>
                <div><span className="text-gray-500">Agent:</span> {fullLLMCall.agent_name}</div>
                <div><span className="text-gray-500">模型:</span> {fullLLMCall.model}</div>
                <div><span className="text-gray-500">耗时:</span> {fullLLMCall.duration_ms}ms</div>
              </div>

              <div>
                <h4 className="font-medium text-gray-900 mb-2">输入消息</h4>
                <div className="space-y-2">
                  {fullLLMCall.input_messages?.map((msg: any, idx: number) => (
                    <div key={idx} className={`p-3 rounded-lg ${msg.role === 'system' ? 'bg-purple-50' : msg.role === 'user' ? 'bg-blue-50' : 'bg-gray-50'}`}>
                      <div className="text-xs font-medium text-gray-500 mb-1">{msg.role}</div>
                      <pre className="text-sm whitespace-pre-wrap">{msg.content}</pre>
                    </div>
                  ))}
                </div>
              </div>

              <div>
                <h4 className="font-medium text-gray-900 mb-2">输出内容</h4>
                <div className="bg-green-50 p-3 rounded-lg">
                  <pre className="text-sm whitespace-pre-wrap">{fullLLMCall.output_content}</pre>
                </div>
              </div>

              {fullLLMCall.error && (
                <div className="bg-red-50 border border-red-200 rounded-lg p-4">
                  <h4 className="font-medium text-red-700 mb-1">错误</h4>
                  <p className="text-sm text-red-600">{fullLLMCall.error}</p>
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
