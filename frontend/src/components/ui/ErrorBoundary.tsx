import { Component, type ErrorInfo, type ReactNode } from 'react'
import { ErrorBoundaryFallback } from '../../lib/i18n/ErrorBoundaryFallback'

interface ErrorBoundaryProps {
  children: ReactNode
  fallback?: ReactNode
}

interface ErrorBoundaryState {
  hasError: boolean
  error: Error | null
}

/**
 * Top-level error boundary. Prevents a render-time exception in any subtree from
 * blanking the entire SPA, showing a recoverable fallback instead. Wrap route
 * content (and other risky subtrees such as the Mol* viewer) with this.
 */
export class ErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  state: ErrorBoundaryState = { hasError: false, error: null }

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { hasError: true, error }
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    // Surfaced to the console for now; wire to an error-reporting service later.
    console.error('Unhandled UI error:', error, info.componentStack)
  }

  handleReset = () => {
    this.setState({ hasError: false, error: null })
  }

  render() {
    if (!this.state.hasError) {
      return this.props.children
    }

    if (this.props.fallback) {
      return this.props.fallback
    }

    return (
      <ErrorBoundaryFallback message={this.state.error?.message} onReset={this.handleReset} />
    )
  }
}
