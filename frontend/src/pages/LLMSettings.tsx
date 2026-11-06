import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { ArrowLeft, Save, Check, AlertCircle, Loader2, Clock, Terminal, Cpu, Trash2, FlaskConical } from 'lucide-react'
import { llmConfigApi } from '../services/api'

interface LLMConfig {
  provider: 'openai' | 'kimi' | 'deepseek' | 'yuanbao'
  apiKey: string
  baseUrl: string
  model: string
  responseTime?: number
  timeout?: number
}

interface TestResult {
  success: boolean
  message: string
  responseTime?: number
  response?: string
  error?: string
}

interface EffectiveConfig {
  provider?: string
  base_url?: string
  model?: string
  has_api_key?: boolean
  uses_user_key?: boolean
}

const defaultConfigs: Record<string, LLMConfig> = {
  openai: { provider: 'openai', apiKey: '', baseUrl: 'https://api.openai.com/v1', model: 'gpt-4-turbo-preview' },
  kimi: { provider: 'kimi', apiKey: '', baseUrl: 'http://localhost:8088', model: 'kimi' },
  deepseek: { provider: 'deepseek', apiKey: '', baseUrl: 'https://api.deepseek.com', model: 'deepseek-chat' },
  yuanbao: { provider: 'yuanbao', apiKey: '', baseUrl: 'http://localhost:8088', model: 'yuanbao' },
}

const PROVIDER_META = [
  { key: 'deepseek', label: 'DeepSeek', icon: '🔵', desc: '直连 API', color: 'bg-blue-500', placeholder: 'deepseek-chat' },
  { key: 'openai', label: 'OpenAI', icon: '🟢', desc: '官方 API', color: 'bg-emerald-500', placeholder: 'gpt-4-turbo-preview' },
  { key: 'kimi', label: 'Kimi', icon: '🔴', desc: '本地 Chat2Api', color: 'bg-red-500', placeholder: 'kimi' },
  { key: 'yuanbao', label: '腾讯元宝', icon: '🟣', desc: '本地 Chat2Api', color: 'bg-purple-500', placeholder: 'yuanbao' },
]

export function LLMSettings() {
  const navigate = useNavigate()
  const [config, setConfig] = useState<LLMConfig>(defaultConfigs.deepseek)
  const [savedProvider, setSavedProvider] = useState<string>('')
  const [effective, setEffective] = useState<EffectiveConfig>({})
  const [saved, setSaved] = useState(false)
  const [error, setError] = useState('')
  const [isTesting, setIsTesting] = useState(false)
  const [testResult, setTestResult] = useState<TestResult | null>(null)
  const [testLogs, setTestLogs] = useState<string[]>([])
  const [hasSavedKey, setHasSavedKey] = useState(false)
  const [clearing, setClearing] = useState(false)

  useEffect(() => {
    // BYOK：从后端加载当前用户的配置（Key 不回显明文）
    llmConfigApi.getCurrentConfig()
      .then((res: any) => {
        setHasSavedKey(!!res.uses_user_key)
        setEffective({
          provider: res.provider,
          base_url: res.base_url,
          model: res.model,
          has_api_key: res.has_api_key,
          uses_user_key: res.uses_user_key,
        })
        if (res.provider) {
          setSavedProvider(res.provider)
          setConfig(prev => ({
            ...prev,
            provider: res.provider as any,
            baseUrl: res.base_url || prev.baseUrl,
            model: res.model || prev.model,
          }))
        }
        if (res.timeout) {
          setConfig(prev => ({ ...prev, timeout: res.timeout }))
        }
      })
      .catch(() => {})
  }, [])

  const addLog = (message: string) => {
    setTestLogs(prev => [...prev, `[${new Date().toLocaleTimeString()}] ${message}`])
  }

  const handleSave = async () => {
    try {
      const result = await llmConfigApi.saveConfig({
        provider: config.provider,
        apiKey: config.apiKey || undefined,
        baseUrl: config.baseUrl,
        model: config.model,
        responseTime: config.responseTime,
        timeout: config.timeout,
      }) as any

      addLog(`✅ 后端配置已同步: ${config.provider} @ ${config.baseUrl}`)
      addLog(`超时时间设置为 ${result.timeout} 秒`)
      setSavedProvider(config.provider)
      setEffective(prev => ({ ...prev, provider: config.provider, base_url: config.baseUrl, model: config.model }))
      if (config.apiKey) {
        setHasSavedKey(true)
        setConfig(prev => ({ ...prev, apiKey: '' }))
      }
      setSaved(true)
      setError('')
      setTimeout(() => setSaved(false), 2000)
    } catch (err: any) {
      const detail = err?.response?.data?.detail || err.message
      setError(`保存到后端失败: ${detail}`)
      addLog(`❌ 保存失败: ${detail}`)
    }
  }

  const handleClearConfig = async () => {
    if (!window.confirm('清除你的 LLM 配置？之后将回落服务端默认配置。')) return
    setClearing(true)
    try {
      const res = await llmConfigApi.clearConfig()
      setHasSavedKey(false)
      setSavedProvider('')
      setConfig(prev => ({ ...prev, apiKey: '', baseUrl: defaultConfigs[prev.provider]?.baseUrl || '', model: defaultConfigs[prev.provider]?.model || '' }))
      setError('')
      addLog(`✅ ${res?.message || '已清除我的配置'}`)
    } catch (err: any) {
      setError(`清除失败: ${err?.response?.data?.detail || err.message}`)
    } finally {
      setClearing(false)
    }
  }

  const selectProvider = (provider: string) => {
    const base = defaultConfigs[provider]
    setConfig(provider === savedProvider ? { ...base, ...(effective.base_url ? { baseUrl: effective.base_url } : {}), ...(effective.model ? { model: effective.model } : {}) } : { ...base })
    setError('')
    setTestResult(null)
    setTestLogs([])
  }

  const testConnection = async () => {
    setIsTesting(true)
    setTestResult(null)
    setTestLogs([])

    try {
      addLog(`开始测试 ${config.provider} API...`)
      addLog(`Base URL: ${config.baseUrl || '使用默认值'}`)

      const result = await llmConfigApi.testConnection({
        provider: config.provider,
        apiKey: config.apiKey || undefined,
        baseUrl: config.baseUrl || undefined,
        model: config.model || undefined,
      }) as any

      if (result.success) {
        addLog(`✅ ${result.message}`)
        if (result.response_time_ms) addLog(`响应时间: ${result.response_time_ms}ms`)
        if (result.response) addLog(`AI 回复: ${result.response}`)
        if (result.response_time_ms) {
          setConfig(prev => ({ ...prev, responseTime: Math.round(result.response_time_ms / 1000) }))
        }
        setTestResult({
          success: true,
          message: result.message,
          responseTime: result.response_time_ms,
          response: result.response,
        })
      } else {
        addLog(`❌ ${result.message}`)
        if (result.error) addLog(`错误详情: ${result.error}`)
        setTestResult({ success: false, message: result.message, error: result.error })
      }
    } catch (err: any) {
      addLog(`测试失败: ${err.message}`)
      setTestResult({ success: false, message: '连接失败', error: err.message })
    } finally {
      setIsTesting(false)
    }
  }

  const effectiveBadge = effective.uses_user_key
    ? { text: '我的 Key', cls: 'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/40 dark:text-emerald-300' }
    : { text: '全局默认 Key', cls: 'bg-gray-100 text-gray-600 dark:bg-gray-700 dark:text-gray-300' }

  return (
    <div className="max-w-6xl mx-auto">
      <button
        onClick={() => navigate(-1)}
        className="flex items-center gap-2 text-gray-600 hover:text-gray-800 mb-6 transition-colors"
      >
        <ArrowLeft className="h-5 w-5" />
        返回
      </button>

      <div className="flex items-center justify-between mb-2">
        <h1 className="text-2xl font-bold text-gray-900 dark:text-white flex items-center gap-2">
          <Cpu className="h-6 w-6 text-primary-600" /> 我的 LLM 配置（BYOK）
        </h1>
        {hasSavedKey && (
          <span className="px-2.5 py-1 rounded-full bg-emerald-100 text-emerald-700 dark:bg-emerald-900/40 dark:text-emerald-300 text-xs font-medium">
            已配置个人 Key
          </span>
        )}
      </div>
      <p className="text-gray-500 dark:text-gray-400 mb-6">
        配置你自己的 API Key（Bring Your Own Key）：生成/评测的 token 费用由你自己的 Key 承担。
      </p>

      {error && (
        <div className="mb-6 p-4 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg flex items-center gap-3 text-red-600 dark:text-red-400">
          <AlertCircle className="h-5 w-5" />
          {error}
        </div>
      )}
      {saved && (
        <div className="mb-6 p-4 bg-green-50 dark:bg-green-900/20 border border-green-200 dark:border-green-800 rounded-lg flex items-center gap-3 text-green-600 dark:text-green-400">
          <Check className="h-5 w-5" />
          配置已保存
        </div>
      )}

      {/* 当前生效模型 */}
      <div className="mb-6 p-4 bg-white dark:bg-gray-800 rounded-xl shadow-sm border border-gray-200 dark:border-gray-700">
        <p className="text-xs text-gray-500 dark:text-gray-400 mb-2">当前生效模型（写作/评测等所有生成链路）</p>
        <div className="flex flex-wrap items-center gap-x-6 gap-y-2 text-sm">
          <span className="flex items-center gap-2 font-medium text-gray-900 dark:text-white">
            <span className="w-2.5 h-2.5 rounded-full bg-blue-500" />
            {effective.provider || '—'}
          </span>
          <span className="text-gray-700 dark:text-gray-300">{effective.model || '—'}</span>
          <span className="text-gray-500 dark:text-gray-400 truncate max-w-[320px]" title={effective.base_url}>
            {effective.base_url || '—'}
          </span>
          <span className={`px-2 py-0.5 rounded-full text-[11px] font-medium ${effectiveBadge.cls}`}>
            {effectiveBadge.text}
          </span>
          {!effective.has_api_key && (
            <span className="px-2 py-0.5 rounded-full bg-amber-100 text-amber-700 dark:bg-amber-900/40 dark:text-amber-300 text-[11px] font-medium">
              无可用 Key：生成会失败，请在下方配置
            </span>
          )}
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* 左侧：Provider 卡片 + 编辑表单 */}
        <div className="space-y-6">
          <div className="bg-white dark:bg-gray-800 rounded-xl shadow-sm border border-gray-200 dark:border-gray-700 p-5">
            <h2 className="text-sm font-semibold text-gray-700 dark:text-gray-300 mb-3">选择提供商</h2>
            <div className="grid grid-cols-2 gap-3">
              {PROVIDER_META.map((p) => {
                const active = config.provider === p.key
                const isSaved = savedProvider === p.key
                return (
                  <button
                    key={p.key}
                    onClick={() => selectProvider(p.key)}
                    className={`relative p-3 rounded-xl border-2 text-left transition-all ${
                      active
                        ? 'border-primary-600 bg-primary-50 dark:bg-primary-900/20 shadow-sm'
                        : 'border-gray-200 dark:border-gray-700 hover:border-primary-300 bg-white dark:bg-gray-800'
                    }`}
                  >
                    <div className="flex items-center gap-2">
                      <span className={`w-8 h-8 rounded-lg ${p.color} flex items-center justify-center text-white text-lg shrink-0`}>
                        {p.icon}
                      </span>
                      <div className="min-w-0">
                        <div className="font-medium text-gray-900 dark:text-white flex items-center gap-1.5">
                          {p.label}
                          {isSaved && <Check className="h-3.5 w-3.5 text-emerald-500" />}
                        </div>
                        <div className="text-xs text-gray-500 dark:text-gray-400">{p.desc}</div>
                      </div>
                    </div>
                    <div className="mt-2 text-xs text-gray-600 dark:text-gray-300 truncate">
                      {isSaved ? (effective.model || p.placeholder) : p.placeholder}
                    </div>
                    {isSaved && (
                      <span className="absolute top-2 right-2 px-1.5 py-0.5 rounded-full bg-emerald-100 text-emerald-700 dark:bg-emerald-900/40 dark:text-emerald-300 text-[10px] font-medium">
                        已配置
                      </span>
                    )}
                  </button>
                )
              })}
            </div>
          </div>

          <div className="bg-white dark:bg-gray-800 rounded-xl shadow-sm border border-gray-200 dark:border-gray-700 p-6">
            <h2 className="text-sm font-semibold text-gray-700 dark:text-gray-300 mb-4">
              编辑 {PROVIDER_META.find((p) => p.key === config.provider)?.label} 配置
            </h2>

            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                  API Key {hasSavedKey && config.provider === savedProvider && <span className="text-green-600 dark:text-green-400 text-xs">· 已配置</span>}
                </label>
                <input
                  type="password"
                  value={config.apiKey}
                  onChange={(e) => setConfig({ ...config, apiKey: e.target.value })}
                  placeholder={hasSavedKey && config.provider === savedProvider ? '已配置 Key（留空则不修改）' : 'sk-... / 你的 API Key'}
                  className="w-full px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white focus:ring-2 focus:ring-primary-500 focus:border-transparent"
                />
                <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
                  {hasSavedKey && config.provider === savedProvider
                    ? '已保存你的 Key（不显示明文）。输入新 Key 可更换；留空保存则保持不变。'
                    : '你的 API Key，加密存储于服务端，仅你的账号可用（BYOK）。'}
                </p>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">Base URL</label>
                <input
                  type="text"
                  value={config.baseUrl}
                  onChange={(e) => setConfig({ ...config, baseUrl: e.target.value })}
                  className="w-full px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white focus:ring-2 focus:ring-primary-500 focus:border-transparent"
                />
                <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
                  {config.provider === 'openai'
                    ? 'OpenAI API 地址，一般不需要修改'
                    : config.provider === 'deepseek'
                      ? 'DeepSeek API 地址，一般不需要修改'
                      : 'Chat2Api 服务地址，默认 http://localhost:8000'}
                </p>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">模型</label>
                <input
                  type="text"
                  value={config.model}
                  onChange={(e) => setConfig({ ...config, model: e.target.value })}
                  placeholder={defaultConfigs[config.provider]?.model}
                  className="w-full px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white focus:ring-2 focus:ring-primary-500 focus:border-transparent"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">请求超时时间（秒）</label>
                <input
                  type="number"
                  min="60"
                  max="3600"
                  step="30"
                  value={config.timeout || ''}
                  onChange={(e) => setConfig({ ...config, timeout: e.target.value ? parseInt(e.target.value) : undefined })}
                  placeholder="留空自动计算"
                  className="w-full px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white focus:ring-2 focus:ring-primary-500 focus:border-transparent"
                />
                <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
                  {config.responseTime
                    ? `根据测试时长(${config.responseTime}s)自动计算，或手动设置（60-3600秒）`
                    : '测试连接后将自动计算，或手动设置（60-3600秒）'}
                </p>
              </div>

              <div className="flex gap-3 pt-1">
                <button
                  onClick={testConnection}
                  disabled={isTesting}
                  className="flex-1 py-3 bg-gray-600 text-white rounded-lg hover:bg-gray-700 disabled:opacity-50 flex items-center justify-center gap-2 transition-colors"
                >
                  {isTesting ? <Loader2 className="h-5 w-5 animate-spin" /> : <FlaskConical className="h-5 w-5" />}
                  测试连接
                </button>
                <button
                  onClick={handleSave}
                  className="flex-1 py-3 bg-primary-600 text-white rounded-lg hover:bg-primary-700 flex items-center justify-center gap-2 transition-colors"
                >
                  <Save className="h-5 w-5" />
                  保存配置
                </button>
              </div>

              <div className="pt-1">
                <button
                  onClick={handleClearConfig}
                  disabled={clearing || !hasSavedKey}
                  className="text-sm text-red-600 dark:text-red-400 hover:text-red-700 dark:hover:text-red-300 disabled:opacity-40 disabled:cursor-not-allowed flex items-center gap-1.5"
                >
                  <Trash2 className="h-4 w-4" />
                  {clearing ? '清除中...' : '清除我的配置（移除我的 Key）'}
                </button>
              </div>
            </div>
          </div>
        </div>

        {/* 右侧：测试日志 */}
        <div className="bg-gray-900 text-gray-100 rounded-xl shadow-sm p-6 self-start">
          <div className="flex items-center gap-2 mb-4">
            <Terminal className="h-5 w-5" />
            <h2 className="text-lg font-semibold">测试日志</h2>
          </div>

          <div className="bg-gray-800 rounded-lg p-4 h-64 overflow-y-auto font-mono text-sm mb-4">
            {testLogs.length === 0 ? (
              <div className="text-gray-500 text-center py-8">点击"测试连接"开始测试</div>
            ) : (
              testLogs.map((log, index) => (
                <div key={index} className="mb-1">{log}</div>
              ))
            )}
            {isTesting && (
              <div className="flex items-center gap-2 text-yellow-400">
                <Loader2 className="h-4 w-4 animate-spin" />
                测试中...
              </div>
            )}
          </div>

          {testResult && (
            <div className={`p-4 rounded-lg ${testResult.success ? 'bg-green-900/30 border border-green-700' : 'bg-red-900/30 border border-red-700'}`}>
              <div className="flex items-center gap-2 mb-2">
                {testResult.success ? <Check className="h-5 w-5 text-green-400" /> : <AlertCircle className="h-5 w-5 text-red-400" />}
                <span className={`font-medium ${testResult.success ? 'text-green-400' : 'text-red-400'}`}>
                  {testResult.message}
                </span>
              </div>
              {testResult.responseTime && (
                <div className="flex items-center gap-2 text-sm text-gray-400 mb-2">
                  <Clock className="h-4 w-4" />
                  响应时间: {testResult.responseTime}ms
                </div>
              )}
              {testResult.response && (
                <div className="mt-2">
                  <div className="text-xs text-gray-500 mb-1">AI 回复:</div>
                  <div className="bg-gray-800 rounded p-2 text-sm text-gray-200">{testResult.response}</div>
                </div>
              )}
              {testResult.error && (
                <div className="mt-2 text-red-300 text-sm">错误: {testResult.error}</div>
              )}
            </div>
          )}

          <div className="mt-6 text-sm text-gray-400">
            <h3 className="font-medium text-gray-300 mb-2">使用说明:</h3>
            <ul className="space-y-1 list-disc list-inside">
              <li>你的 API Key 加密存储于服务端，仅你的账号使用</li>
              <li>生成/评测的 token 费用由你自己的 Key 承担（BYOK）</li>
              <li>未配置 Key 时回落服务端默认配置（管理员网关）</li>
              <li>每本小说可在小说详情「本书模型」单独覆盖 provider/模型</li>
              <li>测试成功后再保存配置</li>
            </ul>
          </div>
        </div>
      </div>
    </div>
  )
}
