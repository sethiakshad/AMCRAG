/**
 * src/components/comparison/ComparisonCharts.tsx
 * Pure SVG responsive charts comparing Normal RAG vs AMCRAG.
 * Zero external heavy dependencies, 100% React 19 compatible.
 */

import React from 'react';
import {
  AggregateQualityMetrics,
  CategoryBreakdown,
  PerformanceMetrics,
} from '../../types/comparison';

interface ComparisonChartsProps {
  amcragAggregate: AggregateQualityMetrics;
  normalRagAggregate: AggregateQualityMetrics;
  amcragPerformance: PerformanceMetrics;
  normalRagPerformance: PerformanceMetrics;
  categoryBreakdown: CategoryBreakdown[];
}

const COLOR_AMCRAG = 'var(--brand)';
const COLOR_NORMAL = '#8A887F';

export const ComparisonCharts: React.FC<ComparisonChartsProps> = ({
  amcragAggregate,
  normalRagAggregate,
  amcragPerformance,
  normalRagPerformance,
  categoryBreakdown,
}) => {
  // A. Answer Quality Metrics List
  const qualityMetrics = [
    {
      name: 'Correctness',
      amc: amcragAggregate.mean_answer_correctness,
      norm: normalRagAggregate.mean_answer_correctness,
    },
    {
      name: 'Faithfulness',
      amc: amcragAggregate.mean_faithfulness,
      norm: normalRagAggregate.mean_faithfulness,
    },
    {
      name: 'Relevancy',
      amc: amcragAggregate.mean_answer_relevancy,
      norm: normalRagAggregate.mean_answer_relevancy,
    },
    {
      name: 'Context Precision',
      amc: amcragAggregate.mean_context_precision,
      norm: normalRagAggregate.mean_context_precision,
    },
    {
      name: 'Context Recall',
      amc: amcragAggregate.mean_context_recall,
      norm: normalRagAggregate.mean_context_recall,
    },
  ];

  // B. Retrieval Quality Metrics List
  const retrievalMetrics = [
    { name: 'Recall@1', amc: amcragAggregate.recall_at_1, norm: normalRagAggregate.recall_at_1 },
    { name: 'Recall@3', amc: amcragAggregate.recall_at_3, norm: normalRagAggregate.recall_at_3 },
    { name: 'Recall@5', amc: amcragAggregate.recall_at_5, norm: normalRagAggregate.recall_at_5 },
    { name: 'MRR', amc: amcragAggregate.mrr, norm: normalRagAggregate.mrr },
  ];

  // C. Latency Breakdown
  const latencyMetrics = [
    {
      name: 'Mean Total',
      amc: amcragPerformance.mean_latency_ms,
      norm: normalRagPerformance.mean_latency_ms,
    },
    {
      name: 'Median Total',
      amc: amcragPerformance.median_latency_ms,
      norm: normalRagPerformance.median_latency_ms,
    },
    {
      name: 'Retrieval',
      amc: amcragPerformance.mean_retrieval_latency_ms,
      norm: normalRagPerformance.mean_retrieval_latency_ms,
    },
    {
      name: 'Generation',
      amc: amcragPerformance.mean_generation_latency_ms,
      norm: normalRagPerformance.mean_generation_latency_ms,
    },
  ];

  const maxLatency = Math.max(
    1,
    ...latencyMetrics.map((m) => Math.max(m.amc || 0, m.norm || 0))
  );

  return (
    <div className="comp-charts-grid">
      {/* 1. Answer Quality Grouped Bar Chart */}
      <div className="comp-chart-card">
        <div className="comp-chart-header">
          <div className="comp-chart-title">
            <span>Answer Quality</span>
            <span style={{ fontSize: '11px', color: 'var(--text-300)', fontWeight: 400 }}>
              (0.0 – 1.0 Normalized Scale)
            </span>
          </div>
          <div className="comp-chart-legend">
            <div className="comp-legend-item">
              <span className="comp-legend-dot" style={{ background: COLOR_AMCRAG }} />
              <span>AMCRAG</span>
            </div>
            <div className="comp-legend-item">
              <span className="comp-legend-dot" style={{ background: COLOR_NORMAL }} />
              <span>Normal RAG</span>
            </div>
          </div>
        </div>

        <div className="comp-svg-container">
          <svg viewBox="0 0 520 220" style={{ width: '100%', height: 'auto', display: 'block' }}>
            {/* Grid lines */}
            {[0, 0.25, 0.5, 0.75, 1.0].map((tick) => {
              const y = 170 - tick * 140;
              return (
                <g key={tick}>
                  <line x1="40" y1={y} x2="510" y2={y} stroke="var(--border-100)" strokeDasharray="3 3" />
                  <text x="32" y={y + 4} fill="var(--text-300)" fontSize="10" textAnchor="end">
                    {Math.round(tick * 100)}%
                  </text>
                </g>
              );
            })}

            {/* Bars */}
            {qualityMetrics.map((item, idx) => {
              const groupX = 65 + idx * 90;
              const amcVal = item.amc !== null && item.amc !== undefined ? item.amc : 0;
              const normVal = item.norm !== null && item.norm !== undefined ? item.norm : 0;

              const amcHeight = amcVal * 140;
              const normHeight = normVal * 140;

              return (
                <g key={item.name}>
                  {/* Normal RAG bar */}
                  <rect
                    x={groupX}
                    y={170 - normHeight}
                    width="26"
                    height={normHeight}
                    fill={COLOR_NORMAL}
                    rx="3"
                  >
                    <title>{`Normal RAG ${item.name}: ${(normVal * 100).toFixed(1)}%`}</title>
                  </rect>

                  {/* AMCRAG bar */}
                  <rect
                    x={groupX + 30}
                    y={170 - amcHeight}
                    width="26"
                    height={amcHeight}
                    fill={COLOR_AMCRAG}
                    rx="3"
                  >
                    <title>{`AMCRAG ${item.name}: ${(amcVal * 100).toFixed(1)}%`}</title>
                  </rect>

                  {/* Metric Label */}
                  <text
                    x={groupX + 28}
                    y="192"
                    fill="var(--text-200)"
                    fontSize="10.5"
                    fontWeight="500"
                    textAnchor="middle"
                  >
                    {item.name.length > 11 ? item.name.slice(0, 10) + '.' : item.name}
                  </text>
                  <text
                    x={groupX + 28}
                    y="206"
                    fill="var(--text-300)"
                    fontSize="9.5"
                    textAnchor="middle"
                  >
                    {item.amc !== null ? `${(amcVal * 100).toFixed(0)}% vs ${(normVal * 100).toFixed(0)}%` : 'N/A'}
                  </text>
                </g>
              );
            })}
          </svg>
        </div>
      </div>

      {/* 2. Retrieval Quality Bar / Line Chart */}
      <div className="comp-chart-card">
        <div className="comp-chart-header">
          <div className="comp-chart-title">
            <span>Retrieval Quality</span>
            <span style={{ fontSize: '11px', color: 'var(--text-300)', fontWeight: 400 }}>
              (Recall@K & MRR)
            </span>
          </div>
          <div className="comp-chart-legend">
            <div className="comp-legend-item">
              <span className="comp-legend-dot" style={{ background: COLOR_AMCRAG }} />
              <span>AMCRAG</span>
            </div>
            <div className="comp-legend-item">
              <span className="comp-legend-dot" style={{ background: COLOR_NORMAL }} />
              <span>Normal RAG</span>
            </div>
          </div>
        </div>

        <div className="comp-svg-container">
          <svg viewBox="0 0 520 220" style={{ width: '100%', height: 'auto', display: 'block' }}>
            {[0, 0.25, 0.5, 0.75, 1.0].map((tick) => {
              const y = 170 - tick * 140;
              return (
                <g key={tick}>
                  <line x1="40" y1={y} x2="510" y2={y} stroke="var(--border-100)" strokeDasharray="3 3" />
                  <text x="32" y={y + 4} fill="var(--text-300)" fontSize="10" textAnchor="end">
                    {Math.round(tick * 100)}%
                  </text>
                </g>
              );
            })}

            {retrievalMetrics.map((item, idx) => {
              const groupX = 80 + idx * 105;
              const amcVal = item.amc !== null && item.amc !== undefined ? item.amc : 0;
              const normVal = item.norm !== null && item.norm !== undefined ? item.norm : 0;

              const amcHeight = amcVal * 140;
              const normHeight = normVal * 140;

              return (
                <g key={item.name}>
                  <rect
                    x={groupX}
                    y={170 - normHeight}
                    width="28"
                    height={normHeight}
                    fill={COLOR_NORMAL}
                    rx="3"
                  />
                  <rect
                    x={groupX + 32}
                    y={170 - amcHeight}
                    width="28"
                    height={amcHeight}
                    fill={COLOR_AMCRAG}
                    rx="3"
                  />
                  <text
                    x={groupX + 30}
                    y="192"
                    fill="var(--text-200)"
                    fontSize="11"
                    fontWeight="500"
                    textAnchor="middle"
                  >
                    {item.name}
                  </text>
                  <text
                    x={groupX + 30}
                    y="206"
                    fill="var(--text-300)"
                    fontSize="9.5"
                    textAnchor="middle"
                  >
                    {item.amc !== null ? `${(amcVal * 100).toFixed(0)}% vs ${(normVal * 100).toFixed(0)}%` : 'N/A'}
                  </text>
                </g>
              );
            })}
          </svg>
        </div>
      </div>

      {/* 3. Latency & Efficiency Grouped Bar Chart */}
      <div className="comp-chart-card">
        <div className="comp-chart-header">
          <div className="comp-chart-title">
            <span>Latency Performance</span>
            <span style={{ fontSize: '11px', color: 'var(--text-300)', fontWeight: 400 }}>
              (Milliseconds breakdown)
            </span>
          </div>
          <div className="comp-chart-legend">
            <div className="comp-legend-item">
              <span className="comp-legend-dot" style={{ background: COLOR_AMCRAG }} />
              <span>AMCRAG</span>
            </div>
            <div className="comp-legend-item">
              <span className="comp-legend-dot" style={{ background: COLOR_NORMAL }} />
              <span>Normal RAG</span>
            </div>
          </div>
        </div>

        <div className="comp-svg-container">
          <svg viewBox="0 0 520 220" style={{ width: '100%', height: 'auto', display: 'block' }}>
            {[0, 0.25, 0.5, 0.75, 1.0].map((tick) => {
              const y = 170 - tick * 140;
              const latLabel = Math.round(tick * maxLatency);
              return (
                <g key={tick}>
                  <line x1="45" y1={y} x2="510" y2={y} stroke="var(--border-100)" strokeDasharray="3 3" />
                  <text x="38" y={y + 4} fill="var(--text-300)" fontSize="9.5" textAnchor="end">
                    {latLabel}ms
                  </text>
                </g>
              );
            })}

            {latencyMetrics.map((item, idx) => {
              const groupX = 75 + idx * 108;
              const amcHeight = maxLatency > 0 ? (item.amc / maxLatency) * 140 : 0;
              const normHeight = maxLatency > 0 ? (item.norm / maxLatency) * 140 : 0;

              return (
                <g key={item.name}>
                  <rect
                    x={groupX}
                    y={170 - normHeight}
                    width="28"
                    height={normHeight}
                    fill={COLOR_NORMAL}
                    rx="3"
                  >
                    <title>{`Normal RAG: ${item.norm.toFixed(1)}ms`}</title>
                  </rect>
                  <rect
                    x={groupX + 32}
                    y={170 - amcHeight}
                    width="28"
                    height={amcHeight}
                    fill={COLOR_AMCRAG}
                    rx="3"
                  >
                    <title>{`AMCRAG: ${item.amc.toFixed(1)}ms`}</title>
                  </rect>
                  <text
                    x={groupX + 30}
                    y="192"
                    fill="var(--text-200)"
                    fontSize="11"
                    fontWeight="500"
                    textAnchor="middle"
                  >
                    {item.name}
                  </text>
                  <text
                    x={groupX + 30}
                    y="206"
                    fill="var(--text-300)"
                    fontSize="9.5"
                    textAnchor="middle"
                  >
                    {`${item.amc.toFixed(0)}ms vs ${item.norm.toFixed(0)}ms`}
                  </text>
                </g>
              );
            })}
          </svg>
        </div>
      </div>

      {/* 4. Question Category Analysis Matrix / Heatmap */}
      <div className="comp-chart-card">
        <div className="comp-chart-header">
          <div className="comp-chart-title">
            <span>Category Performance Analysis</span>
          </div>
          <div style={{ fontSize: '12px', color: 'var(--text-300)' }}>
            Breakdown across reasoning types
          </div>
        </div>

        <table className="comp-category-matrix">
          <thead>
            <tr>
              <th>Category</th>
              <th>Count</th>
              <th>Normal RAG Correctness</th>
              <th>AMCRAG Correctness</th>
              <th>AMCRAG Faithfulness</th>
              <th>Latency Delta</th>
            </tr>
          </thead>
          <tbody>
            {categoryBreakdown.length === 0 ? (
              <tr>
                <td colSpan={6} style={{ textAlign: 'center', color: 'var(--text-300)', padding: '24px' }}>
                  No evaluated categories yet.
                </td>
              </tr>
            ) : (
              categoryBreakdown.map((row) => {
                const normPct = row.normal_rag_correctness != null ? `${(row.normal_rag_correctness * 100).toFixed(0)}%` : 'N/A';
                const amcPct = row.amcrag_correctness != null ? `${(row.amcrag_correctness * 100).toFixed(0)}%` : 'N/A';
                const amcFaith = row.amcrag_faithfulness != null ? `${(row.amcrag_faithfulness * 100).toFixed(0)}%` : 'N/A';
                const deltaLat = Math.round(row.amcrag_latency_ms - row.normal_rag_latency_ms);

                return (
                  <tr key={row.category}>
                    <td>
                      <span className={`comp-badge ${row.category}`}>
                        {row.category.replace('_', ' ')}
                      </span>
                    </td>
                    <td>{row.count}</td>
                    <td style={{ fontWeight: 500 }}>{normPct}</td>
                    <td style={{ fontWeight: 600, color: 'var(--brand)' }}>{amcPct}</td>
                    <td>{amcFaith}</td>
                    <td style={{ fontFamily: 'var(--font-mono)', fontSize: '12px' }}>
                      {deltaLat >= 0 ? `+${deltaLat}ms` : `${deltaLat}ms`}
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
};
