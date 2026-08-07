"""Allowed emoji reactions — the single backend source of truth.

Reactions are stored as canonical string keys rather than raw glyphs so that
unicode variation selectors and skin-tone modifiers can never produce duplicate
rows, and so the rendered emoji can change without a data migration.

``frontend/src/lib/reactions.js`` mirrors this list (same keys, same order).
"""

ALLOWED_REACTIONS: list[str] = [
    "+1",
    "-1",
    "laugh",
    "hooray",
    "confused",
    "heart",
    "rocket",
    "eyes",
    "writing",
    "nails",
]

# How long to wait before delivering a reaction's Telegram message. The window
# lets the reactor change or undo their choice first — see
# ``ReactionService.reaction_notification_still_valid``.
REACTION_TELEGRAM_DELAY = 60

# Rendering map — used for Telegram notification bodies, where the glyph must be
# embedded in the message text.
REACTION_EMOJI: dict[str, str] = {
    "+1": "👍",
    "-1": "👎",
    "laugh": "😄",
    "hooray": "🎉",
    "confused": "😕",
    "heart": "❤️",
    "rocket": "🚀",
    "eyes": "👀",
    "writing": "✍️",
    "nails": "💅",
}
