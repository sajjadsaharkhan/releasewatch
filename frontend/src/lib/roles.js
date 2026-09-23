// Role-level gates for navigation and whole screens (PRD §7.3). These mirror
// backend/app/policy.py for things that aren't about one item. Anything about a
// specific item — buttons, menus, flags — reads the item's `allowed_actions` /
// `blocked_actions` instead (see components/common/ActionButton.jsx); never
// re-derive item permissions from the role here.

export const TECH_ROLES = ['qa', 'developer', 'pm', 'cto', 'admin']

/** Everyone except Support. */
export const isTech = (role) => TECH_ROLES.includes(role)

export const isSupport = (role) => role === 'support'

/** Where a role lands after sign-in or on `/`. Support has no dashboard. */
export const homePath = (role) => (isSupport(role) ? '/inbox' : '/dashboard')

/** Manage users and projects — Admin only (§7.3). */
export const canManageUsersAndProjects = (role) => role === 'admin'

export const ONLY_ADMINS_MANAGE_PROJECTS = 'Only admins can manage projects.'
export const ONLY_ADMINS_MANAGE_USERS = 'Only admins can manage users.'
