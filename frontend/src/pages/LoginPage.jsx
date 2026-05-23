import React, { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { LogIn, Eye, EyeOff, AlertCircle } from 'lucide-react'
import { cn } from '../lib/cn'
import { Button } from '../components/ui/Button'
import { Input } from '../components/ui/Input'
import { authApi } from '../lib/api'
import { useApp } from '../hooks/useApp'

export default function LoginPage() {
  const navigate = useNavigate()
  const { login } = useApp()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError('')
    setLoading(true)

    try {
      const response = await authApi.login(email, password)
      const { access_token, refresh_token } = response.data

      // Store tokens
      localStorage.setItem('rw:token', access_token)
      localStorage.setItem('rw:refresh_token', refresh_token)

      // Fetch user data and update auth state
      const meResponse = await authApi.me()
      login(meResponse.data, access_token)

      // Navigate to dashboard
      navigate('/dashboard')
    } catch (err) {
      const message = err.response?.data?.detail || 'Login failed. Please check your credentials.'
      setError(message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-zinc-50 dark:bg-zinc-900 px-4">
      <div className="w-full max-w-md">
        {/* Logo/Brand */}
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-12 h-12 rounded-xl bg-indigo-600 mb-4">
            <svg className="w-7 h-7 text-white" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5" strokeLinecap="round" strokeLinejoin="round"/>
            </svg>
          </div>
          <h1 className="text-2xl font-bold text-zinc-900 dark:text-zinc-100">Releasewatch</h1>
          <p className="text-sm text-zinc-600 dark:text-zinc-400 mt-1">Sign in to your workspace</p>
        </div>

        {/* Login Form */}
        <div className="bg-white dark:bg-zinc-800 rounded-xl shadow-sm border border-zinc-200 dark:border-zinc-700 p-6">
          <form onSubmit={handleSubmit} className="space-y-4">
            {/* Error Message */}
            {error && (
              <div className="flex items-start gap-2 p-3 rounded-lg bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800">
                <AlertCircle className="w-4 h-4 text-red-600 dark:text-red-400 mt-0.5 flex-shrink-0" />
                <p className="text-sm text-red-700 dark:text-red-300">{error}</p>
              </div>
            )}

            {/* Email */}
            <div>
              <label htmlFor="email" className="block text-sm font-medium text-zinc-700 dark:text-zinc-300 mb-1.5">
                Email
              </label>
              <Input
                id="email"
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="you@example.com"
                required
                autoFocus
                className="w-full"
              />
            </div>

            {/* Password */}
            <div>
              <label htmlFor="password" className="block text-sm font-medium text-zinc-700 dark:text-zinc-300 mb-1.5">
                Password
              </label>
              <div className="relative">
                <Input
                  id="password"
                  type={showPassword ? 'text' : 'password'}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="••••••••"
                  required
                  className="w-full pr-10"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-zinc-500 hover:text-zinc-700 dark:text-zinc-400 dark:hover:text-zinc-200"
                >
                  {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                </button>
              </div>
            </div>

            {/* Remember Me */}
            <div className="flex items-center justify-between">
              <label className="flex items-center gap-2 cursor-pointer">
                <input type="checkbox" className="rounded border-zinc-300 text-indigo-600 focus:ring-indigo-500" />
                <span className="text-sm text-zinc-600 dark:text-zinc-400">Remember me</span>
              </label>
              <a href="#forgot-password" className="text-sm text-indigo-600 hover:text-indigo-500 dark:text-indigo-400">
                Forgot password?
              </a>
            </div>

            {/* Submit Button */}
            <Button
              type="submit"
              disabled={loading}
              className="w-full"
            >
              {loading ? (
                <>
                  <svg className="animate-spin -ml-1 mr-2 h-4 w-4" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                  </svg>
                  Signing in...
                </>
              ) : (
                <>
                  <LogIn className="w-4 h-4 mr-2" />
                  Sign in
                </>
              )}
            </Button>
          </form>

          {/* Demo Notice */}
          <div className="mt-6 pt-6 border-t border-zinc-200 dark:border-zinc-700">
            <p className="text-xs text-center text-zinc-500 dark:text-zinc-400">
              Demo credentials: <span className="font-mono bg-zinc-100 dark:bg-zinc-700 px-1.5 py-0.5 rounded">admin@example.com</span> / <span className="font-mono bg-zinc-100 dark:bg-zinc-700 px-1.5 py-0.5 rounded">password123</span>
            </p>
          </div>
        </div>

        {/* Footer */}
        <p className="text-center text-sm text-zinc-600 dark:text-zinc-400 mt-6">
          Don't have an account? <a href="#signup" className="text-indigo-600 hover:text-indigo-500 dark:text-indigo-400 font-medium">Contact your admin</a>
        </p>
      </div>
    </div>
  )
}
