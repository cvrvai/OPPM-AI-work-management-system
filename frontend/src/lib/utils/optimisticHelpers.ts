import type { QueryClient } from '@tanstack/react-query'

/**
 * Shared optimistic update helpers.
 * These utilities make it easy to update cache entries before
 * the server confirms the mutation, then roll back on error.
 */

interface OptimisticContext<T> {
  previous: T | undefined
}

/**
 * Update a single entity in a list cache by matching its id.
 */
export function optimisticUpdateInList<T extends { id: string }>(
  queryClient: QueryClient,
  queryKey: unknown[],
  updatedItem: Partial<T> & { id: string }
): OptimisticContext<T[]> {
  const previous = queryClient.getQueryData<T[]>(queryKey)
  if (previous) {
    queryClient.setQueryData<T[]>(queryKey, (old) =>
      old?.map((item) =>
        item.id === updatedItem.id ? { ...item, ...updatedItem } : item
      ) ?? old
    )
  }
  return { previous }
}

/**
 * Update a single entity in an object cache.
 */
export function optimisticUpdateObject<T extends Record<string, unknown>>(
  queryClient: QueryClient,
  queryKey: unknown[],
  updatedFields: Partial<T>
): OptimisticContext<T> {
  const previous = queryClient.getQueryData<T>(queryKey)
  if (previous) {
    queryClient.setQueryData<T>(queryKey, { ...previous, ...updatedFields })
  }
  return { previous }
}

/**
 * Rollback helper — restores the previous cache value on mutation error.
 */
export function rollbackOnError<T>(
  queryClient: QueryClient,
  queryKey: unknown[],
  context: OptimisticContext<T> | undefined
) {
  if (context?.previous !== undefined) {
    queryClient.setQueryData(queryKey, context.previous)
  }
}
