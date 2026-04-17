import { Link, useLocation, useNavigate, Outlet } from 'react-router-dom'
import { BookOpen, Home, Settings, Moon, Sun, User, LogOut, GitBranch, BarChart3 } from 'lucide-react'
import { useState, useEffect } from 'react'

interface LayoutProps {
  children: React.ReactNode
}

interface UserInfo {
  id: number
  username: string
  nickname?: string
  avatar?: string
}

export function Layout(_props: LayoutProps) {
  const location = useLocation()
  const navigate = useNavigate()
  const [darkMode, setDarkMode] = useState(false)
  const [user, setUser] = useState<UserInfo | null>(null)
  const [showUserMenu, setShowUserMenu] = useState(false)

  useEffect(() => {
    if (darkMode) {
      document.documentElement.classList.add('dark')
    } else {
      document.documentElement.classList.remove('dark')
    }
  }, [darkMode])

  useEffect(() => {
    // 从localStorage获取用户信息
    const userStr = localStorage.getItem('user')
    if (userStr) {
      try {
        setUser(JSON.parse(userStr))
      } catch {
        // 解析失败，忽略
      }
    }
  }, [])

  const handleLogout = () => {
    localStorage.removeItem('access_token')
    localStorage.removeItem('user')
    navigate('/login')
  }

  const navItems = [
    { path: '/', label: '工作台', icon: Home },
    { path: '/workflow/graph', label: 'Agent协作', icon: GitBranch },
    { path: '/training', label: 'RL训练', icon: BarChart3 },
    { path: '/evaluation', label: '八维评测', icon: BarChart3 },
    { path: '/settings/llm', label: 'API配置', icon: Settings },
  ]

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-gray-900 transition-colors">
      {/* 顶部导航 */}
      <header className="bg-white dark:bg-gray-800 shadow-sm border-b border-gray-200 dark:border-gray-700">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between h-16">
            <div className="flex items-center">
              <Link to="/" className="flex items-center gap-2">
                <BookOpen className="h-8 w-8 text-primary-600" />
                <span className="text-xl font-bold text-gray-900 dark:text-white">
                  NovelGen
                </span>
              </Link>
            </div>
            
            <nav className="flex items-center gap-4">
              {navItems.map((item) => (
                <Link
                  key={item.path}
                  to={item.path}
                  className={`flex items-center gap-2 px-3 py-2 rounded-md text-sm font-medium transition-colors ${
                    location.pathname === item.path
                      ? 'bg-primary-100 text-primary-700 dark:bg-primary-900 dark:text-primary-300'
                      : 'text-gray-600 hover:bg-gray-100 dark:text-gray-300 dark:hover:bg-gray-700'
                  }`}
                >
                  <item.icon className="h-4 w-4" />
                  {item.label}
                </Link>
              ))}
              
              <button
                onClick={() => setDarkMode(!darkMode)}
                className="p-2 rounded-md text-gray-600 hover:bg-gray-100 dark:text-gray-300 dark:hover:bg-gray-700"
              >
                {darkMode ? <Sun className="h-5 w-5" /> : <Moon className="h-5 w-5" />}
              </button>

              {/* 用户菜单 */}
              <div className="relative">
                <button
                  onClick={() => setShowUserMenu(!showUserMenu)}
                  className="flex items-center gap-2 p-2 rounded-md hover:bg-gray-100 dark:hover:bg-gray-700"
                >
                  <div className="w-8 h-8 rounded-full bg-primary-100 dark:bg-primary-900 flex items-center justify-center">
                    {user?.avatar ? (
                      <img src={user.avatar} alt={user.username} className="w-8 h-8 rounded-full" />
                    ) : (
                      <User className="h-5 w-5 text-primary-600" />
                    )}
                  </div>
                  <span className="text-sm text-gray-700 dark:text-gray-300 hidden sm:block">
                    {user?.nickname || user?.username || '用户'}
                  </span>
                </button>

                {showUserMenu && (
                  <div className="absolute right-0 mt-2 w-48 bg-white dark:bg-gray-800 rounded-lg shadow-lg border border-gray-200 dark:border-gray-700 py-1 z-50">
                    <div className="px-4 py-2 border-b border-gray-200 dark:border-gray-700">
                      <p className="text-sm font-medium text-gray-900 dark:text-white">
                        {user?.nickname || user?.username}
                      </p>
                      <p className="text-xs text-gray-500 dark:text-gray-400">
                        {user?.username}
                      </p>
                    </div>
                    <button
                      onClick={handleLogout}
                      className="w-full flex items-center gap-2 px-4 py-2 text-sm text-red-600 hover:bg-red-50 dark:hover:bg-red-900/20"
                    >
                      <LogOut className="h-4 w-4" />
                      退出登录
                    </button>
                  </div>
                )}
              </div>
            </nav>
          </div>
        </div>
      </header>

      {/* 主内容区 */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <Outlet />
      </main>

      {/* 页脚 */}
      <footer className="bg-white dark:bg-gray-800 border-t border-gray-200 dark:border-gray-700 mt-auto">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
          <p className="text-center text-sm text-gray-500 dark:text-gray-400">
            NovelGen - 多智能体小说生成系统
          </p>
        </div>
      </footer>

      {/* 点击外部关闭用户菜单 */}
      {showUserMenu && (
        <div
          className="fixed inset-0 z-40"
          onClick={() => setShowUserMenu(false)}
        />
      )}
    </div>
  )
}
