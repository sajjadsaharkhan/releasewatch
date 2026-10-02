import { STATUS } from '../../lib/constants'

// What "Merge into this" will do to the candidate, per BR-49 — the sentence
// the API's merge_effect renders (FR-S13, AC-S11). The backend computes the
// effect with the merge's own reason function, so this never disagrees with
// what actually happens.
export function mergeEffectSentence(hint) {
  const label = STATUS[hint.candidate.status]?.label ?? hint.candidate.status
  switch (hint.merge_effect) {
    case 'stays_cancelled':
      return 'Stays Cancelled'
    case 'returns_release_qa':
      return 'Done → back to To do (release QA)'
    case 'returns_production':
      return 'Done → back to To do (production)'
    default:
      return `Stays ${label}`
  }
}
