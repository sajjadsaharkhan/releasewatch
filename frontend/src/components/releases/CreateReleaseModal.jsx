import React from 'react'
import { ReleaseFormModal } from './ReleaseFormModal'

// New release (slice 09): one form with Edit — see ReleaseFormModal.
export function CreateReleaseModal({ open, onClose, onCreated, projectId }) {
  return <ReleaseFormModal open={open} onClose={onClose} projectId={projectId} onSaved={onCreated} />
}
