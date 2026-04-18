/**
 * ProcessButton.jsx — Submit button with loading spinner animation.
 */

export default function ProcessButton({ loading, disabled, onClick }) {
  return (
    <div className="process-section">
      <button
        id="process-btn"
        className={`process-btn ${loading ? 'loading' : ''}`}
        onClick={onClick}
        disabled={disabled || loading}
        aria-busy={loading}
        type="button"
      >
        {loading ? (
          <>
            <span className="spinner" aria-hidden="true" />
            Processing timesheet…
          </>
        ) : (
          <>
            <span aria-hidden="true">⚡</span>
            Extract Timesheet Data
          </>
        )}
      </button>
    </div>
  );
}
