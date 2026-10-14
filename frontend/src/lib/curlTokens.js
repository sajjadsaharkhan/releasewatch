// Synchronous tokenizer for cURL commands, so an editor can recolor on every
// keystroke without waiting on Shiki. Tokens concatenate back to the input
// exactly — CurlEditor overlays them on a textarea and relies on that.
//
// Token types: command, flag, method, url, string, variable, continuation,
// comment, text.

const METHODS = /^(GET|POST|PUT|PATCH|DELETE|HEAD|OPTIONS)$/
const TOKEN = new RegExp([
  /(#[^\n]*)/.source,                              // 1 comment
  /("(?:\\.|[^"\\])*"?|'[^']*'?)/.source,          // 2 quoted string (may be unterminated)
  /(\\(?=\n|$))/.source,                           // 3 line continuation
  /(\$\{?[A-Za-z_][A-Za-z0-9_]*\}?)/.source,       // 4 variable
  /(--?[A-Za-z][\w-]*)/.source,                    // 5 flag
  /([^\s"'$\\]+)/.source,                          // 6 bare word
  /([\s\S])/.source,                               // 7 anything else
].join('|'), 'g')

export function tokenizeCurl(src) {
  const tokens = []
  let prevFlag = null
  for (const m of src.matchAll(TOKEN)) {
    const [value, comment, string, cont, variable, flag, word] = m
    let type = 'text'
    if (comment) type = 'comment'
    else if (string) type = 'string'
    else if (cont) type = 'continuation'
    else if (variable) type = 'variable'
    else if (flag && /(^|\s)$/.test(src.slice(0, m.index))) type = 'flag'
    else if (word || flag) {
      if (word === 'curl') type = 'command'
      else if ((prevFlag === '-X' || prevFlag === '--request') && METHODS.test(word)) type = 'method'
      else if (/^https?:\/\//i.test(value)) type = 'url'
    }
    if (/\S/.test(value)) prevFlag = type === 'flag' ? value : null
    const last = tokens[tokens.length - 1]
    if (last && last.type === type && type === 'text') last.value += value
    else tokens.push({ type, value })
  }
  return tokens
}
