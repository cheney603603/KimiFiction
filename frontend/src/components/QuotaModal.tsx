import { useState, useEffect } from 'react'

interface QuotaEvent extends Event {
  detail?: string
}

/**
 * 全局额度超限弹层：监听 `quota-exceeded` 事件（由 axios 402 拦截器派发）。
 * 升级按钮为占位（真支付上线前引导联系管理员）。
 */
export function QuotaModal() {
  const [open, setOpen] = useState(false)
  const [message, setMessage] = useState('')
  const [showUpgradeHint, setShowUpgradeHint] = useState(false)

  useEffect(() => {
    const handler = (e: QuotaEvent) => {
      setMessage(e.detail || '额度已用完，升级 Pro 可继续创作')
      setShowUpgradeHint(false)
      setOpen(true)
    }
    window.addEventListener('quota-exceeded', handler as EventListener)
    return () => window.removeEventListener('quota-exceeded', handler as EventListener)
  }, [])

  if (!open) return null

  return (
    <div
      className="fixed inset-0 z-[100] flex items-center justify-center bg-black/50 p-4"
      data-quota-modal
      onClick={() => setOpen(false)}
    >
      <div
        className="w-full max-w-md bg-white dark:bg-gray-800 rounded-xl shadow-xl border border-gray-200 dark:border-gray-700 p-6"
        onClick={e => e.stopPropagation()}
      >
        <div className="flex items-center gap-3 mb-3">
          <span className="text-2xl">⛽</span>
          <h2 className="text-lg font-bold text-gray-900 dark:text-white">额度已用完</h2>
        </div>
        <p className="text-sm text-gray-600 dark:text-gray-300 mb-4">{message}</p>
        {showUpgradeHint && (
          <div className="p-3 mb-4 bg-indigo-50 dark:bg-indigo-900/30 border border-indigo-200 dark:border-indigo-800 rounded-lg text-sm text-indigo-700 dark:text-indigo-300">
            Pro 升级通道即将上线。当前可联系管理员在「额度墙」中为你开通 Pro。
          </div>
        )}
        <div className="flex justify-end gap-3">
          <button
            onClick={() => setOpen(false)}
            className="px-4 py-2 bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-200 rounded-lg text-sm hover:bg-gray-200 dark:hover:bg-gray-600"
          >
            知道了
          </button>
          <button
            onClick={() => setShowUpgradeHint(true)}
            className="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 text-white rounded-lg text-sm font-medium"
          >
            升级 Pro
          </button>
        </div>
      </div>
    </div>
  )
}
