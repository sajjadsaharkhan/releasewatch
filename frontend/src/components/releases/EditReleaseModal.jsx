import React from 'react'
import { ReleaseFormModal } from './ReleaseFormModal'

// Edit a release's fields (FR-49). Status moves live in the lifecycle menu.
export function EditReleaseModal({ open, onClose, release, onSave }) {
  return <ReleaseFormModal open={open} onClose={onClose} release={release} onSaved={onSave} />
}
