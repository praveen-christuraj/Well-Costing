/**
 * Signal that a user cancelled a destructive action.
 *
 * A delete handler can raise this instead of resolving so the caller knows the
 * record was deliberately left alone, rather than treating the rejection as a
 * failure and falling back to deactivation.
 */
export class DeleteCancelledError extends Error {
  constructor(message = 'Delete cancelled.') {
    super(message)
    this.name = 'DeleteCancelled'
  }
}

export function isDeleteCancelled(error: unknown): boolean {
  return error instanceof Error && error.name === 'DeleteCancelled'
}
