import { lazy, type ComponentType } from 'react'

/**
 * Helper to lazy-load modules with named exports.
 * React.lazy() expects a default export, but our pages use named exports.
 * This wrapper resolves the named export and returns it as the default.
 */
export function lazyNamed<T extends ComponentType<any>>(
  loader: () => Promise<{ [key: string]: T }>,
  exportName: string
) {
  return lazy(() =>
    loader().then((module) => ({
      default: module[exportName],
    }))
  )
}
