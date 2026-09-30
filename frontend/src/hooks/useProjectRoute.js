import { useEffect, useRef } from 'react'
import { useNavigate, useParams, useSearchParams } from 'react-router-dom'
import { useApp } from './useApp'

// `/projects/:slug/<section>` pages (Stream, Releases): the URL's project and
// the active project stay in step, the way the Backlog page does it. The URL
// wins when it names a project; once they agree, a later change of the active
// project (the topbar switcher) moves the page to that project's <section>.
// `redirectTo` is where a slug-less route (e.g. `/releases`) should go.
export function useProjectRoute(section) {
  const { slug } = useParams()
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const { projects, activeProjectId, switchProject, projectsLoading } = useApp()
  const project = projects?.find((p) => p.slug === slug) ?? null

  const synced = useRef(false)
  const urlProjectId = useRef(null)
  useEffect(() => {
    if (!project) return
    if (urlProjectId.current !== project.id) {
      urlProjectId.current = project.id
      synced.current = false
    }
    if (String(activeProjectId) === String(project.id)) {
      synced.current = true
      return
    }
    if (!synced.current) {
      switchProject(project.id)
      return
    }
    const next = projects.find((p) => String(p.id) === String(activeProjectId))
    if (next) navigate(`/projects/${next.slug}/${section}`)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [project?.id, activeProjectId])

  const fallback = projects?.find((p) => String(p.id) === String(activeProjectId)) ?? projects?.[0]
  return {
    slug,
    project,
    projectsLoading,
    notFound: Boolean(slug && projects?.length && !project),
    redirectTo: !slug && fallback ? `/projects/${fallback.slug}/${section}?${searchParams.toString()}` : null,
  }
}
