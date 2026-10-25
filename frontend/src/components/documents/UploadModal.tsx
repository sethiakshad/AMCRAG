/**
 * src/components/documents/UploadModal.tsx
 * Drag-and-drop PDF uploader with size bounds checking, format validation, and force re-index option.
 */

import React, { useRef, useState } from 'react';
import { UploadCloud, FileText, CheckCircle2, AlertCircle, Info, RefreshCw } from 'lucide-react';
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
    <Modal isOpen={isOpen} onClose={handleClose} title="Ingest PDF Document" maxWidth="560px">
      <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
        {/* Upload Result Notification */}
        {uploadResult ? (
          <div
            style={{
              padding: '1.25rem',
              borderRadius: '10px',
              background: uploadResult.status === 'cached'
                ? 'rgba(99, 102, 241, 0.1)'
                : 'rgba(16, 185, 129, 0.1)',
              border: `1px solid ${
                uploadResult.status === 'cached'
                  ? 'rgba(99, 102, 241, 0.3)'
                  : 'rgba(16, 185, 129, 0.3)'
              }`,
              display: 'flex',
              flexDirection: 'column',
              gap: '0.75rem',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
              {uploadResult.status === 'cached' ? (
                <Info size={24} style={{ color: '#818cf8' }} />
              ) : (
                <CheckCircle2 size={24} style={{ color: '#10b981' }} />
              )}
              <div>
                <div style={{ fontWeight: 600, color: '#ffffff' }}>
                  {uploadResult.status === 'cached'
                    ? 'Document Already Cached'
                    : 'Document Indexed Successfully'}
                </div>
                <div style={{ fontSize: '0.8125rem', color: 'var(--text-secondary)' }}>
                  {uploadResult.message}
                </div>
              </div>
            </div>

            <div
              style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(3, 1fr)',
                gap: '8px',
                background: 'rgba(0, 0, 0, 0.25)',
                padding: '0.75rem',
                borderRadius: '8px',
                fontSize: '0.75rem',
                textAlign: 'center',
              }}
            >
              <div>
                <span style={{ color: 'var(--text-muted)', display: 'block' }}>Pages</span>
                <strong style={{ color: '#ffffff', fontSize: '1rem' }}>{uploadResult.page_count}</strong>
              </div>
              <div>
                <span style={{ color: 'var(--text-muted)', display: 'block' }}>Text Chunks</span>
                <strong style={{ color: '#ffffff', fontSize: '1rem' }}>{uploadResult.chunk_count}</strong>
              </div>
              <div>
                <span style={{ color: 'var(--text-muted)', display: 'block' }}>150 DPI Images</span>
                <strong style={{ color: '#ffffff', fontSize: '1rem' }}>{uploadResult.image_count}</strong>
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
                border: `2px dashed ${dragOver ? 'var(--brand-primary)' : 'var(--border-medium)'}`,
                borderRadius: '12px',
                padding: '2.5rem 1.5rem',
                textAlign: 'center',
                cursor: 'pointer',
                background: dragOver ? 'rgba(99, 102, 241, 0.08)' : 'rgba(255, 255, 255, 0.02)',
                transition: 'all 0.2s ease',
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
                size={40}
                style={{
                  color: dragOver ? 'var(--brand-primary)' : 'var(--text-muted)',
                  margin: '0 auto 0.75rem auto',
                }}
              />
              <div style={{ fontWeight: 600, color: '#ffffff', marginBottom: '4px' }}>
                Click to browse or drop your PDF here
              </div>
              <div style={{ fontSize: '0.8125rem', color: 'var(--text-muted)' }}>
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
                  padding: '0.75rem 1rem',
                  borderRadius: '8px',
                  background: 'rgba(99, 102, 241, 0.1)',
                  border: '1px solid rgba(99, 102, 241, 0.3)',
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                  <FileText size={20} style={{ color: '#818cf8' }} />
                  <div>
                    <div style={{ fontSize: '0.875rem', fontWeight: 600, color: '#ffffff' }}>
                      {selectedFile.name}
                    </div>
                    <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>
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
                fontSize: '0.8125rem',
                color: 'var(--text-secondary)',
                cursor: 'pointer',
              }}
            >
              <input
                type="checkbox"
                checked={forceReindex}
                onChange={(e) => setForceReindex(e.target.checked)}
                style={{ accentColor: 'var(--brand-primary)', width: '16px', height: '16px' }}
              />
              <span>
                <strong>Force Re-index:</strong> Overwrite cache and re-extract text chunks and page images even if already uploaded.
              </span>
            </label>

            {/* Error Message */}
            {clientError && (
              <div
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '8px',
                  padding: '0.75rem',
                  borderRadius: '8px',
                  background: 'rgba(244, 63, 94, 0.1)',
                  border: '1px solid rgba(244, 63, 94, 0.3)',
                  color: '#fb7185',
                  fontSize: '0.8125rem',
                }}
              >
                <AlertCircle size={16} />
                <span>{clientError}</span>
              </div>
            )}

            {/* Submit Action */}
            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.75rem', marginTop: '0.5rem' }}>
              <Button variant="secondary" onClick={handleClose} disabled={isUploading}>
                Cancel
              </Button>
              <Button
                variant="primary"
                onClick={handleSubmit}
                disabled={!selectedFile || isUploading}
                isLoading={isUploading}
                icon={<RefreshCw size={15} />}
              >
                {isUploading ? 'Extracting & Indexing...' : 'Upload & Process'}
              </Button>
            </div>
          </>
        )}
      </div>
    </Modal>
  );
};
