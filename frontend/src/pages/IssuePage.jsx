import React, { useState, useEffect } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { IssueDetail } from '../components/issues/IssueDetail'
import { issuesApi } from '../lib/api'

export default function IssuePage() {
  const { slug } = useParams()
  const navigate = useNavigate()
  const [issue, setIssue] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  const issueNum = slug?.startsWith('issue-') ? parseInt(slug.slice(6), 10) : null

  useEffect(() => {
    if (!issueNum) { setError('Invalid issue reference'); setLoading(false); return }
    setLoading(true)
    setError(null)
    issuesApi.getByNumber(issueNum)
      .then(res => { setIssue(res.data); setLoading(false) })
      .catch(() => { setError('Issue not found'); setLoading(false) })
  }, [issueNum])

  const handleUpdate = (_freshIssue) => {
    // useIssueDetail owns the live issue copy; no page-level sync needed.
    // issue_number is immutable so handleNavigate still works from initial fetch.
  }

  const handleClose = () => navigate('/issues')

  const handleNavigate = (direction) => {
    if (!issue) return
    const nextNum = direction === 'prev' ? issue.issue_number - 1 : issue.issue_number + 1
    navigate(`/issue/issue-${nextNum}`)
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
          <p className="text-sm text-zinc-500 mb-4">{error || `"${slug}" doesn't exist or you don't have access.`}</p>
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

  return <IssueDetail key={issue.id} issue={issue} onUpdate={handleUpdate} onClose={handleClose} onNavigate={handleNavigate} />
}
