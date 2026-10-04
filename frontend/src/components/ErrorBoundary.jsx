import React from "react";

/**
 * Error boundary that catches render crashes and shows a friendly reload button.
 * Does NOT lose form data or queued photos — those live in parent state which
 * survives the boundary reset.
 */
export class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false };
  }

  static getDerivedStateFromError() {
    return { hasError: true };
  }

  componentDidCatch(error, info) {
    console.error("ErrorBoundary caught:", error, info);
  }

  handleReload = () => {
    this.setState({ hasError: false });
    if (this.props.onReload) this.props.onReload();
    else window.location.reload();
  };

  render() {
    if (this.state.hasError) {
      return (
        <div className="flex flex-col items-center justify-center min-h-[60vh] gap-4 p-6 text-center">
          <div className="text-5xl">🔧</div>
          <h2 className="text-lg font-bold text-slate-800">Something went wrong</h2>
          <p className="text-sm text-slate-500 max-w-sm">
            The page hit an error. Your data is safe. Tap to reload and try again.
          </p>
          <button
            onClick={this.handleReload}
            className="px-5 py-2.5 rounded-lg bg-emerald-600 text-white font-semibold text-sm hover:bg-emerald-700 transition-colors"
          >
            Reload
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}
