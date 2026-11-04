import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { ArrowLeft, Save, Check, AlertCircle, Play, Loader2, Clock, Terminal } from 'lucide-react'
import { llmConfigApi } from '../services/api'

interface LLMConfig {
  provider: 'openai' | 'kimi' | 'deepseek' | 'yuanbao'
  apiKey: string
  baseUrl: string
  model: string
  responseTime?: number  // 测试返回时长（秒）
  timeout?: number  // 手动设置的超时时间（秒）
}

interface TestResult {
  success: boolean
  message: string
  responseTime?: number
  response?: string
  error?: string
}

const defaultConfigs: Record<string, LLMConfig> = {
  openai: {
    provider: 'openai',
    apiKey: '',
    baseUrl: 'https://api.openai.com/v1',
    model: 'gpt-4-turbo-preview',
  },
  kimi: {
    provider: 'kimi',
    apiKey: '',
    baseUrl: 'http://localhost:8088',
    model: 'kimi',
  },
  deepseek: {
    provider: 'deepseek',
    apiKey: '',
    baseUrl: 'https://api.deepseek.com',
    model: 'deepseek-chat',
  },
  yuanbao: {
    provider: 'yuanbao',
    apiKey: '',
    baseUrl: 'http://localhost:8088',
    model: 'yuanbao',
  },
}

export function LLMSettings() {
  const navigate = useNavigate()
  const [config, setConfig] = useState<LLMConfig>(defaultConfigs.deepseek)
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
        if (res.provider) {
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
      .catch(() => {
        // 后端不可达时使用默认配置
      })
  }, [])

  const addLog = (message: string) => {
    setTestLogs(prev => [...prev, `[${new Date().toLocaleTimeString()}] ${message}`])
  }

  const handleSave = async () => {
    // 保存到后端（BYOK：Key 加密存储，不回显明文）
    try {
      const result = await llmConfigApi.saveConfig({
        provider: config.provider,
        // 未输入新 Key 时不覆盖已有 Key（后端回落已保存的 Key / 全局配置）
        apiKey: config.apiKey || undefined,
        baseUrl: config.baseUrl,
        model: config.model,
        responseTime: config.responseTime,
        timeout: config.timeout,
      }) as any

      addLog(`✅ 后端配置已同步: ${config.provider} @ ${config.baseUrl}`)
      addLog(`超时时间设置为 ${result.timeout} 秒`)
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
      setConfig(prev => ({ ...prev, apiKey: '', baseUrl: defaultConfigs[prev.provider]?.baseUrl || '', model: defaultConfigs[prev.provider]?.model || '' }))
      setError('')
      addLog(`✅ ${res?.message || '已清除我的配置'}`)
    } catch (err: any) {
      setError(`清除失败: ${err?.response?.data?.detail || err.message}`)
    } finally {
      setClearing(false)
    }
  }

  const handleProviderChange = (provider: string) => {
    setConfig(defaultConfigs[provider])
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
      
      // 通过后端代理测试连接
      addLog('通过后端代理发送测试请求...')
      
      const result = await llmConfigApi.testConnection({
        provider: config.provider,
        apiKey: config.apiKey || undefined,
        baseUrl: config.baseUrl || undefined,
        model: config.model || undefined,
      }) as any
      
      if (result.success) {
        addLog(`✅ ${result.message}`)
        if (result.response_time_ms) {
          addLog(`响应时间: ${result.response_time_ms}ms`)
        }
        if (result.response) {
          addLog(`AI 回复: ${result.response}`)
        }
        
        // 保存测试返回时长到配置（转换为秒）
        if (result.response_time_ms) {
          const responseTimeSec = Math.round(result.response_time_ms / 1000)
          setConfig(prev => ({ ...prev, responseTime: responseTimeSec }))
        }
        
        setTestResult({
          success: true,
          message: result.message,
          responseTime: result.response_time_ms,
          response: result.response,
        })
      } else {
        addLog(`❌ ${result.message}`)
        if (result.error) {
          addLog(`错误详情: ${result.error}`)
        }
        
        setTestResult({
          success: false,
          message: result.message,
          error: result.error,
        })
      }
    } catch (err: any) {
      addLog(`测试失败: ${err.message}`)
      
      setTestResult({
        success: false,
        message: '连接失败',
        error: err.message,
      })
    } finally {
      setIsTesting(false)
    }
  }

  return (
    <div className="max-w-4xl mx-auto">
      {/* 返回按钮 */}
      <button
        onClick={() => navigate(-1)}
        className="flex items-center gap-2 text-gray-600 hover:text-gray-800 mb-6 transition-colors"
      >
        <ArrowLeft className="h-5 w-5" />
        返回
      </button>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* 左侧：配置表单 */}
        <div className="bg-white dark:bg-gray-800 rounded-xl shadow-sm border border-gray-200 dark:border-gray-700 p-8">
          <h1 className="text-2xl font-bold text-gray-900 dark:text-white mb-2">
            我的 LLM 配置（BYOK）
          </h1>
          <p className="text-gray-500 dark:text-gray-400 mb-8">
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

          <div className="space-y-6">
            {/* 提供商选择 */}
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                选择提供商
              </label>
              <div className="grid grid-cols-2 gap-4">
                {[
                  { key: 'openai', label: 'OpenAI', desc: '官方 API' },
                  { key: 'kimi', label: 'Kimi', desc: '本地 Chat2Api' },
                  { key: 'deepseek', label: 'DeepSeek', desc: '本地 Chat2Api' },
                  { key: 'yuanbao', label: '腾讯元宝', desc: '本地 Chat2Api' },
                ].map((item) => (
                  <button
                    key={item.key}
                    onClick={() => handleProviderChange(item.key)}
                    className={`p-4 rounded-lg border-2 text-left transition-colors ${
                      config.provider === item.key
                        ? 'border-primary-600 bg-primary-50 dark:bg-primary-900/20'
                        : 'border-gray-200 dark:border-gray-600 hover:border-primary-300'
                    }`}
                  >
                    <div className="font-medium text-gray-900 dark:text-white">
                      {item.label}
                    </div>
                    <div className="text-sm text-gray-500 dark:text-gray-400">
                      {item.desc}
                    </div>
                  </button>
                ))}
              </div>
            </div>

            {/* API Key（BYOK：加密存服务端，不回显明文） */}
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                API Key {hasSavedKey && <span className="text-green-600 dark:text-green-400 text-xs">· 已配置</span>}
              </label>
              <input
                type="password"
                value={config.apiKey}
                onChange={(e) => setConfig({ ...config, apiKey: e.target.value })}
                placeholder={hasSavedKey ? '已配置 Key（留空则不修改）' : 'sk-... / 你的 API Key'}
                className="w-full px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white focus:ring-2 focus:ring-primary-500 focus:border-transparent"
              />
              <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
                {hasSavedKey
                  ? '已保存你的 Key（不显示明文）。输入新 Key 可更换；留空保存则保持不变。'
                  : '你的 API Key，加密存储于服务端，仅你的账号可用（BYOK）。'}
              </p>
            </div>

            {/* Base URL */}
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                Base URL
              </label>
              <input
                type="text"
                value={config.baseUrl}
                onChange={(e) => setConfig({ ...config, baseUrl: e.target.value })}
                className="w-full px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white focus:ring-2 focus:ring-primary-500 focus:border-transparent"
              />
              <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
                {config.provider === 'openai' 
                  ? 'OpenAI API 地址，一般不需要修改'
                  : 'Chat2Api 服务地址，默认 http://localhost:8000'}
              </p>
            </div>

            {/* 模型选择 */}
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                模型
              </label>
              {config.provider === 'openai' ? (
                <select
                  value={config.model}
                  onChange={(e) => setConfig({ ...config, model: e.target.value })}
                  className="w-full px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white focus:ring-2 focus:ring-primary-500 focus:border-transparent"
                >
                  <option value="gpt-4-turbo-preview">GPT-4 Turbo</option>
                  <option value="gpt-4">GPT-4</option>
                  <option value="gpt-3.5-turbo">GPT-3.5 Turbo</option>
                </select>
              ) : (
                <input
                  type="text"
                  value={config.model}
                  disabled
                  className="w-full px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-gray-100 dark:bg-gray-600 text-gray-500 dark:text-gray-400"
                />
              )}
            </div>

            {/* 超时时间设置 */}
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                请求超时时间（秒）
              </label>
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

            {/* 操作按钮 */}
            <div className="flex gap-3">
              <button
                onClick={testConnection}
                disabled={isTesting}
                className="flex-1 py-3 bg-gray-600 text-white rounded-lg hover:bg-gray-700 disabled:opacity-50 flex items-center justify-center gap-2 transition-colors"
              >
                {isTesting ? (
                  <Loader2 className="h-5 w-5 animate-spin" />
                ) : (
                  <Play className="h-5 w-5" />
                )}
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

            {/* 清除我的配置 */}
            <div className="pt-2">
              <button
                onClick={handleClearConfig}
                disabled={clearing || !hasSavedKey}
                className="text-sm text-red-600 dark:text-red-400 hover:text-red-700 dark:hover:text-red-300 disabled:opacity-40 disabled:cursor-not-allowed"
              >
                {clearing ? '清除中...' : '清除我的配置（移除我的 Key）'}
              </button>
            </div>
          </div>
        </div>

        {/* 右侧：测试结果 */}
        <div className="bg-gray-900 text-gray-100 rounded-xl shadow-sm p-6">
          <div className="flex items-center gap-2 mb-4">
            <Terminal className="h-5 w-5" />
            <h2 className="text-lg font-semibold">测试日志</h2>
          </div>

          {/* 测试日志 */}
          <div className="bg-gray-800 rounded-lg p-4 h-64 overflow-y-auto font-mono text-sm mb-4">
            {testLogs.length === 0 ? (
              <div className="text-gray-500 text-center py-8">
                点击"测试连接"开始测试
              </div>
            ) : (
              testLogs.map((log, index) => (
                <div key={index} className="mb-1">
                  {log}
                </div>
              ))
            )}
            {isTesting && (
              <div className="flex items-center gap-2 text-yellow-400">
                <Loader2 className="h-4 w-4 animate-spin" />
                测试中...
              </div>
            )}
          </div>

          {/* 测试结果 */}
          {testResult && (
            <div className={`p-4 rounded-lg ${
              testResult.success 
                ? 'bg-green-900/30 border border-green-700' 
                : 'bg-red-900/30 border border-red-700'
            }`}>
              <div className="flex items-center gap-2 mb-2">
                {testResult.success ? (
                  <Check className="h-5 w-5 text-green-400" />
                ) : (
                  <AlertCircle className="h-5 w-5 text-red-400" />
                )}
                <span className={`font-medium ${
                  testResult.success ? 'text-green-400' : 'text-red-400'
                }`}>
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
                  <div className="bg-gray-800 rounded p-2 text-sm text-gray-200">
                    {testResult.response}
                  </div>
                </div>
              )}
              
              {testResult.error && (
                <div className="mt-2 text-red-300 text-sm">
                  错误: {testResult.error}
                </div>
              )}
            </div>
          )}

          {/* 使用说明 */}
          <div className="mt-6 text-sm text-gray-400">
            <h3 className="font-medium text-gray-300 mb-2">使用说明:</h3>
            <ul className="space-y-1 list-disc list-inside">
              <li>你的 API Key 加密存储于服务端，仅你的账号使用，其他人不可见</li>
              <li>生成/评测的 token 费用由你自己的 Key 承担（BYOK）</li>
              <li>未配置 Key 时回落服务端默认配置（管理员网关）</li>
              <li>测试成功后再保存配置</li>
            </ul>
          </div>
        </div>
      </div>
    </div>
  )
}
