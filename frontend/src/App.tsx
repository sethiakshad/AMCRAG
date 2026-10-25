/**
 * src/App.tsx
 * Primary application layout and navigation shell for AMCRAG.
 */

import React, { useState } from 'react';
import {
  Sparkles,
  MessageSquare,
  Database,
  BookOpen,
  FileCode,
  Layers,
} from 'lucide-react';
import { ChatWindow } from './components/chat/ChatWindow';
import { DocumentManager } from './components/documents/DocumentManager';
import { HealthIndicator } from './components/health/HealthIndicator';
import { useHealth } from './hooks/useHealth';
import { useDocuments } from './hooks/useDocuments';

export function App() {
  const [activeTab, setActiveTab] = useState<'chat' | 'documents'>('chat');
  const [preselectedDocId, setPreselectedDocId] = useState<string | null>(null);

  const { health, isLoading: isHealthLoading, isOffline, checkHealth } = useHealth();
  const { allDocuments } = useDocuments();

  const handleChatWithDoc = (docId: string) => {
    setPreselectedDocId(docId);
    setActiveTab('chat');
  };

  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        minHeight: '100vh',
        background: 'radial-gradient(ellipse 80% 50% at 50% -20%, rgba(99, 102, 241, 0.15), transparent 70%), var(--bg-main)',
      }}
    >
      {/* Top Navigation Bar */}
      <header
        style={{
          borderBottom: '1px solid var(--border-subtle)',
          background: 'rgba(8, 11, 18, 0.8)',
          backdropFilter: 'blur(16px)',
          position: 'sticky',
          top: 0,
          zIndex: 100,
        }}
      >
        <div
          style={{
            maxWidth: '1200px',
            margin: '0 auto',
            padding: '0.75rem 1.5rem',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            gap: '1rem',
          }}
        >
          {/* Brand Identity */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <div
              style={{
                width: '32px',
                height: '32px',
                borderRadius: '8px',
                background: 'var(--brand-gradient)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                color: '#ffffff',
                boxShadow: '0 2px 10px rgba(99, 102, 241, 0.4)',
              }}
            >
              <Sparkles size={18} />
            </div>

            <div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                <span className="gradient-text" style={{ fontSize: '1.125rem', fontFamily: 'var(--font-heading)' }}>
                  AMCRAG
                </span>
                <span
                  style={{
                    fontSize: '0.6875rem',
                    fontWeight: 700,
                    padding: '1px 6px',
                    borderRadius: '4px',
                    background: 'rgba(255, 255, 255, 0.08)',
                    color: 'var(--text-secondary)',
                    fontFamily: 'var(--font-mono)',
                  }}
                >
                  v1.0
                </span>
              </div>
              <div style={{ fontSize: '0.6875rem', color: 'var(--text-muted)' }}>
                Adaptive Multimodal Corrective RAG
              </div>
            </div>
          </div>

          {/* Center Tabs Navigation */}
          <nav
            style={{
              display: 'flex',
              alignItems: 'center',
              padding: '3px',
              borderRadius: '10px',
              background: 'rgba(255, 255, 255, 0.04)',
              border: '1px solid var(--border-subtle)',
            }}
          >
            <button
              onClick={() => setActiveTab('chat')}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '6px',
                padding: '6px 14px',
                borderRadius: '8px',
                border: 'none',
                background: activeTab === 'chat' ? 'var(--brand-gradient)' : 'transparent',
                color: activeTab === 'chat' ? '#ffffff' : 'var(--text-secondary)',
                fontSize: '0.8125rem',
                fontWeight: activeTab === 'chat' ? 600 : 500,
                cursor: 'pointer',
                transition: 'all 0.15s ease',
              }}
            >
              <MessageSquare size={14} />
              <span>Ask & Chat</span>
            </button>

            <button
              onClick={() => setActiveTab('documents')}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '6px',
                padding: '6px 14px',
                borderRadius: '8px',
                border: 'none',
                background: activeTab === 'documents' ? 'var(--brand-gradient)' : 'transparent',
                color: activeTab === 'documents' ? '#ffffff' : 'var(--text-secondary)',
                fontSize: '0.8125rem',
                fontWeight: activeTab === 'documents' ? 600 : 500,
                cursor: 'pointer',
                transition: 'all 0.15s ease',
              }}
            >
              <Database size={14} />
              <span>Knowledge Base</span>
              {allDocuments.length > 0 && (
                <span
                  style={{
                    fontSize: '0.6875rem',
                    fontWeight: 700,
                    padding: '1px 5px',
                    borderRadius: '9999px',
                    background: activeTab === 'documents' ? 'rgba(255,255,255,0.25)' : 'rgba(99,102,241,0.2)',
                    color: activeTab === 'documents' ? '#fff' : '#818cf8',
                  }}
                >
                  {allDocuments.length}
                </span>
              )}
            </button>
          </nav>

          {/* Right Toolbar: Health & External Docs */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
            <HealthIndicator
              health={health}
              isLoading={isHealthLoading}
              isOffline={isOffline}
              onRefresh={checkHealth}
            />

            <a
              href="/docs"
              target="_blank"
              rel="noreferrer"
              className="btn-icon"
              title="FastAPI Swagger OpenAPI Documentation (/docs)"
              style={{ textDecoration: 'none' }}
            >
              <FileCode size={18} />
            </a>

            <a
              href="https://github.com/sethiakshad/AMCRAG"
              target="_blank"
              rel="noreferrer"
              className="btn-icon"
              title="AMCRAG GitHub Repository"
              style={{ textDecoration: 'none' }}
            >
              <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor">
                <path fillRule="evenodd" clipRule="evenodd" d="M12 2C6.477 2 2 6.484 2 12.017c0 4.425 2.865 8.18 6.839 9.504.5.092.682-.217.682-.483 0-.237-.008-.868-.013-1.703-2.782.605-3.369-1.343-3.369-1.343-.454-1.158-1.11-1.466-1.11-1.466-.908-.62.069-.608.069-.608 1.003.07 1.53 1.032 1.53 1.032.892 1.53 2.341 1.088 2.91.832.092-.647.35-1.088.636-1.338-2.22-.253-4.555-1.113-4.555-4.951 0-1.093.39-1.988 1.029-2.688-.103-.253-.446-1.272.098-2.65 0 0 .84-.27 2.75 1.026A9.564 9.564 0 0112 6.844c.85.004 1.705.115 2.504.337 1.909-1.296 2.747-1.027 2.747-1.027.546 1.379.202 2.398.1 2.651.64.7 1.028 1.595 1.028 2.688 0 3.848-2.339 4.695-4.566 4.943.359.309.678.92.678 1.855 0 1.338-.012 2.419-.012 2.747 0 .268.18.58.688.482A10.019 10.019 0 0022 12.017C22 6.484 17.522 2 12 2z" />
              </svg>
            </a>
          </div>
        </div>
      </header>

      {/* Main View Area */}
      <main
        style={{
          flex: 1,
          maxWidth: '1200px',
          width: '100%',
          margin: '0 auto',
          padding: '1.25rem 1.5rem',
          display: 'flex',
          flexDirection: 'column',
        }}
      >
        {activeTab === 'chat' ? (
          <ChatWindow
            availableDocuments={allDocuments}
            preselectedDocId={preselectedDocId}
            onClearPreselectedDoc={() => setPreselectedDocId(null)}
          />
        ) : (
          <DocumentManager onChatWithDoc={handleChatWithDoc} />
        )}
      </main>
    </div>
  );
}

export default App;
