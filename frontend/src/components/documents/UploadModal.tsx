/**
 * src/components/documents/UploadModal.tsx
 * Drag-and-drop PDF uploader with size bounds checking, format validation, and force re-index option.
 * Styled with Claude paper aesthetic.
 */

import React, { useRef, useState } from 'react';
import { UploadCloud, FileText, Check, AlertCircle, Info, RefreshCw } from 'lucide-react';
import { Modal } from '../ui/Modal';
import { Button } from '../ui/Button';
import { DocumentUploadResponse } from '../../types/amcrag';
import { formatBytes } from '../../utils/formatters';

export interface UploadModalProps {
  isOpen: boolean;
  onClose: () => void;
  onUpload: (file: File, force: boolean) => Promise<DocumentUploadResponse>;
  isUploading: boolean;
}

const MAX_FILE_SIZE = 100 * 1024 * 1024; // 100 MB bound matching backend

export const UploadModal: React.FC<UploadModalProps> = ({
  isOpen,
  onClose,
  onUpload,
  isUploading,
}) => {
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [forceReindex, setForceReindex] = useState<boolean>(false);
  const [dragOver, setDragOver] = useState<boolean>(false);
  const [clientError, setClientError] = useState<string | null>(null);
  const [uploadResult, setUploadResult] = useState<DocumentUploadResponse | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const resetState = () => {
    setSelectedFile(null);
    setForceReindex(false);
    setClientError(null);
    setUploadResult(null);
  };

  const handleClose = () => {
    if (!isUploading) {
      resetState();
      onClose();
    }
  };

  const validateAndSetFile = (file: File) => {
    setClientError(null);
    setUploadResult(null);

    if (!file.name.toLowerCase().endsWith('.pdf')) {
      setClientError('Invalid file type: AMCRAG currently accepts PDF documents (.pdf) only.');
      return;
    }

    if (file.size > MAX_FILE_SIZE) {
      setClientError(`File too large: ${formatBytes(file.size)} exceeds maximum allowable limit of 100 MB.`);
      return;
    }

    if (file.size === 0) {
      setClientError('Selected file is empty (0 bytes).');
      return;
    }

    setSelectedFile(file);
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      validateAndSetFile(e.target.files[0]);
    }
  };

  const handleDrop = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setDragOver(false);
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      validateAndSetFile(e.dataTransfer.files[0]);
    }
  };

  const handleSubmit = async () => {
    if (!selectedFile) return;
    try {
      const res = await onUpload(selectedFile, forceReindex);
      setUploadResult(res);
    } catch (err: any) {
      setClientError(err.message || 'Document upload and indexing failed.');
    }
  };

  return (
    <Modal isOpen={isOpen} onClose={handleClose} title="Ingest PDF Document" maxWidth="520px">
      <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
        {/* Upload Result Notification */}
        {uploadResult ? (
          <div
            style={{
              padding: '16px',
              borderRadius: 'var(--radius-md)',
              background: 'var(--bg-100)',
              border: `var(--border-w) solid ${
                uploadResult.status === 'cached'
                  ? 'var(--border-200)'
                  : 'rgba(23, 163, 74, 0.3)'
              }`,
              display: 'flex',
              flexDirection: 'column',
              gap: '12px',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
              {uploadResult.status === 'cached' ? (
                <Info size={22} style={{ color: 'var(--brand-clay)' }} />
              ) : (
                <Check size={22} strokeWidth={2.5} style={{ color: 'var(--success)' }} />
              )}
              <div>
                <div style={{ fontWeight: 500, color: 'var(--text-100)', fontSize: '14.5px' }}>
                  {uploadResult.status === 'cached'
                    ? 'Document Already Cached'
                    : 'Document Indexed Successfully'}
                </div>
                <div style={{ fontSize: '13px', color: 'var(--text-300)' }}>
                  {uploadResult.message}
                </div>
              </div>
            </div>

            <div
              style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(3, 1fr)',
                gap: '8px',
                background: 'var(--bg-300)',
                padding: '10px',
                borderRadius: 'var(--radius-md)',
                fontSize: '12px',
                textAlign: 'center',
              }}
            >
              <div>
                <span style={{ color: 'var(--text-300)', display: 'block' }}>Pages</span>
                <strong style={{ color: 'var(--text-100)', fontSize: '15px' }}>{uploadResult.page_count}</strong>
              </div>
              <div>
                <span style={{ color: 'var(--text-300)', display: 'block' }}>Text Chunks</span>
                <strong style={{ color: 'var(--text-100)', fontSize: '15px' }}>{uploadResult.chunk_count}</strong>
              </div>
              <div>
                <span style={{ color: 'var(--text-300)', display: 'block' }}>150 DPI Images</span>
                <strong style={{ color: 'var(--text-100)', fontSize: '15px' }}>{uploadResult.image_count}</strong>
              </div>
            </div>

            <Button variant="secondary" size="sm" onClick={resetState} style={{ alignSelf: 'flex-start' }}>
              Upload Another Document
            </Button>
          </div>
        ) : (
          <>
            {/* Drag & Drop Target */}
            <div
              onDragOver={(e) => {
                e.preventDefault();
                setDragOver(true);
              }}
              onDragLeave={() => setDragOver(false)}
              onDrop={handleDrop}
              onClick={() => fileInputRef.current?.click()}
              style={{
                border: `1.5px dashed ${dragOver ? 'var(--brand)' : 'var(--border-300)'}`,
                borderRadius: 'var(--radius-lg)',
                padding: '2rem 1.5rem',
                textAlign: 'center',
                cursor: 'pointer',
                background: dragOver ? 'var(--brand-tint)' : 'var(--bg-100)',
                transition: 'all var(--dur-base) ease',
              }}
            >
              <input
                ref={fileInputRef}
                type="file"
                accept=".pdf,application/pdf"
                style={{ display: 'none' }}
                onChange={handleFileChange}
              />
              <UploadCloud
                size={36}
                style={{
                  color: dragOver ? 'var(--brand)' : 'var(--text-300)',
                  margin: '0 auto 8px auto',
                }}
              />
              <div style={{ fontWeight: 500, color: 'var(--text-100)', marginBottom: '4px', fontSize: '14.5px' }}>
                Select a PDF file or drag it here
              </div>
              <div style={{ fontSize: '12.5px', color: 'var(--text-300)' }}>
                Accepts PDF files up to 100 MB. Extracts text, tables, and renders 150 DPI page PNGs for ColPali.
              </div>
            </div>

            {/* Selected File Details */}
            {selectedFile && (
              <div
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  padding: '10px 14px',
                  borderRadius: 'var(--radius-md)',
                  background: 'var(--bg-100)',
                  border: 'var(--border-w) solid var(--border-200)',
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                  <FileText size={18} style={{ color: 'var(--brand-clay)' }} />
                  <div>
                    <div style={{ fontSize: '13.5px', fontWeight: 500, color: 'var(--text-100)' }}>
                      {selectedFile.name}
                    </div>
                    <div style={{ fontSize: '12px', color: 'var(--text-300)' }}>
                      {formatBytes(selectedFile.size)}
                    </div>
                  </div>
                </div>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={(e) => {
                    e.stopPropagation();
                    setSelectedFile(null);
                  }}
                >
                  Change
                </Button>
              </div>
            )}

            {/* Force Re-index Toggle */}
            <label
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '8px',
                fontSize: '13px',
                color: 'var(--text-200)',
                cursor: 'pointer',
              }}
            >
              <input
                type="checkbox"
                checked={forceReindex}
                onChange={(e) => setForceReindex(e.target.checked)}
                style={{ accentColor: 'var(--brand)', width: '16px', height: '16px' }}
              />
              <span>
                <strong>Force Re-index:</strong> Overwrite cache and re-extract text chunks and page images.
              </span>
            </label>

            {/* Error Message */}
            {clientError && (
              <div
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '8px',
                  padding: '10px 14px',
                  borderRadius: 'var(--radius-md)',
                  background: 'rgba(181, 51, 51, 0.08)',
                  border: 'var(--border-w) solid rgba(181, 51, 51, 0.3)',
                  color: 'var(--danger)',
                  fontSize: '13px',
                }}
              >
                <AlertCircle size={15} />
                <span>{clientError}</span>
              </div>
            )}

            {/* Submit Action */}
            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '8px', marginTop: '4px', paddingTop: '10px', borderTop: 'var(--border-w) solid var(--border-100)' }}>
              <Button variant="secondary" onClick={handleClose} disabled={isUploading}>
                Cancel
              </Button>
              <Button
                variant="primary"
                onClick={handleSubmit}
                disabled={!selectedFile || isUploading}
                isLoading={isUploading}
                icon={<RefreshCw size={14} />}
              >
                {isUploading ? 'Extracting & Indexing…' : 'Upload & Process'}
              </Button>
            </div>
          </>
        )}
      </div>
    </Modal>
  );
};
