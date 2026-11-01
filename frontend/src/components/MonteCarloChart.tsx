import React, { useRef, useEffect } from 'react';
import { BarChart3 } from 'lucide-react';
import type { SimulationResult } from '../types';

interface MonteCarloChartProps {
  simulation?: Partial<SimulationResult> | null;
  betLine?: number;
}

export const MonteCarloChart: React.FC<MonteCarloChartProps> = ({ simulation, betLine }) => {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas || !simulation || !simulation.histogram_totals || simulation.histogram_totals.length === 0) return;

    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    // Handle high DPI
    const dpr = window.devicePixelRatio || 1;
    const rect = canvas.getBoundingClientRect();
    canvas.width = rect.width * dpr;
    canvas.height = rect.height * dpr;
    ctx.scale(dpr, dpr);

    const width = rect.width;
    const height = rect.height;

    ctx.clearRect(0, 0, width, height);

    const data = simulation.histogram_totals;
    const minVal = simulation.total_p025 || Math.min(...data);
    const maxVal = simulation.total_p975 || Math.max(...data);
    const range = Math.max(1, maxVal - minVal);

    // Compute bins
    const numBins = 36;
    const bins = new Array(numBins).fill(0);
    data.forEach((val) => {
      if (val >= minVal && val <= maxVal) {
        const binIdx = Math.min(numBins - 1, Math.floor(((val - minVal) / range) * numBins));
        bins[binIdx]++;
      }
    });

    const maxBinCount = Math.max(...bins, 1);
    const padding = { top: 30, right: 25, bottom: 40, left: 30 };
    const chartWidth = width - padding.left - padding.right;
    const chartHeight = height - padding.top - padding.bottom;
    const barWidth = chartWidth / numBins;

    // Draw grid lines
    ctx.strokeStyle = '#1e293b';
    ctx.lineWidth = 1;
    for (let i = 0; i <= 4; i++) {
      const y = padding.top + (chartHeight / 4) * i;
      ctx.beginPath();
      ctx.moveTo(padding.left, y);
      ctx.lineTo(width - padding.right, y);
      ctx.stroke();
    }

    // Draw bars
    bins.forEach((count, i) => {
      const barHeight = (count / maxBinCount) * chartHeight;
      const x = padding.left + i * barWidth;
      const y = padding.top + chartHeight - barHeight;

      const binVal = minVal + (i + 0.5) * (range / numBins);

      // Color based on betting line if present
      let grad = ctx.createLinearGradient(0, y, 0, padding.top + chartHeight);
      if (betLine && binVal > betLine) {
        grad.addColorStop(0, '#10b981'); // Over (Green)
        grad.addColorStop(1, 'rgba(16, 185, 129, 0.2)');
      } else if (betLine && binVal < betLine) {
        grad.addColorStop(0, '#f43f5e'); // Under (Red)
        grad.addColorStop(1, 'rgba(244, 63, 94, 0.2)');
      } else {
        grad.addColorStop(0, '#ff7700'); // Neutral Orange
        grad.addColorStop(1, 'rgba(255, 119, 0, 0.15)');
      }

      ctx.fillStyle = grad;
      ctx.fillRect(x + 1, y, Math.max(1, barWidth - 2), barHeight);
    });

    // Draw median line
    if (simulation.total_median) {
      const medianX = padding.left + ((simulation.total_median - minVal) / range) * chartWidth;
      ctx.strokeStyle = '#ff9933';
      ctx.lineWidth = 2;
      ctx.setLineDash([5, 4]);
      ctx.beginPath();
      ctx.moveTo(medianX, padding.top);
      ctx.lineTo(medianX, padding.top + chartHeight);
      ctx.stroke();
      ctx.setLineDash([]);

      ctx.fillStyle = '#ff9933';
      ctx.font = 'bold 11px Outfit';
      ctx.fillText(`Med: ${simulation.total_median}`, medianX - 25, padding.top - 8);
    }

    // Draw betting line if provided
    if (betLine && betLine >= minVal && betLine <= maxVal) {
      const lineX = padding.left + ((betLine - minVal) / range) * chartWidth;
      ctx.strokeStyle = '#38bdf8';
      ctx.lineWidth = 2.5;
      ctx.beginPath();
      ctx.moveTo(lineX, padding.top);
      ctx.lineTo(lineX, padding.top + chartHeight);
      ctx.stroke();

      ctx.fillStyle = '#38bdf8';
      ctx.font = 'bold 11px Outfit';
      ctx.fillText(`Línea: ${betLine}`, lineX + 5, padding.top + 14);
    }

    // X-axis labels
    ctx.fillStyle = '#94a3b8';
    ctx.font = '10px JetBrains Mono';
    ctx.fillText(`${Math.round(minVal)} pts`, padding.left, height - 10);
    ctx.fillText(`${Math.round(minVal + range / 2)} pts`, padding.left + chartWidth / 2 - 20, height - 10);
    ctx.fillText(`${Math.round(maxVal)} pts`, width - padding.right - 45, height - 10);

  }, [simulation, betLine]);

  if (!simulation) {
    return (
      <div className="glass-card" style={{ padding: '24px', textAlign: 'center', color: 'var(--text-muted)' }}>
        No hay datos de simulación disponibles.
      </div>
    );
  }

  return (
    <div className="glass-card" style={{ padding: '22px' }}>
      <div style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        marginBottom: '14px',
        flexWrap: 'wrap',
        gap: '10px'
      }}>
        <h3 style={{ fontSize: '1.15rem', fontWeight: 700, display: 'flex', alignItems: 'center', gap: '8px' }}>
          <BarChart3 size={18} color="var(--accent-orange)" />
          Distribución de Totales Monte Carlo (5.000 Sims)
        </h3>

        <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
          <span className="badge-tag" style={{ background: 'rgba(255, 119, 0, 0.15)', color: '#ff9933' }}>
            Media: {simulation.total_mean?.toFixed(1)} pts
          </span>
          <span className="badge-tag" style={{ background: 'rgba(56, 189, 248, 0.15)', color: '#38bdf8' }}>
            Desv: ±{simulation.total_std?.toFixed(1)}
          </span>
          <span className="badge-tag" style={{ background: 'rgba(16, 185, 129, 0.15)', color: '#10b981' }}>
            IC 90%: [{simulation.total_p05?.toFixed(0)} - {simulation.total_p95?.toFixed(0)}]
          </span>
        </div>
      </div>

      <div style={{ width: '100%', height: '220px', position: 'relative' }}>
        <canvas
          ref={canvasRef}
          style={{ width: '100%', height: '100%', display: 'block' }}
        />
      </div>

      <div style={{
        marginTop: '12px',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        gap: '20px',
        fontSize: '0.78rem',
        color: 'var(--text-secondary)'
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
          <span style={{ width: '12px', height: '12px', background: '#ff7700', borderRadius: '2px' }} />
          <span>Distribución Probabilística</span>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
          <span style={{ width: '12px', height: '2px', background: '#ff9933', display: 'inline-block' }} />
          <span>Mediana</span>
        </div>
        {betLine && (
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <span style={{ width: '12px', height: '2px', background: '#38bdf8', display: 'inline-block' }} />
            <span>Línea Apuesta ({betLine})</span>
          </div>
        )}
      </div>
    </div>
  );
};
