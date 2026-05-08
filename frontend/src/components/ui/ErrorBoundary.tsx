import { Component, type ReactNode } from 'react'
import { ErrorFallback } from '@/components/ui/ErrorFallback'

interface Props {
  children: ReactNode
  context?: string
}

interface State {
  hasError: boolean
  error: Error | null
}

export class ErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props)
    this.state = { hasError: false, error: null }
  }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error }
  }

  componentDidCatch(error: Error, errorInfo: React.ErrorInfo) {
    const context = this.props.context ?? 'unknown'
    // eslint-disable-next-line no-console
    console.error(`[ErrorBoundary:${context}]`, error, errorInfo)
  }

  handleReset = () => {
    this.setState({ hasError: false, error: null })
  }

  render() {
    if (this.state.hasError) {
      return (
        <ErrorFallback
          error={this.state.error}
          context={this.props.context}
          onReset={this.handleReset}
        />
      )
    }

    return this.props.children
  }
}
