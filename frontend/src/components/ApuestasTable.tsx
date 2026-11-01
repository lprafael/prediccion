import React, { useState, useEffect, useCallback } from "react";
import { Edit3, Trash2, TrendingUp, TrendingDown, Save, X, RefreshCw } from "lucide-react";
import { getApuestasPartido, updateApuesta, deleteApuesta } from "../api/client";
import type { Apuesta } from "../types";

interface ApuestasTableProps {
  partidoId: number;
  onChanged?: () => void;
}

interface EditState {
  tipo_apuesta: string;
  linea: number;
  cuota: number;
  monto: number;
  notas: string;
}

const BADGE: Record<string, { bg: string; color: string; label: string }> = {
  PENDIENTE: { bg: "rgba(251,191,36,0.15)", color: "#fbbf24", label: "Pendiente" },
  GANADA:    { bg: "rgba(16,185,129,0.15)",  color: "#10b981", label: "Ganada"   },
  PERDIDA:   { bg: "rgba(244,63,94,0.15)",   color: "#f43f5e", label: "Perdida"  },
  PUSH:      { bg: "rgba(148,163,184,0.15)", color: "#94a3b8", label: "Push"     },
};

export const ApuestasTable: React.FC<ApuestasTableProps> = ({ partidoId, onChanged }) => {
  const [apuestas, setApuestas] = useState<Apuesta[]>([]);
  const [loading, setLoading] = useState(false);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [editForm, setEditForm] = useState<EditState | null>(null);
  const [saving, setSaving] = useState(false);
  const [deletingId, setDeletingId] = useState<number | null>(null);
  const [confirmDeleteId, setConfirmDeleteId] = useState<number | null>(null);
  const [msg, setMsg] = useState<{ text: string; ok: boolean } | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const data = await getApuestasPartido(partidoId);
      setApuestas(data as unknown as Apuesta[]);
    } catch (e: any) {
      setMsg({ text: `Error al cargar apuestas: ${e.message}`, ok: false });
    } finally {
      setLoading(false);
    }
  }, [partidoId]);

  useEffect(() => { load(); }, [load]);

  const startEdit = (a: Apuesta) => {
    setEditingId(a.id);
    setEditForm({
      tipo_apuesta: a.tipo_apuesta || "OVER",
      linea: Number(a.linea) || 0,
      cuota: Number(a.cuota) || 1.90,
      monto: Number(a.monto) || 100000,
      notas: a.notas || ""
    });
    setMsg(null);
  };

  const cancelEdit = () => { setEditingId(null); setEditForm(null); };

  const saveEdit = async () => {
    if (!editingId || !editForm) return;
    if (editForm.monto <= 0) {
      setMsg({ text: "El monto debe ser mayor a 0", ok: false });
      return;
    }
    if (editForm.cuota <= 1.0) {
      setMsg({ text: "La cuota debe ser mayor a 1.0", ok: false });
      return;
    }

    setSaving(true);
    try {
      await updateApuesta(editingId, {
        tipo_apuesta: editForm.tipo_apuesta,
        linea: editForm.linea,
        cuota: editForm.cuota,
        monto: editForm.monto,
        notas: editForm.notas,
      });
      setMsg({ text: "Apuesta actualizada correctamente", ok: true });
      setEditingId(null);
      setEditForm(null);
      await load();
      if (onChanged) onChanged();
      setTimeout(() => setMsg(null), 3000);
    } catch (e: any) {
      setMsg({ text: `Error: ${e.message}`, ok: false });
    } finally {
      setSaving(false);
    }
  };

  const doDelete = async () => {
    if (!confirmDeleteId) return;
    setDeletingId(confirmDeleteId);
    setConfirmDeleteId(null);
    try {
      await deleteApuesta(confirmDeleteId);
      setMsg({ text: "Apuesta eliminada", ok: true });
      await load();
      if (onChanged) onChanged();
      setTimeout(() => setMsg(null), 3000);
    } catch (e: any) {
      setMsg({ text: `Error: ${e.message}`, ok: false });
    } finally {
      setDeletingId(null);
    }
  };

  if (apuestas.length === 0 && !loading) return null;

  const inputStyle = (color: string): React.CSSProperties => ({
    width: "100%", background: "transparent", border: "none",
    color, fontSize: "1rem", fontWeight: 800, outline: "none", fontFamily: "JetBrains Mono",
  });

  return (
    <div className="glass-card" style={{ padding: "20px" }}>
      {/* Header */}
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "16px", flexWrap: "wrap", gap: "8px" }}>
        <h3 style={{ fontSize: "1.05rem", fontWeight: 800, color: "var(--text-primary)", display: "flex", alignItems: "center", gap: "8px", margin: 0 }}>
          Apuestas Registradas para este Partido
          <span style={{ fontSize: "0.72rem", background: "rgba(255,255,255,0.08)", color: "var(--text-muted)", padding: "2px 8px", borderRadius: "12px", fontWeight: 600 }}>
            {apuestas.length}
          </span>
        </h3>
        <button
          onClick={load} disabled={loading}
          style={{ display: "flex", alignItems: "center", gap: "5px", background: "rgba(255,255,255,0.05)", border: "1px solid var(--border-subtle)", borderRadius: "6px", padding: "4px 10px", cursor: "pointer", color: "var(--text-muted)", fontSize: "0.75rem", fontWeight: 700 }}
        >
          <RefreshCw size={12} />
          Actualizar
        </button>
      </div>

      {/* Mensaje */}
      {msg && (
        <div style={{ marginBottom: "12px", padding: "8px 12px", borderRadius: "7px", fontSize: "0.82rem", fontWeight: 700, background: msg.ok ? "rgba(16,185,129,0.12)" : "rgba(239,68,68,0.1)", border: `1px solid ${msg.ok ? "#10b981" : "#ef4444"}`, color: msg.ok ? "#10b981" : "#f87171" }}>
          {msg.ok ? "✅" : "❌"} {msg.text}
        </div>
      )}

      {/* Confirmacion eliminar */}
      {confirmDeleteId && (
        <div style={{ marginBottom: "12px", padding: "12px 16px", borderRadius: "8px", background: "rgba(239,68,68,0.1)", border: "1px solid #ef4444", display: "flex", alignItems: "center", justifyContent: "space-between", gap: "12px", flexWrap: "wrap" }}>
          <span style={{ color: "#f87171", fontWeight: 700, fontSize: "0.85rem" }}>
            ¿Eliminar esta apuesta? Esta acción no se puede deshacer.
          </span>
          <div style={{ display: "flex", gap: "8px" }}>
            <button onClick={() => setConfirmDeleteId(null)} style={{ padding: "5px 14px", borderRadius: "6px", border: "1px solid var(--border-subtle)", background: "transparent", color: "var(--text-muted)", cursor: "pointer", fontSize: "0.8rem", fontWeight: 700 }}>
              Cancelar
            </button>
            <button onClick={doDelete} style={{ padding: "5px 14px", borderRadius: "6px", border: "none", background: "#ef4444", color: "#fff", cursor: "pointer", fontSize: "0.8rem", fontWeight: 700 }}>
              Sí, eliminar
            </button>
          </div>
        </div>
      )}

      {/* Lista */}
      <div style={{ display: "flex", flexDirection: "column", gap: "10px" }}>
        {loading && apuestas.length === 0 && (
          <div style={{ textAlign: "center", color: "var(--text-muted)", padding: "20px", fontSize: "0.85rem" }}>Cargando apuestas...</div>
        )}

        {apuestas.map(a => {
          const isEditing = editingId === a.id;
          const badge = BADGE[a.resultado] || BADGE.PENDIENTE;
          const isOver = (a.tipo_apuesta || "").toUpperCase().includes("OVER");

          return (
            <div key={a.id} style={{ background: isEditing ? "rgba(251,191,36,0.05)" : "rgba(0,0,0,0.25)", border: `1px solid ${isEditing ? "#fbbf24" : "var(--border-subtle)"}`, borderRadius: "10px", padding: "14px 16px", transition: "border-color 0.2s" }}>

              {/* Vista normal */}
              {!isEditing && (
                <div style={{ display: "flex", alignItems: "flex-start", gap: "14px", flexWrap: "wrap" }}>
                  {/* Tipo/Linea */}
                  <div style={{ minWidth: "110px" }}>
                    <div style={{ display: "flex", alignItems: "center", gap: "5px", marginBottom: "2px" }}>
                      {isOver ? <TrendingUp size={14} color="#10b981" /> : <TrendingDown size={14} color="#f43f5e" />}
                      <span style={{ fontWeight: 900, fontSize: "0.9rem", color: isOver ? "#10b981" : "#f43f5e" }}>
                        {a.tipo_apuesta || "--"}
                      </span>
                    </div>
                    <span style={{ fontSize: "0.78rem", color: "var(--text-secondary)" }}>
                      Línea: <strong style={{ color: "#fff", fontFamily: "JetBrains Mono" }}>{a.linea ?? "--"}</strong>
                    </span>
                  </div>

                  {/* Cuota/Monto */}
                  <div style={{ minWidth: "170px" }}>
                    <div style={{ fontSize: "0.72rem", color: "var(--text-muted)", marginBottom: "2px" }}>Cuota / Monto</div>
                    <span style={{ fontWeight: 800, fontFamily: "JetBrains Mono", color: "var(--accent-gold)", fontSize: "0.9rem" }}>
                      {(Number(a.cuota) || 0).toFixed(2)}
                    </span>
                    <span style={{ color: "var(--text-muted)", margin: "0 5px" }}>·</span>
                    <span style={{ fontWeight: 700, color: "var(--accent-orange)", fontFamily: "JetBrains Mono", fontSize: "0.88rem" }}>
                      Gs. {(Number(a.monto) || 0).toLocaleString("es-PY")}
                    </span>
                  </div>

                  {/* Prob/EV */}
                  {(a.prob_modelo != null || a.ev_estimado != null) && (
                    <div style={{ minWidth: "130px" }}>
                      <div style={{ fontSize: "0.72rem", color: "var(--text-muted)", marginBottom: "2px" }}>Prob. modelo / EV</div>
                      {a.prob_modelo != null && (
                        <span style={{ fontWeight: 700, color: "#a78bfa", fontSize: "0.85rem" }}>
                          {((Number(a.prob_modelo) || 0) * 100).toFixed(1)}%
                        </span>
                      )}
                      {a.ev_estimado != null && (
                        <>
                          <span style={{ color: "var(--text-muted)", margin: "0 4px" }}>·</span>
                          <span style={{ fontWeight: 700, color: (Number(a.ev_estimado) || 0) >= 0 ? "#10b981" : "#f87171", fontSize: "0.85rem" }}>
                            {(Number(a.ev_estimado) || 0) >= 0 ? "+" : ""}{(Number(a.ev_estimado) || 0).toFixed(1)}%
                          </span>
                        </>
                      )}
                    </div>
                  )}

                  {/* Q/Modo */}
                  <div style={{ minWidth: "100px" }}>
                    <div style={{ fontSize: "0.72rem", color: "var(--text-muted)", marginBottom: "2px" }}>Cuarto / Modo</div>
                    <span style={{ fontSize: "0.82rem", color: "var(--text-secondary)" }}>Q{a.momento_cuarto ?? "?"}</span>
                    <span style={{ margin: "0 4px", color: "var(--text-muted)" }}>·</span>
                    <span style={{ fontSize: "0.75rem", fontWeight: 700, color: a.es_ficticia ? "var(--accent-orange)" : "#10b981" }}>
                      {a.es_ficticia ? "Ficticia" : "Real"}
                    </span>
                  </div>

                  {/* Resultado */}
                  <div style={{ minWidth: "85px" }}>
                    <div style={{ fontSize: "0.72rem", color: "var(--text-muted)", marginBottom: "4px" }}>Resultado</div>
                    <span style={{ fontSize: "0.75rem", fontWeight: 800, background: badge.bg, color: badge.color, padding: "2px 8px", borderRadius: "5px" }}>
                      {badge.label}
                    </span>
                  </div>

                  {/* Notas */}
                  {a.notas && (
                    <div style={{ flex: 1, minWidth: "180px" }}>
                      <div style={{ fontSize: "0.72rem", color: "var(--text-muted)", marginBottom: "2px" }}>Notas</div>
                      <span style={{ fontSize: "0.76rem", color: "var(--text-secondary)", fontStyle: "italic", wordBreak: "break-word" }}>
                        {a.notas}
                      </span>
                    </div>
                  )}

                  {/* Acciones */}
                  <div style={{ marginLeft: "auto", display: "flex", gap: "6px", alignSelf: "center", flexShrink: 0 }}>
                    <button
                      onClick={() => startEdit(a)}
                      style={{ display: "flex", alignItems: "center", gap: "4px", padding: "5px 10px", borderRadius: "6px", border: "1px solid rgba(251,191,36,0.3)", background: "rgba(251,191,36,0.08)", color: "#fbbf24", cursor: "pointer", fontSize: "0.75rem", fontWeight: 700 }}
                    >
                      <Edit3 size={12} /> Editar
                    </button>
                    <button
                      onClick={() => setConfirmDeleteId(a.id)}
                      disabled={deletingId === a.id}
                      style={{ display: "flex", alignItems: "center", gap: "4px", padding: "5px 10px", borderRadius: "6px", border: "1px solid rgba(239,68,68,0.3)", background: "rgba(239,68,68,0.08)", color: "#f87171", cursor: "pointer", fontSize: "0.75rem", fontWeight: 700 }}
                    >
                      <Trash2 size={12} /> {deletingId === a.id ? "..." : "Eliminar"}
                    </button>
                  </div>
                </div>
              )}

              {/* Formulario de Edición */}
              {isEditing && editForm && (
                <div>
                  <div style={{ fontSize: "0.78rem", color: "#fbbf24", fontWeight: 800, marginBottom: "12px" }}>
                    Editando apuesta #{a.id}
                  </div>

                  {/* Tipo */}
                  <div style={{ marginBottom: "12px" }}>
                    <label style={{ fontSize: "0.7rem", color: "var(--text-muted)", fontWeight: 700, display: "block", marginBottom: "6px" }}>TIPO</label>
                    <div style={{ display: "flex", gap: "8px" }}>
                      {["OVER", "UNDER"].map(t => (
                        <button
                          key={t} type="button"
                          onClick={() => setEditForm(f => f ? { ...f, tipo_apuesta: t } : f)}
                          style={{
                            padding: "6px 16px",
                            borderRadius: "6px",
                            cursor: "pointer",
                            fontWeight: 800,
                            fontSize: "0.82rem",
                            border: `2px solid ${editForm.tipo_apuesta === t ? (t === "OVER" ? "#10b981" : "#f43f5e") : "var(--border-subtle)"}`,
                            background: editForm.tipo_apuesta === t ? (t === "OVER" ? "rgba(16,185,129,0.15)" : "rgba(244,63,94,0.15)") : "transparent",
                            color: editForm.tipo_apuesta === t ? (t === "OVER" ? "#10b981" : "#f43f5e") : "var(--text-muted)"
                          }}
                        >
                          {t}
                        </button>
                      ))}
                    </div>
                  </div>

                  {/* Linea / Cuota / Monto */}
                  <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: "10px", marginBottom: "12px" }}>
                    <div style={{ background: "var(--bg-surface-elevated)", padding: "8px 12px", borderRadius: "8px" }}>
                      <label style={{ fontSize: "0.68rem", color: "var(--text-muted)", fontWeight: 700, display: "block", marginBottom: "3px" }}>LÍNEA</label>
                      <input
                        type="number"
                        step={0.5}
                        value={editForm.linea}
                        onChange={e => setEditForm(f => f ? { ...f, linea: Number(e.target.value) } : f)}
                        style={inputStyle("#fff")}
                      />
                    </div>
                    <div style={{ background: "var(--bg-surface-elevated)", padding: "8px 12px", borderRadius: "8px" }}>
                      <label style={{ fontSize: "0.68rem", color: "var(--text-muted)", fontWeight: 700, display: "block", marginBottom: "3px" }}>CUOTA</label>
                      <input
                        type="number"
                        step={0.01}
                        value={editForm.cuota}
                        onChange={e => setEditForm(f => f ? { ...f, cuota: Number(e.target.value) } : f)}
                        style={inputStyle("var(--accent-gold)")}
                      />
                    </div>
                    <div style={{ background: "var(--bg-surface-elevated)", padding: "8px 12px", borderRadius: "8px" }}>
                      <label style={{ fontSize: "0.68rem", color: "var(--text-muted)", fontWeight: 700, display: "block", marginBottom: "3px" }}>MONTO (Gs.)</label>
                      <input
                        type="number"
                        step={10000}
                        value={editForm.monto}
                        onChange={e => setEditForm(f => f ? { ...f, monto: Number(e.target.value) } : f)}
                        style={inputStyle("var(--accent-orange)")}
                      />
                    </div>
                  </div>

                  {/* Notas */}
                  <div style={{ marginBottom: "14px" }}>
                    <label style={{ fontSize: "0.7rem", color: "var(--text-muted)", fontWeight: 700, display: "block", marginBottom: "4px" }}>NOTAS</label>
                    <input
                      type="text"
                      value={editForm.notas}
                      onChange={e => setEditForm(f => f ? { ...f, notas: e.target.value } : f)}
                      style={{ width: "100%", background: "rgba(0,0,0,0.3)", border: "1px solid var(--border-subtle)", borderRadius: "6px", color: "#fff", padding: "7px 10px", fontSize: "0.82rem", outline: "none" }}
                    />
                  </div>

                  {/* Botones */}
                  <div style={{ display: "flex", gap: "8px" }}>
                    <button
                      onClick={saveEdit}
                      disabled={saving}
                      style={{ display: "flex", alignItems: "center", gap: "6px", padding: "7px 18px", borderRadius: "7px", border: "none", background: "linear-gradient(135deg,#10b981,#059669)", color: "#fff", fontWeight: 800, fontSize: "0.85rem", cursor: "pointer" }}
                    >
                      <Save size={13} />{saving ? "Guardando..." : "Guardar cambios"}
                    </button>
                    <button
                      onClick={cancelEdit}
                      style={{ display: "flex", alignItems: "center", gap: "6px", padding: "7px 14px", borderRadius: "7px", border: "1px solid var(--border-subtle)", background: "transparent", color: "var(--text-muted)", fontWeight: 700, fontSize: "0.85rem", cursor: "pointer" }}
                    >
                      <X size={13} />Cancelar
                    </button>
                  </div>
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
};
