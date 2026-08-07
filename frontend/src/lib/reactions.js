/**
 * Allowed comment reactions — mirrors `backend/app/core/reactions.py`.
 *
 * Keys are canonical and stable; the emoji is presentation only, so the glyphs
 * can change without touching stored data. Order here drives pill order in the
 * UI and must match the backend list so summaries render consistently.
 */
export const REACTIONS = [
  { key: '+1',       emoji: '👍', label: 'Like' },
  { key: '-1',       emoji: '👎', label: 'Dislike' },
  { key: 'laugh',    emoji: '😄', label: 'Laugh' },
  { key: 'hooray',   emoji: '🎉', label: 'Hooray' },
  { key: 'confused', emoji: '😕', label: 'Confused' },
  { key: 'heart',    emoji: '❤️', label: 'Love' },
  { key: 'rocket',   emoji: '🚀', label: 'Rocket' },
  { key: 'eyes',     emoji: '👀', label: 'Eyes' },
  { key: 'writing',  emoji: '✍️', label: 'Noted' },
  { key: 'nails',    emoji: '💅', label: 'Nailed it' },
]

export const REACTION_BY_KEY = Object.fromEntries(REACTIONS.map(r => [r.key, r]))

/** Emoji for a key, falling back to the key itself if it was retired. */
export function reactionEmoji(key) {
  return REACTION_BY_KEY[key]?.emoji ?? key
}

/** Human label for a key, e.g. for aria-label and tooltips. */
export function reactionLabel(key) {
  return REACTION_BY_KEY[key]?.label ?? key
}
