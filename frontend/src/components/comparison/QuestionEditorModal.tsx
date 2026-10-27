/**
 * src/components/comparison/QuestionEditorModal.tsx
 * Modal dialog enabling users to review, edit, add, and curate evaluation questions and reference answers.
 */

import React, { useState } from 'react';
import { X, Plus, Trash2, Check, HelpCircle } from 'lucide-react';
import { EvaluationQuestion, QuestionCategory } from '../../types/comparison';

interface QuestionEditorModalProps {
  isOpen: boolean;
  onClose: () => void;
  questions: EvaluationQuestion[];
  onSave: (updated: EvaluationQuestion[]) => void;
}

export const QuestionEditorModal: React.FC<QuestionEditorModalProps> = ({
  isOpen,
  onClose,
  questions,
  onSave,
}) => {
  const [draftQuestions, setDraftQuestions] = useState<EvaluationQuestion[]>(questions);

  if (!isOpen) return null;

  const handleUpdate = (index: number, field: keyof EvaluationQuestion, value: any) => {
    setDraftQuestions((prev) => {
      const copy = [...prev];
      copy[index] = { ...copy[index], [field]: value };
      return copy;
    });
  };

  const handleAddQuestion = () => {
    const newQ: EvaluationQuestion = {
      id: `q_${Date.now()}`,
      question: 'New evaluation query?',
      category: 'factual',
      reference_answer: '',
      expected_pages: [],
      expected_keywords: [],
    };
    setDraftQuestions((prev) => [...prev, newQ]);
  };

  const handleDeleteQuestion = (index: number) => {
    setDraftQuestions((prev) => prev.filter((_, i) => i !== index));
  };

  const handleApply = () => {
    onSave(draftQuestions);
    onClose();
  };

  return (
    <div className="comp-modal-overlay" onClick={onClose}>
      <div className="comp-modal" onClick={(e) => e.stopPropagation()}>
        {/* Header */}
        <div style={{ padding: '16px 20px', borderBottom: 'var(--border-w) solid var(--border-200)', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <div>
            <div style={{ fontSize: '15px', fontWeight: 600, color: 'var(--text-100)' }}>
              Review & Edit Evaluation Questions
            </div>
            <div style={{ fontSize: '12px', color: 'var(--text-300)' }}>
              Customize evaluation queries and reference ground truth answers before running the benchmark.
            </div>
          </div>
          <button
            onClick={onClose}
            className="btn btn-icon"
            style={{ width: '28px', height: '28px' }}
          >
            <X size={16} />
          </button>
        </div>

        {/* Content list */}
        <div style={{ padding: '16px 20px', overflowY: 'auto', flex: 1, display: 'flex', flexDirection: 'column', gap: '14px' }}>
          {draftQuestions.map((q, idx) => (
            <div
              key={q.id || idx}
              style={{
                background: 'var(--bg-100)',
                border: 'var(--border-w) solid var(--border-200)',
                borderRadius: 'var(--radius-md)',
                padding: '14px',
                display: 'flex',
                flexDirection: 'column',
                gap: '10px',
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '10px' }}>
                <span style={{ fontSize: '12px', fontWeight: 600, color: 'var(--brand)' }}>
                  Question #{idx + 1}
                </span>

                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <select
                    value={q.category}
                    onChange={(e) => handleUpdate(idx, 'category', e.target.value as QuestionCategory)}
                    className="comp-select"
                    style={{ height: '28px', fontSize: '12px', padding: '0 8px' }}
                  >
                    <option value="factual">Factual</option>
                    <option value="multihop">Multi-hop</option>
                    <option value="visual_table">Table / Visual</option>
                    <option value="unanswerable">Unanswerable</option>
                  </select>

                  <button
                    onClick={() => handleDeleteQuestion(idx)}
                    className="btn btn-icon"
                    style={{ width: '28px', height: '28px', color: 'var(--danger)' }}
                    title="Remove question"
                  >
                    <Trash2 size={14} />
                  </button>
                </div>
              </div>

              {/* Question Text */}
              <div>
                <label style={{ fontSize: '11px', textTransform: 'uppercase', color: 'var(--text-300)', fontWeight: 600, display: 'block', marginBottom: '3px' }}>
                  Question Prompt
                </label>
                <input
                  type="text"
                  value={q.question}
                  onChange={(e) => handleUpdate(idx, 'question', e.target.value)}
                  style={{
                    width: '100%',
                    height: '34px',
                    padding: '0 10px',
                    borderRadius: 'var(--radius-sm)',
                    border: 'var(--border-w) solid var(--border-200)',
                    background: 'var(--bg-000)',
                    color: 'var(--text-100)',
                    fontSize: '13px',
                    fontFamily: 'var(--font-sans)',
                  }}
                />
              </div>

              {/* Reference Answer */}
              <div>
                <label style={{ fontSize: '11px', textTransform: 'uppercase', color: 'var(--text-300)', fontWeight: 600, display: 'block', marginBottom: '3px' }}>
                  Reference Ground Truth Answer (for correctness F1 calculation)
                </label>
                <textarea
                  rows={2}
                  value={q.reference_answer || ''}
                  onChange={(e) => handleUpdate(idx, 'reference_answer', e.target.value)}
                  placeholder="Expected answer text. Leave blank if unavailable (will show N/A)."
                  style={{
                    width: '100%',
                    padding: '8px 10px',
                    borderRadius: 'var(--radius-sm)',
                    border: 'var(--border-w) solid var(--border-200)',
                    background: 'var(--bg-000)',
                    color: 'var(--text-100)',
                    fontSize: '12.5px',
                    fontFamily: 'var(--font-sans)',
                    resize: 'vertical',
                  }}
                />
              </div>

              {/* Page references */}
              <div>
                <label style={{ fontSize: '11px', textTransform: 'uppercase', color: 'var(--text-300)', fontWeight: 600, display: 'block', marginBottom: '3px' }}>
                  Expected Source Pages (comma separated, e.g. 1, 2)
                </label>
                <input
                  type="text"
                  value={(q.expected_pages || []).join(', ')}
                  onChange={(e) => {
                    const pages = e.target.value
                      .split(',')
                      .map((p) => parseInt(p.trim(), 10))
                      .filter((n) => !isNaN(n));
                    handleUpdate(idx, 'expected_pages', pages);
                  }}
                  placeholder="Optional ground truth page numbers for retrieval recall & MRR"
                  style={{
                    width: '100%',
                    height: '30px',
                    padding: '0 10px',
                    borderRadius: 'var(--radius-sm)',
                    border: 'var(--border-w) solid var(--border-200)',
                    background: 'var(--bg-000)',
                    color: 'var(--text-100)',
                    fontSize: '12px',
                    fontFamily: 'var(--font-mono)',
                  }}
                />
              </div>
            </div>
          ))}

          <button
            onClick={handleAddQuestion}
            className="btn btn-outline"
            style={{ height: '36px', gap: '6px', justifyContent: 'center' }}
          >
            <Plus size={14} />
            <span>Add Custom Question</span>
          </button>
        </div>

        {/* Footer */}
        <div style={{ padding: '14px 20px', borderTop: 'var(--border-w) solid var(--border-200)', display: 'flex', alignItems: 'center', justifyContent: 'flex-end', gap: '10px' }}>
          <button onClick={onClose} className="btn btn-outline" style={{ height: '34px' }}>
            Cancel
          </button>
          <button onClick={handleApply} className="btn btn-primary" style={{ height: '34px', gap: '6px' }}>
            <Check size={14} />
            <span>Save & Use ({draftQuestions.length} Questions)</span>
          </button>
        </div>
      </div>
    </div>
  );
};
