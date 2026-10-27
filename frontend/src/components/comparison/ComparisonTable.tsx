/**
 * src/components/comparison/ComparisonTable.tsx
 * Detailed side-by-side comparison table with expandable evidence & metric inspect drawers.
 */

import React, { useState } from 'react';
import {
  ChevronDown,
  ChevronRight,
  CheckCircle2,
  XCircle,
  AlertTriangle,
  Info,
  GitCommit,
  Check,
} from 'lucide-react';
import { ComparedQuestionResult } from '../../types/comparison';

interface ComparisonTableProps {
  questions: ComparedQuestionResult[];
  categoryFilter: string;
}

export const ComparisonTable: React.FC<ComparisonTableProps> = ({
  questions,
  categoryFilter,
}) => {
  const [expandedId, setExpandedId] = useState<string | null>(null);

  const filtered = questions.filter((q) => {
    if (categoryFilter === 'all') return true;
    if (categoryFilter === 'failures_only') {
      return !q.is_correct_amcrag || !q.is_correct_normal;
    }
    if (categoryFilter === 'identical_only') {
      return !!q.has_identical_evidence;
    }
    return q.category === categoryFilter;
  });

  const toggleRow = (id: string) => {
    setExpandedId((curr) => (curr === id ? null : id));
  };

  if (filtered.length === 0) {
    return (
      <div style={{ textAlign: 'center', padding: '40px', color: 'var(--text-300)' }}>
        No evaluation questions match the selected filter.
      </div>
    );
  }

  return (
    <div className="comp-table-card">
      <div className="comp-table-header-bar">
        <div>
          <span style={{ fontSize: '14px', fontWeight: 600, color: 'var(--text-100)' }}>
            Detailed Question Comparison ({filtered.length} evaluated)
          </span>
          <div style={{ fontSize: '12px', color: 'var(--text-300)', marginTop: '2px' }}>
            Click any row to inspect execution stages, side-by-side retrieved evidence, and failure analysis
          </div>
        </div>
      </div>

      <table className="comp-table">
        <thead>
          <tr>
            <th style={{ width: '36px' }}></th>
            <th>Question</th>
            <th>Category</th>
            <th>Normal RAG Answer & Status</th>
            <th>AMCRAG Answer & Status</th>
            <th>F1 Correctness</th>
            <th>Latency</th>
          </tr>
        </thead>
        <tbody>
          {filtered.map((item) => {
            const isExpanded = expandedId === item.question_id;
            const normCorr = item.normal_rag_metrics.answer_correctness != null
              ? `${(item.normal_rag_metrics.answer_correctness * 100).toFixed(0)}%`
              : 'N/A';
            const amcCorr = item.amcrag_metrics.answer_correctness != null
              ? `${(item.amcrag_metrics.answer_correctness * 100).toFixed(0)}%`
              : 'N/A';

            return (
              <React.Fragment key={item.question_id}>
                <tr
                  className={`comp-row ${isExpanded ? 'expanded' : ''}`}
                  onClick={() => toggleRow(item.question_id)}
                >
                  <td style={{ textAlign: 'center', color: 'var(--text-300)' }}>
                    {isExpanded ? <ChevronDown size={16} /> : <ChevronRight size={16} />}
                  </td>
                  <td style={{ fontWeight: 500, color: 'var(--text-100)', maxWidth: '240px' }}>
                    <div>{item.question}</div>
                    {item.has_identical_evidence && (
                      <span
                        style={{
                          fontSize: '10.5px',
                          color: 'var(--text-300)',
                          background: 'var(--bg-200)',
                          padding: '1px 5px',
                          borderRadius: 'var(--radius-sm)',
                          display: 'inline-block',
                          marginTop: '4px',
                        }}
                      >
                        Identical Evidence
                      </span>
                    )}
                  </td>
                  <td>
                    <span className={`comp-badge ${item.category}`}>
                      {item.category.replace('_', ' ')}
                    </span>
                  </td>
                  <td style={{ color: 'var(--text-200)', maxWidth: '240px', fontSize: '12.5px' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '4px' }}>
                      {item.is_correct_normal ? (
                        <span className="comp-status-badge correct">
                          <Check size={11} /> Correct
                        </span>
                      ) : (
                        <span className="comp-status-badge failed">
                          <XCircle size={11} /> Partial / Refused
                        </span>
                      )}
                    </div>
                    <div style={{ maxHeight: '42px', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                      {item.normal_rag_output.answer}
                    </div>
                  </td>
                  <td style={{ color: 'var(--text-100)', maxWidth: '240px', fontSize: '12.5px', fontWeight: 500 }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '4px' }}>
                      {item.is_correct_amcrag ? (
                        <span className="comp-status-badge correct">
                          <Check size={11} /> Correct
                        </span>
                      ) : (
                        <span className="comp-status-badge failed">
                          <XCircle size={11} /> Partial / Refused
                        </span>
                      )}
                      {item.amcrag_output.was_corrected && (
                        <span className="comp-kpi-pill delta" style={{ fontSize: '10px' }}>
                          CRAG Corrected
                        </span>
                      )}
                    </div>
                    <div style={{ maxHeight: '42px', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                      {item.amcrag_output.answer}
                    </div>
                  </td>
                  <td style={{ fontSize: '12px', fontFamily: 'var(--font-mono)' }}>
                    <span style={{ color: '#8A887F' }}>{normCorr}</span>
                    <span style={{ color: 'var(--text-300)', margin: '0 4px' }}>vs</span>
                    <span style={{ color: 'var(--brand)', fontWeight: 600 }}>{amcCorr}</span>
                  </td>
                  <td style={{ fontSize: '12px', fontFamily: 'var(--font-mono)' }}>
                    <span style={{ color: '#8A887F' }}>{item.normal_rag_output.total_latency_ms.toFixed(0)}ms</span>
                    <span style={{ color: 'var(--text-300)', margin: '0 4px' }}>vs</span>
                    <span style={{ color: 'var(--brand)', fontWeight: 600 }}>{item.amcrag_output.total_latency_ms.toFixed(0)}ms</span>
                  </td>
                </tr>

                {/* Expanded Detailed Comparison Row */}
                {isExpanded && (
                  <tr>
                    <td colSpan={7} style={{ padding: 0 }}>
                      <div className="comp-detail-drawer">
                        {/* 1. Ground Truth Reference */}
                        {item.reference_answer && (
                          <div style={{ background: 'var(--bg-000)', padding: '12px 16px', borderRadius: 'var(--radius-md)', border: 'var(--border-w) solid var(--border-200)' }}>
                            <div style={{ fontSize: '11px', textTransform: 'uppercase', color: 'var(--text-300)', fontWeight: 600, letterSpacing: '0.04em', marginBottom: '4px' }}>
                              Ground Truth Reference Answer
                            </div>
                            <div style={{ fontSize: '13px', color: 'var(--text-100)', fontFamily: 'var(--font-serif)', lineHeight: 1.5 }}>
                              {item.reference_answer}
                            </div>
                          </div>
                        )}

                        {/* 2. Diagnostic Failure Analysis Box */}
                        {item.failure_analysis && (
                          <div className={`comp-diagnostic-box ${item.is_correct_amcrag && !item.is_correct_normal ? 'resolved' : ''}`}>
                            <div className="comp-diagnostic-title">
                              <Info size={14} style={{ color: item.is_correct_amcrag && !item.is_correct_normal ? 'var(--success)' : 'var(--brand)' }} />
                              <span>Diagnostic Failure & Retrieval Analysis</span>
                            </div>
                            <div className="comp-diagnostic-text">
                              {item.failure_analysis}
                            </div>
                          </div>
                        )}

                        {/* 3. Pipeline Stages Executed */}
                        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px' }}>
                          <div className="comp-stages-container">
                            <span style={{ fontSize: '11px', textTransform: 'uppercase', color: 'var(--text-300)', fontWeight: 600 }}>
                              Normal RAG Execution Stages ({item.normal_stages_executed?.length || 2}):
                            </span>
                            <div className="comp-stage-flow">
                              {(item.normal_stages_executed || ['dense_vector_retrieval', 'generation']).map((stage, sIdx) => (
                                <span key={sIdx} className="comp-stage-chip">
                                  {stage.replace(/_/g, ' ')}
                                </span>
                              ))}
                            </div>
                          </div>

                          <div className="comp-stages-container">
                            <span style={{ fontSize: '11px', textTransform: 'uppercase', color: 'var(--brand)', fontWeight: 600 }}>
                              AMCRAG Execution Stages ({item.amcrag_stages_executed?.length || 5}):
                            </span>
                            <div className="comp-stage-flow">
                              {(item.amcrag_stages_executed || ['query_analysis', 'hybrid_retrieval', 'crag_eval', 'refinement', 'grounded_generation']).map((stage, sIdx) => (
                                <span key={sIdx} className="comp-stage-chip amcrag">
                                  {stage.replace(/_/g, ' ')}
                                </span>
                              ))}
                            </div>
                          </div>
                        </div>

                        {/* 4. Side by Side Outputs and Retrieved Evidence */}
                        <div className="comp-compare-grid">
                          {/* Normal RAG Column */}
                          <div className="comp-side-box">
                            <div className="comp-side-title">
                              <span style={{ color: '#8A887F' }}>Normal RAG Baseline</span>
                              <span style={{ fontSize: '11px', fontFamily: 'var(--font-mono)', color: 'var(--text-300)' }}>
                                {item.normal_rag_output.total_latency_ms.toFixed(0)} ms total
                              </span>
                            </div>

                            <div style={{ fontSize: '13px', color: 'var(--text-100)', lineHeight: 1.5 }}>
                              {item.normal_rag_output.answer}
                            </div>

                            <div style={{ marginTop: '10px' }}>
                              <div style={{ fontSize: '11.5px', fontWeight: 600, color: 'var(--text-200)', marginBottom: '4px' }}>
                                Retrieved Evidence ({item.normal_rag_output.retrieved_evidence.length} chunks):
                              </div>
                              {item.normal_rag_output.retrieved_evidence.length === 0 ? (
                                <div style={{ fontSize: '12px', color: 'var(--text-300)', fontStyle: 'italic' }}>No chunks retrieved.</div>
                              ) : (
                                item.normal_rag_output.retrieved_evidence.map((chunk, idx) => (
                                  <div key={idx} className="comp-evidence-strip">
                                    <div style={{ fontWeight: 600, marginBottom: '2px', color: 'var(--text-100)' }}>
                                      {chunk.label || `[Chunk ${idx + 1}]`} — Page {chunk.page || 1} (Score: {chunk.score?.toFixed(3) ?? 'N/A'})
                                    </div>
                                    <div>{chunk.text}</div>
                                  </div>
                                ))
                              )}
                            </div>

                            {/* Normal RAG Scores */}
                            <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap', marginTop: '10px', paddingTop: '10px', borderTop: 'var(--border-w) solid var(--border-100)' }}>
                              <span className="comp-kpi-pill tie">Faithfulness: {item.normal_rag_metrics.faithfulness != null ? `${(item.normal_rag_metrics.faithfulness * 100).toFixed(0)}%` : 'N/A'}</span>
                              <span className="comp-kpi-pill tie">Context Precision: {item.normal_rag_metrics.context_precision != null ? `${(item.normal_rag_metrics.context_precision * 100).toFixed(0)}%` : 'N/A'}</span>
                              <span className="comp-kpi-pill tie">Recall@3: {item.normal_rag_metrics.recall_at_3 != null ? `${(item.normal_rag_metrics.recall_at_3 * 100).toFixed(0)}%` : 'N/A'}</span>
                            </div>
                          </div>

                          {/* AMCRAG Column */}
                          <div className="comp-side-box" style={{ borderColor: 'var(--brand-tint)' }}>
                            <div className="comp-side-title">
                              <span style={{ color: 'var(--brand)' }}>AMCRAG Pipeline</span>
                              <span style={{ fontSize: '11px', fontFamily: 'var(--font-mono)', color: 'var(--text-300)' }}>
                                {item.amcrag_output.total_latency_ms.toFixed(0)} ms total
                              </span>
                            </div>

                            <div style={{ fontSize: '13px', color: 'var(--text-100)', lineHeight: 1.5 }}>
                              {item.amcrag_output.answer}
                            </div>

                            <div style={{ marginTop: '10px' }}>
                              <div style={{ fontSize: '11.5px', fontWeight: 600, color: 'var(--text-200)', marginBottom: '4px' }}>
                                Retrieved Evidence ({item.amcrag_output.retrieved_evidence.length} sources):
                              </div>
                              {item.amcrag_output.retrieved_evidence.length === 0 ? (
                                <div style={{ fontSize: '12px', color: 'var(--text-300)', fontStyle: 'italic' }}>No sources retrieved.</div>
                              ) : (
                                item.amcrag_output.retrieved_evidence.map((chunk, idx) => (
                                  <div key={idx} className="comp-evidence-strip" style={{ borderLeftColor: 'var(--brand)' }}>
                                    <div style={{ fontWeight: 600, marginBottom: '2px', color: 'var(--brand)' }}>
                                      {chunk.label || `[E${idx + 1}]`} — Page {chunk.page || 1} (Score: {chunk.score?.toFixed(3) ?? 'N/A'})
                                    </div>
                                    <div>{chunk.text}</div>
                                  </div>
                                ))
                              )}
                            </div>

                            {/* AMCRAG Scores */}
                            <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap', marginTop: '10px', paddingTop: '10px', borderTop: 'var(--border-w) solid var(--border-100)' }}>
                              <span className="comp-kpi-pill delta">Faithfulness: {item.amcrag_metrics.faithfulness != null ? `${(item.amcrag_metrics.faithfulness * 100).toFixed(0)}%` : 'N/A'}</span>
                              <span className="comp-kpi-pill delta">Context Precision: {item.amcrag_metrics.context_precision != null ? `${(item.amcrag_metrics.context_precision * 100).toFixed(0)}%` : 'N/A'}</span>
                              <span className="comp-kpi-pill delta">Recall@3: {item.amcrag_metrics.recall_at_3 != null ? `${(item.amcrag_metrics.recall_at_3 * 100).toFixed(0)}%` : 'N/A'}</span>
                            </div>
                          </div>
                        </div>
                      </div>
                    </td>
                  </tr>
                )}
              </React.Fragment>
            );
          })}
        </tbody>
      </table>
    </div>
  );
};

