import { z } from 'zod'
import { api } from './client'

/**
 * Validated API wrapper.
 * Every response is parsed through a Zod schema at runtime.
 * If the server returns unexpected shapes, we catch it immediately
 * instead of letting it propagate as a runtime crash downstream.
 */
export const validatedApi = {
  get: <T extends z.ZodType>(path: string, schema: T): Promise<z.infer<T>> =>
    api.get<unknown>(path).then((data) => schema.parse(data)),

  post: <T extends z.ZodType>(path: string, data: unknown, schema: T): Promise<z.infer<T>> =>
    api.post<unknown>(path, data).then((res) => schema.parse(res)),

  put: <T extends z.ZodType>(path: string, data: unknown, schema: T): Promise<z.infer<T>> =>
    api.put<unknown>(path, data).then((res) => schema.parse(res)),

  patch: <T extends z.ZodType>(path: string, data: unknown, schema: T): Promise<z.infer<T>> =>
    api.patch<unknown>(path, data).then((res) => schema.parse(res)),

  delete: <T extends z.ZodType>(path: string, schema: T): Promise<z.infer<T>> =>
    api.delete<unknown>(path).then((res) => schema.parse(res)),
}
