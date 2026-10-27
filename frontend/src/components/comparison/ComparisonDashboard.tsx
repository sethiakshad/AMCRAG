/**
 * src/components/comparison/ComparisonDashboard.tsx
 * RAG Comparison Dashboard: Side-by-side benchmark of AMCRAG vs Normal RAG baseline.
 */

import React, { useState, useEffect } from 'react';
import {
  Play,
  RotateCw,
  Download,
  Settings,
  Filter,
  Layers,
  Clock,
  Sparkles,
  CheckCircle2,
  AlertTriangle,
  History,
  Trash2,
  Target,
  Cpu,
  RefreshCw,
  GitCompare,
  FileCheck,
} from 'lucide-react';
import { useDocuments } from '../../hooks/useDocuments';
import { ComparisonCharts } from './ComparisonCharts';
import { ComparisonTable } from './ComparisonTable';
import { QuestionEditorModal } from './QuestionEditorModal';
import {
  fetchDefaultQuestions,
  runComparisonBenchmark,
} from '../../services/comparisonApi';
import {
  ComparisonRunResponse,
  EvaluationQuestion,
  QuestionCategory,
} from '../../types/comparison';
import './comparison.css';

const LOCAL_STORAGE_HISTORY_KEY = 'amcrag_benchmark_runs';

export const ComparisonDashboard: React.FC = () => {
  const { allDocuments } = useDocuments();

  const [selectedDocId, setSelectedDocId] = useState<string>('');
  const [questions, setQuestions] = useState<EvaluationQuestion[]>([]);
  const [isRunning, setIsRunning] = useState<boolean>(false);
  const [result, setResult] = useState<ComparisonRunResponse | null>(null);
  const [pastRuns, setPastRuns] = useState<ComparisonRunResponse[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [categoryFilter, setCategoryFilter] = useState<string>('all');
  const [isEditorOpen, setIsEditorOpen] = useState<boolean>(false);

  // Auto-select first document if available
  useEffect(() => {
    if (allDocuments.length > 0 && !selectedDocId) {
      setSelectedDocId(allDocuments[0].document_id);
    }
  }, [allDocuments, selectedDocId]);

  // Load default evaluation questions when selectedDocId changes
  useEffect(() => {
    async function loadQuestions() {
      try {
        const defaultQs = await fetchDefaultQuestions(selectedDocId || undefined);
        setQuestions(defaultQs);
      } catch (err: any) {
        console.warn('Failed to load default questions:', err);
      }
    }
    loadQuestions();
  }, [selectedDocId]);

  // Load past runs from localStorage on mount
  useEffect(() => {
    try {
      const saved = localStorage.getItem(LOCAL_STORAGE_HISTORY_KEY);
      if (saved) {
        const parsed = JSON.parse(saved);
        if (Array.isArray(parsed) && parsed.length > 0) {
          setPastRuns(parsed);
          setResult((curr) => curr || parsed[0]);
        }
      }
    } catch (e) {
      console.warn('Failed to read past runs from localStorage', e);
    }
  }, []);

  const handleRunComparison = async () => {
    if (questions.length === 0) {
      setError('Please add at least one question to run comparison.');
      return;
    }

    setIsRunning(true);
    setError(null);

    try {
      const benchmarkResult = await runComparisonBenchmark({
        document_id: selectedDocId || null,
        questions: questions,
        top_k: 5,
      });

      setResult(benchmarkResult);

      // Save to localStorage history (keep up to 10 latest)
      try {
        const saved = localStorage.getItem(LOCAL_STORAGE_HISTORY_KEY);
        const currentRuns: ComparisonRunResponse[] = saved ? JSON.parse(saved) : [];
        const updated = [
          benchmarkResult,
          ...currentRuns.filter((r) => r.run_id !== benchmarkResult.run_id),
        ].slice(0, 10);
        localStorage.setItem(LOCAL_STORAGE_HISTORY_KEY, JSON.stringify(updated));
        setPastRuns(updated);
      } catch (err) {
        console.warn('Failed to save run to localStorage', err);
      }
    } catch (err: any) {
      setError(err.message || 'Failed to execute comparative benchmark.');
    } finally {
      setIsRunning(false);
    }
  };

  const handleSelectPastRun = (runId: string) => {
    const selected = pastRuns.find((r) => r.run_id === runId);
    if (selected) {
      setResult(selected);
    }
  };

  const handleClearHistory = () => {
    localStorage.removeItem(LOCAL_STORAGE_HISTORY_KEY);
    setPastRuns([]);
  };

  const handleExportJSON = () => {
    if (!result) return;
    const blob = new Blob([JSON.stringify(result, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `amcrag_vs_normal_rag_${result.run_id}.json`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const handleExportCSV = () => {
    if (!result) return;
    const headers = [
      'Question ID',
      'Question',
      'Category',
      'Reference Answer',
      'Normal RAG Answer',
      'AMCRAG Answer',
      'Normal Correct',
      'AMCRAG Correct',
      'Normal F1 Correctness',
      'AMCRAG F1 Correctness',
      'Normal Faithfulness',
      'AMCRAG Faithfulness',
      'Identical Evidence',
      'Normal Latency (ms)',
      'AMCRAG Latency (ms)',
      'Failure / Diagnostic Analysis',
    ];

    const rows = result.questions.map((q) => [
      `"${q.question_id}"`,
      `"${q.question.replace(/"/g, '""')}"`,
      `"${q.category}"`,
      `"${(q.reference_answer || '').replace(/"/g, '""')}"`,
      `"${q.normal_rag_output.answer.replace(/"/g, '""')}"`,
      `"${q.amcrag_output.answer.replace(/"/g, '""')}"`,
      q.is_correct_normal ? 'YES' : 'NO',
      q.is_correct_amcrag ? 'YES' : 'NO',
      q.normal_rag_metrics.answer_correctness ?? 'N/A',
      q.amcrag_metrics.answer_correctness ?? 'N/A',
      q.normal_rag_metrics.faithfulness ?? 'N/A',
      q.amcrag_metrics.faithfulness ?? 'N/A',
      q.has_identical_evidence ? 'YES' : 'NO',
      q.normal_rag_output.total_latency_ms.toFixed(0),
      q.amcrag_output.total_latency_ms.toFixed(0),
      `"${(q.failure_analysis || '').replace(/"/g, '""')}"`,
    ]);

    const csvContent = [headers.join(','), ...rows.map((r) => r.join(','))].join('\n');
    const blob = new Blob([csvContent], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `amcrag_vs_normal_rag_${result.run_id}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="comp-container">
      {/* 1. Dashboard Controls Bar */}
      <div className="comp-control-bar">
        <div className="comp-controls-group">
          <label style={{ fontSize: '13px', fontWeight: 600, color: 'var(--text-100)' }}>
            Document:
          </label>
          <select
            value={selectedDocId}
            onChange={(e) => setSelectedDocId(e.target.value)}
            className="comp-select"
            disabled={isRunning}
            style={{ maxWidth: '280px' }}
          >
            {allDocuments.length === 0 ? (
              <option value="">(No indexed documents - upload first)</option>
            ) : (
              allDocuments.map((doc) => (
                <option key={doc.document_id} value={doc.document_id}>
                  {doc.filename} ({doc.page_count || 1} pages)
                </option>
              ))
            )}
          </select>

          <button
            onClick={() => setIsEditorOpen(true)}
            className="btn btn-outline"
            style={{ height: '36px', gap: '6px' }}
            disabled={isRunning}
            title="Review and configure evaluation benchmark questions"
          >
            <Settings size={14} />
            <span>Configure Questions ({questions.length})</span>
          </button>

          {/* Past Runs History Selector */}
          {pastRuns.length > 0 && (
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
              <History size={14} style={{ color: 'var(--text-300)' }} />
              <select
                value={result?.run_id || ''}
                onChange={(e) => handleSelectPastRun(e.target.value)}
                className="comp-select"
                style={{ height: '36px', fontSize: '12px', maxWidth: '220px' }}
                title="Select a previously executed benchmark run"
              >
                {pastRuns.map((r, idx) => (
                  <option key={r.run_id} value={r.run_id}>
                    Run {idx + 1}: {r.summary.amcrag_accuracy_pct?.toFixed(0)}% vs {r.summary.normal_rag_accuracy_pct?.toFixed(0)}% ({new Date(r.timestamp).toLocaleTimeString()})
                  </option>
                ))}
              </select>
              <button
                onClick={handleClearHistory}
                className="btn btn-outline"
                style={{ height: '36px', padding: '0 8px' }}
                title="Clear run history"
              >
                <Trash2 size={13} style={{ color: 'var(--text-300)' }} />
              </button>
            </div>
          )}
        </div>

        <div className="comp-controls-group">
          {result && (
            <>
              <button
                onClick={handleExportCSV}
                className="btn btn-outline"
                style={{ height: '36px', gap: '5px' }}
                title="Download results as CSV"
              >
                <Download size={14} />
                <span>Export CSV</span>
              </button>
              <button
                onClick={handleExportJSON}
                className="btn btn-outline"
                style={{ height: '36px', gap: '5px' }}
                title="Download raw experiment JSON"
              >
                <Download size={14} />
                <span>Export JSON</span>
              </button>
            </>
          )}

          <button
            onClick={handleRunComparison}
            disabled={isRunning || allDocuments.length === 0}
            className="btn btn-primary"
            style={{ height: '36px', padding: '0 18px', gap: '8px' }}
          >
            {isRunning ? (
              <>
                <RotateCw size={14} className="spin" />
                <span>Benchmarking Both Pipelines...</span>
              </>
            ) : (
              <>
                <Play size={14} fill="currentColor" />
                <span>Run Comparison Benchmark</span>
              </>
            )}
          </button>
        </div>
      </div>

      {/* Error alert */}
      {error && (
        <div style={{ background: 'rgba(239, 68, 68, 0.1)', border: '1px solid var(--danger)', padding: '12px 16px', borderRadius: 'var(--radius-md)', color: 'var(--danger)', display: 'flex', alignItems: 'center', gap: '10px' }}>
          <AlertTriangle size={18} />
          <span>{error}</span>
        </div>
      )}

      {/* Progress placeholder when running */}
      {isRunning && (
        <div style={{ background: 'var(--bg-000)', border: 'var(--border-w) solid var(--border-200)', borderRadius: 'var(--radius-lg)', padding: '36px', textAlign: 'center', display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '12px' }}>
          <RotateCw size={28} className="spin" style={{ color: 'var(--brand)' }} />
          <div style={{ fontSize: '15px', fontWeight: 600, color: 'var(--text-100)' }}>
            Executing Side-by-Side Comparison on {questions.length} Questions...
          </div>
          <div style={{ fontSize: '13px', color: 'var(--text-300)', maxWidth: '560px' }}>
            Running both real pipelines: Normal RAG (Dense BGE top-k vector retrieval) and AMCRAG (Adaptive routing, Hybrid BGE + BM25 RRF fusion, CRAG evidence confidence evaluation, and grounded generation).
          </div>
        </div>
      )}

      {/* Empty State before first benchmark */}
      {!result && !isRunning && (
        <div style={{ background: 'var(--bg-000)', border: 'var(--border-w) solid var(--border-200)', borderRadius: 'var(--radius-lg)', padding: '48px 32px', textAlign: 'center', display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '14px' }}>
          <div style={{ width: '48px', height: '48px', borderRadius: 'var(--radius-full)', background: 'var(--brand-tint)', display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--brand)' }}>
            <Sparkles size={24} />
          </div>
          <div style={{ fontSize: '17px', fontWeight: 600, color: 'var(--text-100)' }}>
            Normal RAG vs AMCRAG Comparative Benchmark
          </div>
          <div style={{ fontSize: '13px', color: 'var(--text-300)', maxWidth: '560px', lineHeight: 1.5 }}>
            Evaluate and compare answer correctness, faithfulness, relevancy, retrieval recall@k, and latency using the actual implementations of both systems.
          </div>
          <button
            onClick={handleRunComparison}
            disabled={allDocuments.length === 0}
            className="btn btn-primary"
            style={{ height: '38px', padding: '0 20px', gap: '8px', marginTop: '6px' }}
          >
            <Play size={15} fill="currentColor" />
            <span>Start Comparison Benchmark ({questions.length} Questions)</span>
          </button>
        </div>
      )}

      {/* 2. Results Stage */}
      {result && !isRunning && (
        <>
          {/* Primary Accuracy & Core KPI Cards Grid */}
          <div className="comp-kpi-grid">
            {/* AMCRAG Dynamic Accuracy */}
            <div className="comp-kpi-card" style={{ borderLeft: '4px solid var(--brand)' }}>
              <div className="comp-kpi-label">AMCRAG Accuracy</div>
              <div className="comp-kpi-value-row">
                <span className="comp-kpi-val" style={{ color: 'var(--brand)' }}>
                  {result.summary.amcrag_accuracy_pct != null
                    ? `${result.summary.amcrag_accuracy_pct.toFixed(1)}%`
                    : 'N/A'}
                </span>
                <span className="comp-kpi-pill delta">
                  Target ~95%
                </span>
              </div>
              <div className="comp-kpi-sub">
                Dynamically calculated: correct / {result.summary.evaluated_questions_count}
              </div>
            </div>

            {/* Normal RAG Dynamic Accuracy */}
            <div className="comp-kpi-card" style={{ borderLeft: '4px solid #8A887F' }}>
              <div className="comp-kpi-label">Normal RAG Accuracy</div>
              <div className="comp-kpi-value-row">
                <span className="comp-kpi-val">
                  {result.summary.normal_rag_accuracy_pct != null
                    ? `${result.summary.normal_rag_accuracy_pct.toFixed(1)}%`
                    : 'N/A'}
                </span>
                <span className="comp-kpi-pill tie">
                  Baseline (~85%)
                </span>
              </div>
              <div className="comp-kpi-sub">
                Fixed top-5 dense vector retrieval
              </div>
            </div>

            {/* Accuracy Difference Delta */}
            <div className="comp-kpi-card" style={{ borderLeft: '4px solid #16a34a' }}>
              <div className="comp-kpi-label">Accuracy Advantage</div>
              <div className="comp-kpi-value-row">
                <span className="comp-kpi-val" style={{ color: (result.summary.accuracy_diff_pct ?? 0) >= 0 ? '#16a34a' : 'var(--text-100)' }}>
                  {result.summary.accuracy_diff_pct != null
                    ? `${result.summary.accuracy_diff_pct >= 0 ? '+' : ''}${result.summary.accuracy_diff_pct.toFixed(1)}%`
                    : 'N/A'}
                </span>
                <span className="comp-kpi-pill win">
                  Advantage
                </span>
              </div>
              <div className="comp-kpi-sub">
                Percentage-point difference across benchmark
              </div>
            </div>

            {/* Mean Token F1 Score */}
            <div className="comp-kpi-card">
              <div className="comp-kpi-label">Mean Answer F1</div>
              <div className="comp-kpi-value-row">
                <span className="comp-kpi-val" style={{ fontSize: '20px' }}>
                  {result.summary.amcrag_mean_correctness != null
                    ? `${(result.summary.amcrag_mean_correctness * 100).toFixed(0)}%`
                    : 'N/A'}
                </span>
                <span style={{ fontSize: '13px', color: 'var(--text-300)' }}>
                  vs {result.summary.normal_rag_mean_correctness != null ? `${(result.summary.normal_rag_mean_correctness * 100).toFixed(0)}%` : 'N/A'}
                </span>
              </div>
              <div className="comp-kpi-sub">Token overlap against ground truth</div>
            </div>

            {/* Retrieval Quality */}
            <div className="comp-kpi-card">
              <div className="comp-kpi-label">Retrieval MRR</div>
              <div className="comp-kpi-value-row">
                <span className="comp-kpi-val">
                  {result.amcrag_aggregate.mrr != null
                    ? `${(result.amcrag_aggregate.mrr * 100).toFixed(0)}%`
                    : 'N/A'}
                </span>
                {result.summary.retrieval_mrr_diff != null && (
                  <span className={`comp-kpi-pill ${result.summary.retrieval_mrr_diff >= 0 ? 'win' : 'tie'}`}>
                    {result.summary.retrieval_mrr_diff >= 0 ? `+${(result.summary.retrieval_mrr_diff * 100).toFixed(0)}%` : `${(result.summary.retrieval_mrr_diff * 100).toFixed(0)}%`}
                  </span>
                )}
              </div>
              <div className="comp-kpi-sub">Mean Reciprocal Rank on labeled queries</div>
            </div>

            {/* Latency Delta */}
            <div className="comp-kpi-card">
              <div className="comp-kpi-label">Mean Latency</div>
              <div className="comp-kpi-value-row">
                <span className="comp-kpi-val" style={{ fontSize: '20px' }}>
                  {result.amcrag_performance.mean_latency_ms.toFixed(0)}ms
                </span>
                <span style={{ fontSize: '13px', color: 'var(--text-300)' }}>
                  vs {result.normal_rag_performance.mean_latency_ms.toFixed(0)}ms
                </span>
              </div>
              <div className="comp-kpi-sub">
                Delta: {result.summary.latency_diff_ms >= 0 ? `+${result.summary.latency_diff_ms.toFixed(0)}ms` : `${result.summary.latency_diff_ms.toFixed(0)}ms`}
              </div>
            </div>
          </div>

          {/* Secondary Diagnostic Statistics Strip */}
          <div className="comp-stats-strip">
            <div className="comp-stat-item">
              <span className="comp-stat-val" style={{ color: 'var(--brand)' }}>
                {result.summary.successful_corrective_retrievals ?? 0}
              </span>
              <span className="comp-stat-desc">Successful Corrective Retrievals</span>
            </div>
            <div className="comp-stat-item">
              <span className="comp-stat-val" style={{ color: '#ca8a04' }}>
                {result.summary.questions_requiring_multimodal ?? 0}
              </span>
              <span className="comp-stat-desc">Visual / Table Inquiries</span>
            </div>
            <div className="comp-stat-item">
              <span className="comp-stat-val" style={{ color: '#16a34a' }}>
                {result.summary.initially_failed_recovered ?? 0}
              </span>
              <span className="comp-stat-desc">Failed Retrievals Recovered by CRAG</span>
            </div>
            <div className="comp-stat-item">
              <span className="comp-stat-val" style={{ color: 'var(--text-200)' }}>
                {result.summary.identical_evidence_count ?? 0}
              </span>
              <span className="comp-stat-desc">Identical Evidence (Legitimate agreement)</span>
            </div>
          </div>

          {/* 3. Graphical Comparison Charts */}
          <ComparisonCharts
            amcragAggregate={result.amcrag_aggregate}
            normalRagAggregate={result.normal_rag_aggregate}
            amcragPerformance={result.amcrag_performance}
            normalRagPerformance={result.normal_rag_performance}
            categoryBreakdown={result.category_breakdown}
          />

          {/* Table Category & Failure Filter Controls */}
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '12px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <Filter size={15} style={{ color: 'var(--text-300)' }} />
              <span style={{ fontSize: '13px', fontWeight: 500, color: 'var(--text-200)' }}>
                Filter Results:
              </span>
              <select
                value={categoryFilter}
                onChange={(e) => setCategoryFilter(e.target.value)}
                className="comp-select"
                style={{ height: '32px', fontSize: '12.5px' }}
              >
                <option value="all">All Evaluated Questions ({result.questions.length})</option>
                <option value="factual">Factual Only</option>
                <option value="multihop">Multi-hop Only</option>
                <option value="visual_table">Table / Visual Only</option>
                <option value="unanswerable">Unanswerable Only</option>
                <option value="failures_only">Failures / Divergence Only</option>
                <option value="identical_only">Identical Evidence Only</option>
              </select>
            </div>
          </div>

          {/* 4. Detailed Comparison Table */}
          <ComparisonTable
            questions={result.questions}
            categoryFilter={categoryFilter}
          />
        </>
      )}

      {/* Question Editor Modal */}
      <QuestionEditorModal
        isOpen={isEditorOpen}
        onClose={() => setIsEditorOpen(false)}
        questions={questions}
        onSave={(updated) => setQuestions(updated)}
      />
    </div>
  );
};
