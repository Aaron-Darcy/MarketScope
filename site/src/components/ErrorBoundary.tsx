import { Component, type ErrorInfo, type ReactNode } from 'react';

interface State {
  readonly error: Error | null;
}

/** Shows a failed load or an inconsistent export plainly, rather than a blank page. */
export class ErrorBoundary extends Component<{ readonly children: ReactNode }, State> {
  override state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  override componentDidCatch(error: Error, info: ErrorInfo) {
    console.error(error, info.componentStack);
  }

  override render() {
    const { error } = this.state;
    if (!error) return this.props.children;
    return (
      <div className="container error-panel" role="alert">
        <h1>The data could not be shown</h1>
        <p>The page stopped rather than show figures it could not vouch for. The cause was:</p>
        <pre>
          {error.name}: {error.message}
        </pre>
      </div>
    );
  }
}
