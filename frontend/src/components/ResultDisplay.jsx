/**
 * ResultDisplay.jsx — Shows structured parsed timesheet data.
 * Features:
 *   - Entry cards (date, login, logout, hours, confidence)
 *   - Collapsible raw JSON view
 *   - Collapsible OCR raw text view
 *   - Copy-to-clipboard button
 *   - Parse source badge (AI vs Regex)
 *   - Upload to Database button with status feedback
 */

import { useState } from 'react';

function ConfidenceBadge({ confidence }) {
  const cls = `confidence-badge confidence-${confidence || 'low'}`;
  const icons = { high: '✓', medium: '~', low: '?' };
  return (
    <span className={cls}>
      {icons[confidence] || '?'} {confidence || 'unknown'}
    </span>
  );
}

function EntryCard({ entry, index }) {
  const {
    date = null,
    login = null,
    logout = null,
    hours = null,
    confidence = 'low',
  } = entry;

  return (
    <div className="entry-card" id={`entry-card-${index}`}>
      <div className="entry-date">
        {date ? `📅 ${date}` : '📅 Date unknown'}
      </div>

      <div className="entry-times">
        <div className="time-chip">
          <label>Login</label>
          <span>{login || '—'}</span>
        </div>
        <span className="time-arrow">→</span>
        <div className="time-chip">
          <label>Logout</label>
          <span>{logout || '—'}</span>
        </div>
      </div>

      <div className="entry-hours">
        <div>
          <span className="hours-value">
            {hours !== null ? hours : '—'}
          </span>
          <span className="hours-label"> hrs</span>
        </div>
        <ConfidenceBadge confidence={confidence} />
      </div>
    </div>
  );
}

export default function ResultDisplay({
  result,
  rawText,
  error,
  onSubmit,
  submitLoading = false,
  submitResult = null,
  submitError = null,
}) {
  const [jsonExpanded, setJsonExpanded] = useState(false);
  const [ocrExpanded, setOcrExpanded] = useState(false);
  const [copied, setCopied] = useState(false);

  if (error) {
    return (
      <div className="result-section">
        <div className="error-card" id="error-display">
          <span className="error-icon">⚠️</span>
          <div className="error-content">
            <h4>Processing Failed</h4>
            <p>{error}</p>
          </div>
        </div>
      </div>
    );
  }

  if (!result) return null;

  const { entries = [], total_entries = 0, parse_source = 'unknown', employee_name = 'Unknown' } = result;

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(JSON.stringify(result, null, 2));
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // fallback for older browsers
      const el = document.createElement('textarea');
      el.value = JSON.stringify(result, null, 2);
      document.body.appendChild(el);
      el.select();
      document.execCommand('copy');
      document.body.removeChild(el);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  const hasEntries = entries.length > 0;
  const alreadyUploaded = submitResult?.success === true;

  return (
    <div className="result-section">
      <div className="result-card" id="result-card">

        {/* Header */}
        <div className="result-header">
          <div className="result-title">
            <span>📊</span>
            <h3>Extraction Results</h3>
            {employee_name && employee_name !== 'Unknown' && (
              <span className="badge" style={{ marginLeft: '12px', background: 'var(--bg-card-hover)', color: 'var(--text-primary)' }}>
                👤 {employee_name}
              </span>
            )}
          </div>

          <div className="result-meta">
            {parse_source === 'gemini-vision' && (
              <span className="badge badge-ai" title="Extracted directly from image using Google Gemini 2.5 Flash Vision">
                🤖 Gemini Vision
              </span>
            )}
            {parse_source === 'gemini-text' && (
              <span className="badge badge-ai" title="Extracted from OCR text using Google Gemini 2.5 Flash">
                🤖 Gemini Text
              </span>
            )}
            {(parse_source === 'regex' || parse_source === 'unknown') && (
              <span className="badge badge-regex" title="Extracted using rule-based pattern matching (Fallback)">
                🔤 Regex Parse
              </span>
            )}
            <span className="badge badge-entries">
              {total_entries} {total_entries === 1 ? 'Entry' : 'Entries'}
            </span>
            <button
              id="copy-btn"
              className={`copy-btn ${copied ? 'copied' : ''}`}
              onClick={handleCopy}
              aria-label="Copy JSON to clipboard"
            >
              {copied ? '✓ Copied!' : '📋 Copy JSON'}
            </button>
          </div>
        </div>

        {/* Entry cards grid */}
        {entries.length > 0 ? (
          <div className="entries-grid">
            {entries.map((entry, i) => (
              <EntryCard key={i} entry={entry} index={i} />
            ))}
          </div>
        ) : (
          <div style={{ padding: '32px', textAlign: 'center', color: 'var(--text-muted)' }}>
            <span style={{ fontSize: '36px', display: 'block', marginBottom: '12px' }}>🔍</span>
            No timesheet entries could be extracted. Try a clearer image.
          </div>
        )}

        {/* ── Upload to Database ─────────────────────────────── */}
        {hasEntries && (
          <div className="submit-section">
            {/* Success state */}
            {alreadyUploaded ? (
              <div className="submit-success" id="submit-success">
                <span className="submit-success-icon">✅</span>
                <div className="submit-success-content">
                  <h4>Uploaded Successfully</h4>
                  <p>
                    {submitResult?.api_response?.total_entries ?? total_entries}{' '}
                    {(submitResult?.api_response?.total_entries ?? total_entries) === 1 ? 'entry' : 'entries'} for
                    <strong> {employee_name}</strong> sent to the database.
                  </p>
                </div>
              </div>
            ) : (
              <>
                <button
                  id="submit-btn"
                  className={`submit-btn ${submitLoading ? 'loading' : ''}`}
                  onClick={onSubmit}
                  disabled={submitLoading}
                >
                  {submitLoading ? (
                    <>
                      <span className="spinner" />
                      Uploading to Database…
                    </>
                  ) : (
                    <>
                      🚀 Upload to Database
                    </>
                  )}
                </button>
              </>
            )}

            {/* Error state */}
            {submitError && (
              <div className="submit-error" id="submit-error">
                <span className="error-icon">⚠️</span>
                <div className="error-content">
                  <h4>Upload Failed</h4>
                  <p>{submitError}</p>
                </div>
              </div>
            )}
          </div>
        )}

        {/* Raw JSON toggle */}
        <div className="raw-json-section">
          <button
            id="raw-json-toggle"
            className="raw-json-toggle"
            onClick={() => setJsonExpanded(!jsonExpanded)}
            aria-expanded={jsonExpanded}
          >
            <span>{jsonExpanded ? '▲' : '▼'}  View Raw JSON</span>
            <span style={{ fontSize: '10px', opacity: 0.5 }}>
              {JSON.stringify(result).length} chars
            </span>
          </button>

          {jsonExpanded && (
            <div className="json-pre" id="json-output">
              <code>{JSON.stringify(result, null, 2)}</code>
            </div>
          )}
        </div>

        {/* OCR text toggle */}
        {rawText && (
          <div className="ocr-text-section">
            <button
              id="ocr-text-toggle"
              className="ocr-text-toggle"
              onClick={() => setOcrExpanded(!ocrExpanded)}
              aria-expanded={ocrExpanded}
            >
              <span>{ocrExpanded ? '▲' : '▼'}  View Raw OCR Text</span>
              <span style={{ fontSize: '10px', opacity: 0.5 }}>
                {rawText.length} chars
              </span>
            </button>

            {ocrExpanded && (
              <div className="ocr-text-pre" id="ocr-output">
                <code>{rawText}</code>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
