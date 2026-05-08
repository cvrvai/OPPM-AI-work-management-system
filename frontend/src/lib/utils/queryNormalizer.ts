import type { QueryClient } from '@tanstack/react-query'

/**
 * Normalized cache helpers.
 * When an entity is updated, these utilities update it across
 * all matching query keys so every list/object view stays in sync
 * without extra network requests.
 */

/**
 * Update a single entity in all cache entries whose query key starts with
 * the given prefix. Useful when an entity appears in multiple lists.
 */
export function updateEntityInCache<T extends { id: string }>(
  queryClient: QueryClient,
  entity: T,
  keyPrefixes: string[][]
): void {
  for (const prefix of keyPrefixes) {
    queryClient.setQueriesData<T[] | T | undefined>(
      { queryKey: prefix, exact: false },
      (old) => {
        if (Array.isArray(old)) {
          return old.map((item) =>
            item.id === entity.id ? { ...item, ...entity } : item
          ) as T[]
        }
        if (old && typeof old === 'object' && 'id' in old && old.id === entity.id) {
          return { ...old, ...entity } as T
        }
        return old
      }
    )
  }
}

/**
 * Remove an entity from all cache entries matching the given key prefixes.
 */
export function removeEntityFromCache<T extends { id: string }>(
  queryClient: QueryClient,
  entityId: string,
  keyPrefixes: string[][]
): void {
  for (const prefix of keyPrefixes) {
    queryClient.setQueriesData<T[] | undefined>(
      { queryKey: prefix, exact: false },
      (old) => {
        if (Array.isArray(old)) {
          return old.filter((item) => item.id !== entityId) as T[]
        }
        return old
      }
    )
  }
}
