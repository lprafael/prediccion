import React, { useRef, useEffect } from 'react';
import { TrendingUp } from 'lucide-react';
import type { TimelinePoint } from '../types';

interface TimelineChartProps {
  timeline?: TimelinePoint[];
  currentTotal?: number;
}

export const TimelineChart: React.FC<TimelineChartProps> = ({ timeline }) => {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas || !timeline || timeline.length === 0) return;

    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const dpr = window.devicePixelRatio || 1;
    const rect = canvas.getBoundingClientRect();
    canvas.width = rect.width * dpr;
    canvas.height = rect.height * dpr;
    ctx.scale(dpr, dpr);

    const width = rect.width;
    const height = rect.height;

    ctx.clearRect(0, 0, width, height);

    const padding = { top: 25, right: 30, bottom: 35, left: 40 };
    const chartWidth = width - padding.left - padding.right;
    const chartHeight = height - padding.top - padding.bottom;

    const maxMinute = Math.max(...timeline.map((p) => p.minute || 0), 40);
    
    // Determine max Y
    let maxY = 240;
    timeline.forEach((p) => {
      if (p.p95_total && p.p95_total > maxY) maxY = p.p95_total;
      if (p.actual_total && p.actual_total > maxY) maxY = p.actual_total;
    });
    maxY = Math.ceil(maxY / 20) * 20;

    const getX = (min: number) => padding.left + (min / maxMinute) * chartWidth;
    const getY = (val: number) => padding.top + chartHeight - (val / maxY) * chartHeight;

    // Draw horizontal grid lines
    ctx.strokeStyle = '#1e293b';
    ctx.lineWidth = 1;
    for (let i = 0; i <= 5; i++) {
      const yVal = (maxY / 5) * i;
      const y = getY(yVal);
      ctx.beginPath();
      ctx.moveTo(padding.left, y);
      ctx.lineTo(width - padding.right, y);
      ctx.stroke();

      ctx.fillStyle = '#64748b';
      ctx.font = '10px JetBrains Mono';
      ctx.fillText(`${Math.round(yVal)}`, padding.left - 30, y + 3);
    }

    // Draw Quarter dividers
    const quarterMins = [maxMinute / 4, (maxMinute / 4) * 2, (maxMinute / 4) * 3];
    ctx.strokeStyle = 'rgba(255, 255, 255, 0.08)';
    ctx.lineWidth = 1;
    quarterMins.forEach((qm, idx) => {
      const x = getX(qm);
      ctx.beginPath();
      ctx.moveTo(x, padding.top);
      ctx.lineTo(x, padding.top + chartHeight);
      ctx.stroke();

      ctx.fillStyle = '#64748b';
      ctx.font = '10px Outfit';
      ctx.fillText(`Fin Q${idx + 1}`, x - 18, height - 10);
    });

    // 1. Draw Confidence Band (p05 to p95)
    const projectedPoints = timeline.filter((p) => p.p05_total !== undefined && p.p95_total !== undefined);
    if (projectedPoints.length > 0) {
      ctx.beginPath();
      projectedPoints.forEach((p, idx) => {
        const x = getX(p.minute);
        const y = getY(p.p95_total!);
        if (idx === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
      });
      for (let i = projectedPoints.length - 1; i >= 0; i--) {
        const p = projectedPoints[i];
        const x = getX(p.minute);
        const y = getY(p.p05_total!);
        ctx.lineTo(x, y);
      }
      ctx.closePath();
      ctx.fillStyle = 'rgba(255, 119, 0, 0.12)';
      ctx.fill();
    }

    // 2. Draw Baseline Line (Dashed Slate)
    const baselinePoints = timeline.filter((p) => p.baseline_total !== undefined);
    if (baselinePoints.length > 0) {
      ctx.beginPath();
      ctx.strokeStyle = '#64748b';
      ctx.lineWidth = 1.5;
      ctx.setLineDash([4, 4]);
      baselinePoints.forEach((p, idx) => {
        const x = getX(p.minute);
        const y = getY(p.baseline_total!);
        if (idx === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
      });
      ctx.stroke();
      ctx.setLineDash([]);
    }

    // 3. Draw Projected Median Line (Orange)
    const medianPoints = timeline.filter((p) => p.median_total !== undefined);
    if (medianPoints.length > 0) {
      ctx.beginPath();
      ctx.strokeStyle = '#ff7700';
      ctx.lineWidth = 2.5;
      medianPoints.forEach((p, idx) => {
        const x = getX(p.minute);
        const y = getY(p.median_total!);
        if (idx === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
      });
      ctx.stroke();
    }

    // 4. Draw Actual Observed Line (Cyan glow)
    const actualPoints = timeline.filter((p) => p.actual_total !== undefined);
    if (actualPoints.length > 0) {
      ctx.beginPath();
      ctx.strokeStyle = '#38bdf8';
      ctx.lineWidth = 3;
      actualPoints.forEach((p, idx) => {
        const x = getX(p.minute);
        const y = getY(p.actual_total!);
        if (idx === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
      });
      ctx.stroke();

      // Draw dot at latest actual point
      const lastActual = actualPoints[actualPoints.length - 1];
      const dotX = getX(lastActual.minute);
      const dotY = getY(lastActual.actual_total!);

      ctx.beginPath();
      ctx.arc(dotX, dotY, 5, 0, Math.PI * 2);
      ctx.fillStyle = '#38bdf8';
      ctx.fill();
      ctx.strokeStyle = '#fff';
      ctx.lineWidth = 2;
      ctx.stroke();
    }

  }, [timeline]);

  if (!timeline || timeline.length === 0) {
    return (
      <div className="glass-card" style={{ padding: '24px', textAlign: 'center', color: 'var(--text-muted)' }}>
        No hay datos de trayectoria disponibles.
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
          <TrendingUp size={18} color="var(--accent-orange)" />
          Trayectoria Proyectada Minuto a Minuto
        </h3>

        <div style={{ display: 'flex', gap: '14px', fontSize: '0.8rem', color: 'var(--text-secondary)' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <span style={{ width: '12px', height: '3px', background: '#38bdf8', display: 'inline-block' }} />
            <span>Puntos Reales</span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <span style={{ width: '12px', height: '3px', background: '#ff7700', display: 'inline-block' }} />
            <span>Mediana Monte Carlo</span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <span style={{ width: '12px', height: '10px', background: 'rgba(255, 119, 0, 0.25)', display: 'inline-block' }} />
            <span>Banda IC 90%</span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <span style={{ width: '12px', height: '2px', background: '#64748b', borderTop: '1px dashed #64748b', display: 'inline-block' }} />
            <span>Línea Base</span>
          </div>
        </div>
      </div>

      <div style={{ width: '100%', height: '240px', position: 'relative' }}>
        <canvas
          ref={canvasRef}
          style={{ width: '100%', height: '100%', display: 'block' }}
        />
      </div>
    </div>
  );
};
