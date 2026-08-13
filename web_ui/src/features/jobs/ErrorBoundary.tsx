import { Component } from 'react';
import type { ErrorInfo, ReactNode } from 'react';
import './Jobs.css';

interface Props {
  children?: ReactNode;
}

interface State {
  hasError: boolean;
  error: Error | null;
}

export class GlobalErrorBoundary extends Component<Props, State> {
  public state: State = {
    hasError: false,
    error: null
  };

  public static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  public componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error('Uncaught error:', error, errorInfo);
  }

  public render() {
    if (this.state.hasError) {
      return (
        <div className="card error-boundary-card" style={{ margin: 'var(--spacing-8)', borderColor: 'var(--color-error-text)' }}>
          <h2 style={{ color: 'var(--color-error-text)', marginBottom: 'var(--spacing-4)' }}>Something went wrong</h2>
          <div className="error-alert">
            {this.state.error?.message || 'Unknown error occurred.'}
          </div>
          <button 
            className="btn btn-primary"
            onClick={() => this.setState({ hasError: false, error: null })}
          >
            Try Again
          </button>
        </div>
      );
    }

    return this.props.children;
  }
}
