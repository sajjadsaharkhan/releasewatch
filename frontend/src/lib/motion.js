// Motion tokens — Animate UI's (animate-ui.com, utils/motion), copied by value.
// The package needs React 19 and Releasewatch is on 18, so the values live here
// and Motion (`motion/react`) plays them. One token per motion role: take the
// role's token rather than hand-typing a spring or curve. Animate opacity and
// `transform` strings — Motion runs those on the compositor — and keep blur off
// large surfaces (docs/design.md §8).

export const ease = {
  out: [0.23, 1, 0.32, 1],
  soft: [0.215, 0.61, 0.355, 1],
  inOut: [0.77, 0, 0.175, 1],
  away: [0.33, 0.17, 0.67, 0.5],
  color: [0.25, 0.1, 0.25, 1],
}

export const spring = {
  press: { type: 'spring', stiffness: 550, damping: 30, restSpeed: 10 },
  pop: { type: 'spring', stiffness: 400, damping: 29 },
  dialog: { type: 'spring', stiffness: 150, damping: 25 },
  selection: { type: 'spring', stiffness: 300, damping: 30 },
  morph: { type: 'spring', stiffness: 660, damping: 52 },
}

export const transition = {
  overlay: { duration: 0.4, ease: ease.soft },
  dialogFade: { duration: 0.4, ease: ease.soft },
  fade: { duration: 0.2, ease: ease.out },
  reveal: { duration: 0.3, ease: ease.out },
  swap: { duration: 0.15, ease: ease.out },
  sheet: { duration: 0.4, ease: ease.soft },
  dismiss: { duration: 0.2, ease: ease.away },
  instant: { duration: 0 },
}

export const scale = { press: 0.97, popover: 0.8, dialog: 0.8, icon: 0.5 }

export const blur = { icon: 'blur(2px)', surface: 'blur(4px)' }

export const shift = { handoff: 6 }
