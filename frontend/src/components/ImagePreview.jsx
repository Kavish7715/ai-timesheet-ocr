/**
 * ImagePreview.jsx — Shows a thumbnail of the selected file.
 * Provides a "remove" button to clear the selection.
 */

import { useMemo } from 'react';

export default function ImagePreview({ file, onRemove }) {
  // Create an object URL blob preview (memoised per file reference)
  const previewUrl = useMemo(() => {
    if (!file) return null;
    return URL.createObjectURL(file);
  }, [file]);

  const formatSize = (bytes) => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
  };

  if (!file || !previewUrl) return null;

  return (
    <div className="preview-section">
      <div className="preview-card">
        <div className="preview-header">
          <h3>Preview</h3>
          <button
            id="remove-image-btn"
            className="btn-icon"
            onClick={onRemove}
            title="Remove image"
            aria-label="Remove selected image"
          >
            ✕
          </button>
        </div>

        <div className="preview-image-wrap">
          <img
            src={previewUrl}
            alt={`Preview of ${file.name}`}
            id="preview-img"
          />
        </div>

        <div className="preview-footer">
          <span>📄</span>
          <span className="file-name" title={file.name}>{file.name}</span>
          <span style={{ marginLeft: 'auto', color: 'var(--text-muted)' }}>
            {formatSize(file.size)}
          </span>
        </div>
      </div>
    </div>
  );
}
