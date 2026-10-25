/**
 * src/App.tsx
 * Primary application layout and navigation shell adhering to Claude.ai:
 * - 288px Left sidebar with wordmark, "+ Start new chat", navigation, recent documents, and theme switcher.
 * - Minimal top header and full-stage reading layout.
 */

import React, { useState, useEffect } from 'react';
import {
  MessageSquare,
  BookOpen,
  FileCode,
  Sun,
  Moon,
  Plus,
  FileText,
} from 'lucide-react';
import { ChatWindow } from './components/chat/ChatWindow';
import { DocumentManager } from './components/documents/DocumentManager';
import { HealthIndicator } from './components/health/HealthIndicator';
import { useHealth } from './hooks/useHealth';
import { useDocuments } from './hooks/useDocuments';

// Geometric terracotta starburst mark
const StarburstIcon: React.FC<{ size?: number; className?: string }> = ({ size = 20, className = '' }) => (
  <svg
    width={size}
    height={size}
    viewBox="0 0 24 24"
    fill="currentColor"
    className={className}
    style={{ display: 'inline-block', verticalAlign: 'middle', color: 'var(--brand-clay)' }}
  >
    <path d="M12 2L13.8 8.2L20 6.5L16.2 11.5L22 14.5L15.8 16.5L17.5 22.5L12 18.5L6.5 22.5L8.2 16.5L2 14.5L7.8 11.5L4 6.5L10.2 8.2L12 2Z" />
  </svg>
);

export function App() {
  const [activeTab, setActiveTab] = useState<'chat' | 'documents'>('chat');
  const [preselectedDocId, setPreselectedDocId] = useState<string | null>(null);
  const [chatSessionId, setChatSessionId] = useState<number>(1);
  const [theme, setTheme] = useState<'light' | 'dark'>('light');

  const { health, isLoading: isHealthLoading, isOffline, checkHealth } = useHealth();
  const { allDocuments } = useDocuments();

  useEffect(() => {
    const currentTheme = (document.documentElement.getAttribute('data-theme') as 'light' | 'dark') || 'light';
    setTheme(currentTheme);
  }, []);

  const toggleTheme = () => {
    const nextTheme = theme === 'light' ? 'dark' : 'light';
    setTheme(nextTheme);
    document.documentElement.setAttribute('data-theme', nextTheme);
    localStorage.setItem('amcrag_theme', nextTheme);
  };

  const handleStartNewChat = () => {
    setPreselectedDocId(null);
    setActiveTab('chat');
    setChatSessionId((prev) => prev + 1);
  };

  const handleChatWithDoc = (docId: string) => {
    setPreselectedDocId(docId);
    setActiveTab('chat');
  };

  return (
    <div className="app-container">
      {/* 1. Left Sidebar (Claude Anatomy) */}
      <aside className="sidebar">
        {/* Brand Wordmark Row */}
        <div className="brand-word">
          <StarburstIcon size={22} />
          <span>AMCRAG</span>
          <span
            style={{
              fontSize: '11px',
              fontFamily: 'var(--font-mono)',
              padding: '1px 5px',
              borderRadius: '4px',
              background: 'var(--bg-300)',
              color: 'var(--text-300)',
              fontWeight: 500,
              marginLeft: '4px',
            }}
          >
            v1.0
          </span>
        </div>

        {/* Start New Chat Button */}
        <button
          onClick={handleStartNewChat}
          className="sb-row sb-new"
          title="Start a new chat session"
        >
          <div className="plus-icon">
            <Plus size={14} strokeWidth={2.5} />
          </div>
          <span>Start new chat</span>
        </button>

        {/* Main Navigation Rows */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '2px' }}>
          <button
            onClick={() => setActiveTab('chat')}
            className="sb-row"
            aria-current={activeTab === 'chat'}
          >
            <MessageSquare size={17} style={{ color: activeTab === 'chat' ? 'var(--brand)' : 'var(--text-300)' }} />
            <span>Ask & Chat</span>
          </button>

          <button
            onClick={() => setActiveTab('documents')}
            className="sb-row"
            aria-current={activeTab === 'documents'}
          >
            <BookOpen size={17} style={{ color: activeTab === 'documents' ? 'var(--brand)' : 'var(--text-300)' }} />
            <span>Knowledge Base</span>
            {allDocuments.length > 0 && (
              <span
                style={{
                  marginLeft: 'auto',
                  fontSize: '11px',
                  fontFamily: 'var(--font-mono)',
                  fontWeight: 500,
                  padding: '1px 6px',
                  borderRadius: 'var(--radius-full)',
                  background: activeTab === 'documents' ? 'var(--brand)' : 'var(--bg-300)',
                  color: activeTab === 'documents' ? 'var(--on-brand)' : 'var(--text-200)',
                }}
              >
                {allDocuments.length}
              </span>
            )}
          </button>
        </div>

        {/* Section: Recent Indexed Documents */}
        {allDocuments.length > 0 && (
          <div style={{ marginTop: '12px', flex: 1, overflowY: 'auto' }}>
            <div className="sb-label">Recent Documents</div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '2px' }}>
              {allDocuments.slice(0, 8).map((doc) => {
                const isSelected = preselectedDocId === doc.document_id;
                return (
                  <div
                    key={doc.document_id}
                    onClick={() => handleChatWithDoc(doc.document_id)}
                    className={`sb-doc-item ${isSelected ? 'active' : ''}`}
                    title={`Click to filter chat by ${doc.filename}`}
                  >
                    <FileText size={14} style={{ color: isSelected ? 'var(--brand)' : 'var(--text-300)', flexShrink: 0 }} />
                    <span style={{ overflow: 'hidden', textOverflow: 'ellipsis' }}>
                      {doc.filename}
                    </span>
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {/* Sidebar Footer */}
        <div className="sb-footer">
          {/* Health indicator button */}
          <div style={{ padding: '4px 6px' }}>
            <HealthIndicator
              health={health}
              isLoading={isHealthLoading}
              isOffline={isOffline}
              onRefresh={checkHealth}
            />
          </div>

          {/* Theme toggle row */}
          <button
            onClick={toggleTheme}
            className="sb-row"
            title="Toggle light and dark color scheme"
          >
            {theme === 'light' ? (
              <Moon size={16} style={{ color: 'var(--text-300)' }} />
            ) : (
              <Sun size={16} style={{ color: 'var(--text-300)' }} />
            )}
            <span>{theme === 'light' ? 'Dark mode' : 'Light mode'}</span>
          </button>

          {/* API Swagger Documentation link */}
          <a
            href="/docs"
            target="_blank"
            rel="noreferrer"
            className="sb-row"
            title="Open FastAPI Swagger OpenAPI Documentation (/docs)"
          >
            <FileCode size={16} style={{ color: 'var(--text-300)' }} />
            <span>API Documentation</span>
          </a>

          {/* GitHub Repository link */}
          <a
            href="https://github.com/sethiakshad/AMCRAG"
            target="_blank"
            rel="noreferrer"
            className="sb-row"
            title="AMCRAG GitHub Repository"
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor" style={{ color: 'var(--text-300)' }}>
              <path fillRule="evenodd" clipRule="evenodd" d="M12 2C6.477 2 2 6.484 2 12.017c0 4.425 2.865 8.18 6.839 9.504.5.092.682-.217.682-.483 0-.237-.008-.868-.013-1.703-2.782.605-3.369-1.343-3.369-1.343-.454-1.158-1.11-1.466-1.11-1.466-.908-.62.069-.608.069-.608 1.003.07 1.53 1.032 1.53 1.032.892 1.53 2.341 1.088 2.91.832.092-.647.35-1.088.636-1.338-2.22-.253-4.555-1.113-4.555-4.951 0-1.093.39-1.988 1.029-2.688-.103-.253-.446-1.272.098-2.65 0 0 .84-.27 2.75 1.026A9.564 9.564 0 0112 6.844c.85.004 1.705.115 2.504.337 1.909-1.296 2.747-1.027 2.747-1.027.546 1.379.202 2.398.1 2.651.64.7 1.028 1.595 1.028 2.688 0 3.848-2.339 4.695-4.566 4.943.359.309.678.92.678 1.855 0 1.338-.012 2.419-.012 2.747 0 .268.18.58.688.482A10.019 10.019 0 0022 12.017C22 6.484 17.522 2 12 2z" />
            </svg>
            <span>GitHub Repository</span>
          </a>
        </div>
      </aside>

      {/* 2. Main Stage */}
      <main className="main-stage">
        {/* Subtle Header Strip */}
        <header className="app-header">
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <span style={{ fontSize: '14px', fontWeight: 500, color: 'var(--text-100)' }}>
              {activeTab === 'chat' ? 'AMCRAG Research Assistant' : 'Knowledge Base Catalog'}
            </span>
            {activeTab === 'chat' && preselectedDocId && (
              <span
                style={{
                  fontSize: '11px',
                  fontFamily: 'var(--font-mono)',
                  padding: '1px 6px',
                  borderRadius: '4px',
                  background: 'var(--brand-tint)',
                  color: 'var(--brand)',
                }}
              >
                Filtered: {preselectedDocId}
              </span>
            )}
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            {activeTab === 'chat' && (
              <button
                onClick={handleStartNewChat}
                className="btn btn-outline"
                style={{ height: '30px', padding: '0 10px', fontSize: '12.5px', gap: '5px' }}
                title="Clear conversation and start fresh"
              >
                <Plus size={13} />
                <span>New chat</span>
              </button>
            )}
          </div>
        </header>

        {/* Content Area */}
        <div className="stage-content">
          {activeTab === 'chat' ? (
            <ChatWindow
              key={chatSessionId}
              availableDocuments={allDocuments}
              preselectedDocId={preselectedDocId}
              onClearPreselectedDoc={() => setPreselectedDocId(null)}
              onStartNewChat={handleStartNewChat}
            />
          ) : (
            <div style={{ flex: 1, overflowY: 'auto' }}>
              <DocumentManager onChatWithDoc={handleChatWithDoc} />
            </div>
          )}
        </div>
      </main>
    </div>
  );
}

export default App;
