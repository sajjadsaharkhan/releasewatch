import { useEffect, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { IssueDetail } from '../components/issues'
import { Empty } from '../components/ui'
import { issuesApi } from '../lib/api'
import { MOCK_ISSUES } from '../data/mockData'

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

    // Try API first, fall back to mock data
    issuesApi.get(id)
      .then(res => setIssue(res.data))
      .catch(() => {
        const mock = MOCK_ISSUES.find(i => i.id === id || i.id === id.toUpperCase())
        if (mock) {
          setIssue(mock)
        } else {
          setError('Issue not found')
        }
      })
      .finally(() => setLoading(false))
  }, [id])

  const handleUpdate = async (patch) => {
    try {
      const res = await issuesApi.update(id, patch)
      setIssue(res.data)
    } catch {
      // optimistic update for mock mode
      setIssue(prev => ({ ...prev, ...patch }))
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64 text-zinc-400 text-sm">
        Loading issue…
      </div>
    )
  }

  if (error || !issue) {
    return (
      <div className="flex items-center justify-center h-full">
        <Empty
          icon="bug-off"
          title="Issue not found"
          body={`"${id}" doesn't exist or you don't have access.`}
        />
      </div>
    )
  }

  return <IssueDetail issue={issue} onUpdate={handleUpdate} />
}
