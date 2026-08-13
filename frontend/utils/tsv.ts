export interface PasteColumn {
  field: string
}

export function parseTsv(
  text: string,
  columns: PasteColumn[],
): Record<string, string>[] {
  const normalized = text.replace(/\r\n/g, '\n').replace(/\r/g, '\n').trimEnd()
  if (!normalized) return []
  return normalized.split('\n').map((line) => {
    const cells = line.split('\t')
    return Object.fromEntries(
      columns.map((column, index) => [column.field, cells[index]?.trim() ?? '']),
    )
  })
}
