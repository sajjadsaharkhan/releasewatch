/**
 * Calculate contrasting text color for a given hex background color
 * Returns black or white based on luminance for optimal readability
 *
 * @param {string} hexColor - Hex color code (e.g., "#6366f1")
 * @returns {string} - "#000000" or "#ffffff"
 */
export function getContrastColor(hexColor) {
  if (!hexColor || typeof hexColor !== 'string') {
    return '#000000'
  }

  // Remove hash if present
  const hex = hexColor.replace('#', '')

  // Ensure 6 characters
  const fullHex = hex.length === 3
    ? hex.split('').map(char => char + char).join('')
    : hex

  if (fullHex.length !== 6) {
    return '#000000'
  }

  // Convert hex to RGB
  const r = parseInt(fullHex.slice(0, 2), 16)
  const g = parseInt(fullHex.slice(2, 4), 16)
  const b = parseInt(fullHex.slice(4, 6), 16)

  // Calculate luminance using standard formula
  const luminance = (0.299 * r + 0.587 * g + 0.114 * b) / 255

  // Return black or white based on luminance threshold
  return luminance > 0.5 ? '#000000' : '#ffffff'
}