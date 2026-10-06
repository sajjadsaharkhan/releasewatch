// Syntax highlighting for CodeBlock: Shiki (VS Code's TextMate grammars and
// GitHub themes) on the JavaScript regex engine — no WASM. Loaded lazily by
// CodeBlock; each language's grammar loads the first time a block uses it.
// To support a language, add it to LANGS (and its fence aliases to ALIASES).
import { createHighlighterCore } from 'shiki/core'
import { createJavaScriptRegexEngine } from 'shiki/engine/javascript'

const LANGS = {
  bash: ['Bash', () => import('@shikijs/langs/bash')],
  c: ['C', () => import('@shikijs/langs/c')],
  cpp: ['C++', () => import('@shikijs/langs/cpp')],
  csharp: ['C#', () => import('@shikijs/langs/csharp')],
  css: ['CSS', () => import('@shikijs/langs/css')],
  diff: ['Diff', () => import('@shikijs/langs/diff')],
  docker: ['Dockerfile', () => import('@shikijs/langs/docker')],
  go: ['Go', () => import('@shikijs/langs/go')],
  html: ['HTML', () => import('@shikijs/langs/html')],
  http: ['HTTP', () => import('@shikijs/langs/http')],
  ini: ['INI', () => import('@shikijs/langs/ini')],
  java: ['Java', () => import('@shikijs/langs/java')],
  javascript: ['JavaScript', () => import('@shikijs/langs/javascript')],
  json: ['JSON', () => import('@shikijs/langs/json')],
  jsx: ['JSX', () => import('@shikijs/langs/jsx')],
  kotlin: ['Kotlin', () => import('@shikijs/langs/kotlin')],
  markdown: ['Markdown', () => import('@shikijs/langs/markdown')],
  php: ['PHP', () => import('@shikijs/langs/php')],
  powershell: ['PowerShell', () => import('@shikijs/langs/powershell')],
  python: ['Python', () => import('@shikijs/langs/python')],
  razor: ['Razor', () => import('@shikijs/langs/razor')],
  ruby: ['Ruby', () => import('@shikijs/langs/ruby')],
  rust: ['Rust', () => import('@shikijs/langs/rust')],
  scss: ['SCSS', () => import('@shikijs/langs/scss')],
  sql: ['SQL', () => import('@shikijs/langs/sql')],
  swift: ['Swift', () => import('@shikijs/langs/swift')],
  toml: ['TOML', () => import('@shikijs/langs/toml')],
  tsx: ['TSX', () => import('@shikijs/langs/tsx')],
  typescript: ['TypeScript', () => import('@shikijs/langs/typescript')],
  xml: ['XML', () => import('@shikijs/langs/xml')],
  yaml: ['YAML', () => import('@shikijs/langs/yaml')],
}

// Fence names people type → a LANGS key.
const ALIASES = {
  cs: 'csharp', 'c#': 'csharp', dotnet: 'csharp', cshtml: 'razor',
  sh: 'bash', shell: 'bash', zsh: 'bash', curl: 'bash', console: 'bash', terminal: 'bash',
  js: 'javascript', mjs: 'javascript', cjs: 'javascript', ts: 'typescript',
  py: 'python', rb: 'ruby', rs: 'rust', kt: 'kotlin', golang: 'go',
  'c++': 'cpp', h: 'c', hpp: 'cpp', ps1: 'powershell', pwsh: 'powershell',
  yml: 'yaml', md: 'markdown', dockerfile: 'docker', env: 'ini', patch: 'diff',
  svg: 'xml', vue: 'html',
}

const resolve = (lang) => {
  const name = lang?.toLowerCase()
  return name && (LANGS[name] ? name : ALIASES[name])
}

let highlighterPromise = null
const getHighlighter = () => (highlighterPromise ??= createHighlighterCore({
  themes: [import('@shikijs/themes/github-light'), import('@shikijs/themes/github-dark')],
  langs: [],
  engine: createJavaScriptRegexEngine(),
}))

/**
 * Highlighted HTML (inline spans, lines split by <br>) for `code`, or null for
 * an unknown language. Each span carries --shiki-light / --shiki-dark colors,
 * picked by the theme in globals.css. Shiki escapes the source.
 */
export async function highlight(code, lang) {
  const name = resolve(lang)
  if (!name) return null
  const hl = await getHighlighter()
  if (!hl.getLoadedLanguages().includes(name)) await hl.loadLanguage(LANGS[name][1]())
  return hl.codeToHtml(code, {
    lang: name,
    themes: { light: 'github-light', dark: 'github-dark' },
    defaultColor: false,
    structure: 'inline',
  })
}

/** Display name for the code block header, e.g. "C#" for `cs`; the fence text if unknown. */
export function languageLabel(lang) {
  const name = resolve(lang)
  return name ? LANGS[name][0] : lang
}
