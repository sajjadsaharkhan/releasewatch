// Item links that also run an in-app handler (the My Work rows and the board
// cards). A plain left click runs the handler in this tab; Ctrl/Cmd-click,
// Shift-click, middle-click and the context menu's "Open in new tab" are left
// to the browser, so the item opens in a new tab or window as with any link.

export function isPlainClick(e) {
  return e.button === 0 && !e.metaKey && !e.ctrlKey && !e.shiftKey && !e.altKey
}
