/**
 * Advanced, field-agnostic search used by every catalogue grid, trash view,
 * rate-history panel and audit log. A query is split into tokens (quoted
 * phrases stay together); every token must appear somewhere in the haystack
 * so typing a vendor name, a code, a type or any mix of those all work.
 */

const TOKEN_RE = /"([^"]+)"|(\S+)/g

/** Lower-case tokens; `"exact phrase"` is kept as one token. */
export function tokenizeSearch(query: string): string[] {
  const trimmed = query.trim()
  if (!trimmed) return []
  const tokens: string[] = []
  TOKEN_RE.lastIndex = 0
  let match: RegExpExecArray | null
  while ((match = TOKEN_RE.exec(trimmed)) !== null) {
    const token = (match[1] ?? match[2] ?? '').trim().toLowerCase()
    if (token) tokens.push(token)
  }
  return tokens
}

function flattenSearchable(value: unknown, depth = 0): string[] {
  if (value == null || depth > 4) return []
  const kind = typeof value
  if (kind === 'string' || kind === 'number' || kind === 'boolean' || kind === 'bigint') {
    const text = String(value).trim()
    return text ? [text] : []
  }
  if (Array.isArray(value)) {
    return value.flatMap(item => flattenSearchable(item, depth + 1))
  }
  if (kind === 'object') {
    return Object.entries(value as Record<string, unknown>)
      .filter(([key]) => !key.startsWith('_'))
      .flatMap(([, item]) => flattenSearchable(item, depth + 1))
  }
  return []
}

/**
 * True when every search token appears in the flattened source. An empty
 * query matches everything. Field boundaries are preserved so adjacent
 * values cannot combine into a false-positive match.
 */
export function matchesAdvancedSearch(source: unknown, query: string): boolean {
  const tokens = tokenizeSearch(query)
  if (!tokens.length) return true
  const haystack = flattenSearchable(source).join('\u001f').toLowerCase()
  return tokens.every(token => haystack.includes(token))
}
