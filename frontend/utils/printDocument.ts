/**
 * Print helper: opens a dedicated window with a clean, record-quality layout
 * and triggers the browser's print dialog. Used for the well-scoped AFE,
 * AFE Cost Estimate, and Daily Cost report printouts kept for records.
 */

const PRINT_STYLES = `
  * { box-sizing: border-box; }
  body { font-family: 'Segoe UI', Arial, sans-serif; color: #111827; margin: 24px; font-size: 12px; }
  h1 { font-size: 20px; margin: 0 0 2px; letter-spacing: 0.02em; }
  h2 { font-size: 14px; margin: 18px 0 6px; border-bottom: 2px solid #0f766e; padding-bottom: 3px; }
  .doc-subtitle { color: #4b5563; margin: 0 0 14px; }
  .meta-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 6px 18px; margin: 10px 0 4px; }
  .meta-grid div { padding: 3px 0; }
  .meta-grid span { display: block; font-size: 10px; text-transform: uppercase; letter-spacing: 0.06em; color: #6b7280; }
  .meta-grid strong { font-size: 12px; }
  table { width: 100%; border-collapse: collapse; margin: 6px 0 12px; }
  th { background: #0f766e; color: #fff; text-align: left; padding: 5px 6px; font-size: 11px; }
  td { border: 1px solid #d1d5db; padding: 4px 6px; font-size: 11px; }
  td.num, th.num { text-align: right; font-variant-numeric: tabular-nums; }
  tr.total-row td { font-weight: 700; background: #f0fdfa; }
  .signatures { display: grid; grid-template-columns: repeat(3, 1fr); gap: 32px; margin-top: 42px; }
  .signatures div { border-top: 1px solid #111827; padding-top: 6px; font-size: 11px; color: #374151; }
  .print-footer { margin-top: 24px; font-size: 10px; color: #6b7280; }
  @media print { body { margin: 8mm; } }
`

export function printDocument(title: string, bodyHtml: string): void {
  const printWindow = window.open('', '_blank', 'width=1024,height=768')
  if (!printWindow) return
  printWindow.document.write(
    `<!DOCTYPE html><html><head><meta charset="utf-8"><title>${escapeHtml(title)}</title>`
    + `<style>${PRINT_STYLES}</style></head><body>${bodyHtml}</body></html>`,
  )
  printWindow.document.close()
  printWindow.focus()
  // Give the new window a moment to render before opening the dialog.
  window.setTimeout(() => { printWindow.print() }, 350)
}

export function escapeHtml(value: unknown): string {
  return String(value ?? '')
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
}

export function formatMoneyCell(value: string | number | null | undefined): string {
  const numeric = Number(value ?? 0)
  if (!Number.isFinite(numeric)) return '—'
  return numeric.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}
