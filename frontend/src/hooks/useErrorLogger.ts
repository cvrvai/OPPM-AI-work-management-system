import { useCallback } from 'react'

interface ErrorInfo {
  error: Error
  context?: string
  componentStack?: string
}

export function useErrorLogger() {
  const logError = useCallback((info: ErrorInfo) => {
    const prefix = info.context ? `[${info.context}]` : '[App]'
    // eslint-disable-next-line no-console
    console.error(`${prefix} Uncaught error:`, info.error)
    if (info.componentStack) {
      // eslint-disable-next-line no-console
      console.error(`${prefix} Component stack:`, info.componentStack)
    }
    // Future: send to Sentry / LogRocket / custom endpoint
    // sendToSentry(info.error, { context: info.context, componentStack: info.componentStack })
  }, [])

  return { logError }
}
