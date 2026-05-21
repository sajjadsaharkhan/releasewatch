import React, { useState, useEffect } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { IssueDetail } from '../components/issues/IssueDetail'
import { MOCK_ISSUES, issueById } from '../data/mockData'

export default function IssuePage() {
  const { id } = useParams()
  const navigate = useNavigate()
  const [issue, setIssue] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    if (!id) return
    setLoading(true)
    setError(null)

    // Simulate API call with mock data
    setTimeout(() => {
      const found = issueById(id)
      if (found) {
        setIssue(found)
        setLoading(false)
      } else {
        setError('Issue not found')
        setLoading(false)
      }
    }, 300)
  }, [id])

  const handleUpdate = async (patch) => {
    // Optimistic update
    setIssue(prev => ({ ...prev, ...patch }))
    // In real app, would make API call here
  }

  const handleClose = () => {
    navigate('/issues')
  }

  const handleNavigate = (direction) => {
    const currentIndex = MOCK_ISSUES.findIndex(i => i.id === id)
    if (currentIndex === -1) return

    let newIndex
    if (direction === 'prev') {
      newIndex = currentIndex - 1
      if (newIndex < 0) newIndex = MOCK_ISSUES.length - 1 // Wrap to end
    } else {
      newIndex = currentIndex + 1
      if (newIndex >= MOCK_ISSUES.length) newIndex = 0 // Wrap to start
    }

    const newIssue = MOCK_ISSUES[newIndex]
    navigate(`/issue/${newIssue.id}`)
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="text-zinc-500 text-sm">Loading issue…</div>
      </div>
    )
  }

  if (error || !issue) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="text-center">
          <div className="text-6xl mb-4">🔍</div>
          <h3 className="text-lg font-semibold text-zinc-900 dark:text-zinc-100 mb-2">Issue not found</h3>
          <p className="text-sm text-zinc-500 mb-4">{error || `"${id}" doesn't exist or you don't have access.`}</p>
          <button
            onClick={handleClose}
            className="inline-flex items-center gap-2 px-4 py-2 bg-zinc-900 dark:bg-zinc-100 text-white dark:text-zinc-900 rounded-lg hover:opacity-90"
          >
            Back to Issues
          </button>
        </div>
      </div>
    )
  }

  return <IssueDetail issue={issue} onUpdate={handleUpdate} onClose={handleClose} onNavigate={handleNavigate} />
}