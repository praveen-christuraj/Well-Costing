/** Browser download helpers shared by every export button. */

/** Save a fetched blob under `filename` using a transient object URL. */
export function downloadBlob(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob)
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = filename
  anchor.rel = 'noopener'
  document.body.appendChild(anchor)
  anchor.click()
  anchor.remove()
  URL.revokeObjectURL(url)
}

/** `vendors` → `vendors-export.xlsx`, matching the API's Content-Disposition. */
export function exportFilename(entity: string): string {
  return `${entity}-export.xlsx`
}
