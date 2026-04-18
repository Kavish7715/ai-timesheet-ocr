/**
 * App.jsx — Root component for the AI Timesheet Automation System.
 */

import { useState, useCallback } from 'react';
import axios from 'axios';
import './App.css';
import UploadZone from './components/UploadZone';
import ImagePreview from './components/ImagePreview';
import ProcessButton from './components/ProcessButton';
import ResultDisplay from './components/ResultDisplay';

const API_BASE = import.meta.env.VITE_API_URL || '';
const REQUEST_TIMEOUT_MS = Number(import.meta.env.VITE_REQUEST_TIMEOUT_MS || 120000); // 2 min timeout for image upload and processing

export default function App() {
  const [file, setFile] = useState(null);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [rawText, setRawText] = useState(null);
  const [error, setError] = useState(null);

  // Database upload state
  const [submitLoading, setSubmitLoading] = useState(false);
  const [submitResult, setSubmitResult] = useState(null);
  const [submitError, setSubmitError] = useState(null);

  const handleFileSelect = useCallback((selectedFile) => {
    setFile(selectedFile);
    setResult(null);
    setRawText(null);
    setError(null);
    setSubmitResult(null);
    setSubmitError(null);
  }, []);

  const handleRemoveFile = useCallback(() => {
    setFile(null);
    setResult(null);
    setRawText(null);
    setError(null);
    setSubmitResult(null);
    setSubmitError(null);
  }, []);

  const handleProcess = async () => {
    if (!file) return;

    setLoading(true);
    setResult(null);
    setRawText(null);
    setError(null);

    const formData = new FormData();
    formData.append('file', file);

    try {
      const response = await axios.post(`${API_BASE}/upload-timesheet`, formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
        timeout: REQUEST_TIMEOUT_MS,
      });

      const data = response.data;
      setResult(data.result);
      setRawText(data.raw_text || null);
    } catch (err) {
      const msg = err.code === 'ECONNABORTED'
        ? `Processing timed out after ${Math.round(REQUEST_TIMEOUT_MS / 1000)}s. The server might be taking too long to process the image; please try again.`
        : err.response?.data?.detail ||
          err.message ||
          'An unexpected error occurred. Make sure the backend server is running.';
      setError(msg);
    } finally {
      setLoading(false);
    }
  };

  const handleSubmit = async () => {
    if (!result || !result.entries?.length) return;

    setSubmitLoading(true);
    setSubmitResult(null);
    setSubmitError(null);

    try {
      const response = await axios.post(`${API_BASE}/submit-timesheet`, result, {
        headers: { 'Content-Type': 'application/json' },
        timeout: 180000, // 3 min timeout (retries + cold-start)
      });
      setSubmitResult(response.data);
    } catch (err) {
      const msg = err.code === 'ECONNABORTED'
        ? 'Upload timed out. The external server may be waking up — please try again in 30-45 seconds.'
        : err.response?.data?.detail ||
          err.message ||
          'Failed to upload timesheet data to the database.';
      setSubmitError(msg);
    } finally {
      setSubmitLoading(false);
    }
  };

  const showResults = result !== null || error !== null;

  return (
    <div className="app">
      {/* ── Header ── */}
      <header className="app-header">
        <div className="header-logo">
          <div className="logo-icon">⏱️</div>
          <div className="logo-text">
            <h1>AI Timesheet Automation</h1>
            <span>OCR + AI Powered Extraction</span>
          </div>
        </div>
        <div className="header-badge">
          <span className="badge-dot" />
          System Online
        </div>
      </header>

      {/* ── Main ── */}
      <main className="app-main" id="main-content">
        {/* Hero */}
        <section className="hero-section">
          <h2>Extract Work Hours from<br />Timesheet Screenshots</h2>
          <p>
            Upload any timesheet screenshot — from Clockify, Toggl, Jira, or custom tools.
            Our AI model extracts structured date, login, logout, and total hours automatically.
          </p>
        </section>

        {/* Upload */}
        <UploadZone onFileSelect={handleFileSelect} hasFile={!!file} />

        {/* Preview */}
        {file && (
          <ImagePreview file={file} onRemove={handleRemoveFile} />
        )}

        {/* Process button */}
        {file && (
          <ProcessButton
            loading={loading}
            disabled={!file}
            onClick={handleProcess}
          />
        )}

        {/* Results / Error */}
        {showResults && (
          <ResultDisplay
            result={result}
            rawText={rawText}
            error={error}
            onSubmit={handleSubmit}
            submitLoading={submitLoading}
            submitResult={submitResult}
            submitError={submitError}
          />
        )}
      </main>

      {/* ── Footer ── */}
      <footer className="app-footer">
        <p>
          AI Timesheet Automation System &nbsp;·&nbsp;
          EasyOCR + Gemini 2.5 Flash &nbsp;·&nbsp;
          FastAPI + React
        </p>
      </footer>
    </div>
  );
}
