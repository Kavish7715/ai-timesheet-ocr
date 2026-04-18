/**
 * UploadZone.jsx — Drag-and-drop file upload component.
 * Accepts images via drag-drop or click-to-browse.
 */

import { useRef, useState, useCallback } from 'react';

const ACCEPTED_TYPES = ['image/jpeg', 'image/png', 'image/webp', 'image/bmp', 'image/tiff'];
const ACCEPTED_EXTS = '.jpg,.jpeg,.png,.webp,.bmp,.tif,.tiff';

export default function UploadZone({ onFileSelect, hasFile }) {
  const inputRef = useRef(null);
  const [isDragOver, setIsDragOver] = useState(false);

  const handleFile = useCallback((file) => {
    if (!file) return;
    if (!ACCEPTED_TYPES.includes(file.type)) {
      alert(`Unsupported file type: ${file.type}\nPlease upload a JPEG, PNG, WEBP, BMP, or TIFF image.`);
      return;
    }
    onFileSelect(file);
  }, [onFileSelect]);

  const handleDragOver = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragOver(true);
  };

  const handleDragLeave = (e) => {
    e.preventDefault();
    setIsDragOver(false);
  };

  const handleDrop = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragOver(false);
    const file = e.dataTransfer.files?.[0];
    handleFile(file);
  };

  const handleInputChange = (e) => {
    const file = e.target.files?.[0];
    handleFile(file);
    e.target.value = ''; // reset so same file can be re-selected
  };

  const openBrowser = () => inputRef.current?.click();

  return (
    <div className="upload-section">
      <div
        id="upload-zone"
        className={`upload-zone ${isDragOver ? 'drag-over' : ''} ${hasFile ? 'has-file' : ''}`}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        onClick={openBrowser}
        role="button"
        tabIndex={0}
        onKeyDown={(e) => e.key === 'Enter' && openBrowser()}
        aria-label="Upload timesheet image"
      >
        <input
          ref={inputRef}
          type="file"
          accept={ACCEPTED_EXTS}
          onChange={handleInputChange}
          style={{ display: 'none' }}
          id="file-input"
          aria-hidden="true"
        />

        <span className="upload-icon">
          {isDragOver ? '📂' : hasFile ? '✅' : '📁'}
        </span>

        <h3>
          {isDragOver
            ? 'Release to upload'
            : hasFile
            ? 'Image selected — click to change'
            : 'Drop your timesheet screenshot here'}
        </h3>

        <p>
          {hasFile
            ? 'Click anywhere to replace the image'
            : 'Drag & drop or click to browse your device'}
        </p>

        <div className="upload-formats">
          {['PNG', 'JPEG', 'WEBP', 'BMP', 'TIFF'].map((fmt) => (
            <span key={fmt} className="format-tag">{fmt}</span>
          ))}
        </div>

        {!hasFile && (
          <button
            className="upload-browse-btn"
            onClick={(e) => { e.stopPropagation(); openBrowser(); }}
            type="button"
            id="browse-btn"
          >
            📎 Browse Files
          </button>
        )}
      </div>
    </div>
  );
}
