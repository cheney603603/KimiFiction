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
  const [config, setConfig] = useState<LLMConfig>(defaultConfigs.openai)
  const [saved, setSaved] = useState(false)
  const [error, setError] = useState('')
  const [isTesting, setIsTesting] = useState(false)
  const [testResult, setTestResult] = useState<TestResult | null>(null)
  const [testLogs, setTestLogs] = useState<string[]>([])

  useEffect(() => {
    // 从 localStorage 加载配置
    const saved = localStorage.getItem('llm_config')
    if (saved) {
      try {
        setConfig(JSON.parse(saved))
      } catch {
        // 解析失败，使用默认
      }
    } else {
      // 首次加载时，自动保存默认配置
      localStorage.setItem('llm_config', JSON.stringify(defaultConfigs.kimi))
    }
  }, [])

  const addLog = (message: string) => {
    setTestLogs(prev => [...prev, `[${new Date().toLocaleTimeString()}] ${message}`])
  }

  const handleSave = async () => {
    if (!config.apiKey && config.provider === 'openai') {
      setError('OpenAI 需要提供 API Key')
      return
    }

    // 保存到 localStorage
    localStorage.setItem('llm_config', JSON.stringify(config))

    // 同步到后端
    try {
      const result = await llmConfigApi.saveConfig({
        provider: config.provider,
        apiKey: config.apiKey,
        baseUrl: config.baseUrl,
        model: config.model,
        responseTime: config.responseTime,
        timeout: config.timeout,
      }) as any

      addLog(`✅ 后端配置已同步: ${config.provider} @ ${config.baseUrl}`)
      addLog(`超时时间设置为 ${result.timeout} 秒`)
      setSaved(true)
      setError('')
      setTimeout(() => setSaved(false), 2000)
    } catch (err: any) {
      setError(`保存到后端失败: ${err.message}`)
      addLog(`❌ 保存失败: ${err.message}`)
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
    
    const startTime = Date.now()
    
    try {
      addLog(`开始测试 ${config.provider} API...`)
      addLog(`Base URL: ${config.baseUrl}`)
      
      if (config.provider === 'openai') {
        // 测试 OpenAI API
        if (!config.apiKey) {
          throw new Error('OpenAI API Key 未设置')
        }
        
        addLog('发送测试请求到 OpenAI...')
        
        const response = await fetch(`${config.baseUrl}/chat/completions`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${config.apiKey}`,
          },
          body: JSON.stringify({
            model: config.model,
            messages: [
              { role: 'system', content: '你是一个测试助手，请简短回复。' },
              { role: 'user', content: '你好，这是一个测试消息，请回复"测试成功"。' }
            ],
            max_tokens: 50,
          }),
        })
        
        const responseTime = Date.now() - startTime
        
        if (!response.ok) {
          const errorData = await response.json().catch(() => ({}))
          throw new Error(errorData.error?.message || `HTTP ${response.status}`)
        }
        
        const data = await response.json()
        const reply = data.choices?.[0]?.message?.content || '无回复'
        
        addLog(`收到响应，耗时 ${responseTime}ms`)
        
        // 保存测试返回时长到配置（转换为秒）
        const responseTimeSec = Math.round(responseTime / 1000)
        setConfig(prev => ({ ...prev, responseTime: responseTimeSec }))
        
        setTestResult({
          success: true,
          message: '连接成功',
          responseTime,
          response: reply,
        })
      } else if (config.provider === 'deepseek') {
        // DeepSeek Direct API Test
        addLog(`Sending test request to DeepSeek Direct API...`)
        
        if (!config.apiKey) {
          throw new Error('DeepSeek API Key not set')
        }
        
        const testUrl = `${config.baseUrl}/chat/completions`
        addLog(`Request URL: ${testUrl}`)
        
        const response = await fetch(testUrl, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${config.apiKey}`,
          },
          body: JSON.stringify({
            model: config.model || 'deepseek-chat',
            messages: [
              { role: 'system', content: 'You are a test assistant.' },
              { role: 'user', content: 'Reply with "OK" only.' },
            ],
            max_tokens: 50,
          }),
        })
        
        const responseTime = Date.now() - startTime
        
        if (!response.ok) {
          const errorData = await response.json().catch(() => ({}))
          throw new Error(errorData.error?.message || `HTTP ${response.status}`)
        }
        
        const data = await response.json()
        const reply = data.choices?.[0]?.message?.content || 'No reply'
        
        addLog(`Got reply, took ${responseTime}ms`)
        
        const responseTimeSec = Math.round(responseTime / 1000)
        setConfig(prev => ({ ...prev, responseTime: responseTimeSec }))
        
        setTestResult({
          success: true,
          message: 'DeepSeek Connected',
          responseTime,
          response: reply,
        })
      
      } else {
        // 测试 Chat2Api 服务
        addLog(`发送测试请求到 ${config.provider}...`)
        
        const testUrl = `${config.baseUrl}/api/${config.provider}/chat`
        addLog(`请求地址: ${testUrl}`)
        
        const response = await fetch(testUrl, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            message: '你好，这是一个测试消息，请简短回复。',
            timeout: 30,
          }),
        })
        
        const responseTime = Date.now() - startTime
        
        if (!response.ok) {
          if (response.status === 401) {
            throw new Error(`${config.provider} 未登录，请先登录 chat2api`)
          }
          const text = await response.text()
          throw new Error(`HTTP ${response.status}: ${text}`)
        }
        
        const data = await response.json()
        
        if (!data.success) {
          throw new Error(data.message || '请求失败')
        }
        
        addLog(`收到响应，耗时 ${responseTime}ms`)
        
        // 保存测试返回时长到配置（转换为秒）
        const responseTimeSec = Math.round(responseTime / 1000)
        setConfig(prev => ({ ...prev, responseTime: responseTimeSec }))
        
        setTestResult({
          success: true,
          message: '连接成功',
          responseTime,
          response: data.data || '无回复内容',
        })
      }
    } catch (err: any) {
      const responseTime = Date.now() - startTime
      addLog(`测试失败: ${err.message}`)
      
      setTestResult({
        success: false,
        message: '连接失败',
        responseTime,
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
            LLM API 配置
          </h1>
          <p className="text-gray-500 dark:text-gray-400 mb-8">
            配置大语言模型 API，支持 OpenAI 或本地 Chat2Api 服务
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

            {/* API Key (仅 OpenAI 需要) */}
            {config.provider === 'openai' && (
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                  API Key
                </label>
                <input
                  type="password"
                  value={config.apiKey}
                  onChange={(e) => setConfig({ ...config, apiKey: e.target.value })}
                  placeholder="sk-..."
                  className="w-full px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white focus:ring-2 focus:ring-primary-500 focus:border-transparent"
                />
                <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
                  你的 OpenAI API Key，仅存储在本地浏览器
                </p>
              </div>
            )}

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
              <li>OpenAI: 需要有效的 API Key</li>
              <li>Chat2Api: 需要先启动 chat2api 服务并登录</li>
              <li>测试成功后再保存配置</li>
              <li>配置保存在浏览器本地存储</li>
            </ul>
          </div>
        </div>
      </div>
    </div>
  )
}
