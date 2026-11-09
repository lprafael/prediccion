// Extrae los cupones de "Mis Apuestas" de Aposta.la (Kambi) como JSON.
// Uso: abrir https://aposta.la/bets#bethistory con sesion iniciada, cargar el historial
// ("Mostrar mas apuestas") y ejecutar este script en la consola del navegador.
// Devuelve un array con el formato de POST /api/cupones/importar.
(() => {
  const MESES = { ene: 1, feb: 2, mar: 3, abr: 4, may: 5, jun: 6, jul: 7, ago: 8, sep: 9, sept: 9, set: 9, oct: 10, nov: 11, dic: 12 };
  const num = (t) => {
    if (!t) return null;
    const v = parseFloat(t.replace(/[^\d.,]/g, "").replace(/,/g, ""));
    return Number.isFinite(v) ? v : null;
  };
  const fecha = (t) => {
    // "8 nov. 2026 • 21:58" (hora local de Paraguay, UTC-3)
    const m = (t || "").toLowerCase().match(/(\d{1,2})\s+([a-z]+)\.?\s+(\d{4})\s*•\s*(\d{1,2}):(\d{2})/);
    if (!m || !MESES[m[2]]) return null;
    const p = (x) => String(x).padStart(2, "0");
    return `${m[3]}-${p(MESES[m[2]])}-${p(m[1])}T${p(m[4])}:${m[5]}:00-03:00`;
  };
  const campo = (card, etiqueta) => {
    for (const f of card.querySelectorAll(".KambiBC-my-bets-summary__field")) {
      const l = f.querySelector(".KambiBC-my-bets-summary__label");
      if (l && l.innerText.trim().toLowerCase().startsWith(etiqueta)) {
        return f.querySelector(".KambiBC-my-bets-summary__value")?.innerText.trim() || null;
      }
    }
    return null;
  };
  const cupones = [];
  for (const card of document.querySelectorAll(".KambiBC-my-bets-summary__coupon")) {
    const id = card.querySelector(".KambiBC-my-bets-summary__coupon-ref .KambiBC-my-bets-summary__value")?.innerText.trim();
    if (!id) continue;
    const tituloEl = card.querySelector(".KambiBC-my-bets-summary__title");
    const tipo = (tituloEl?.childNodes[0]?.textContent || "").trim();
    const statusTxt = card.querySelector(".KambiBC-my-bets-summary__coupon-status")?.innerText.trim() || "";
    let estado = "abierta";
    if (/cobro de apuesta confirmado/i.test(statusTxt)) estado = "cobro_anticipado";
    else if (/ganad/i.test(statusTxt)) estado = "ganada";
    else if (/perdid/i.test(statusTxt)) estado = "perdida";
    else if (/anulad|cancelad|devuelt/i.test(statusTxt)) estado = "anulada";
    const stakeTxt = campo(card, "apuesta") || "";
    let cuota = num(campo(card, "cuotas"));
    if (!cuota) {
      const m = (tituloEl?.innerText || card.innerText).match(/@\s*([\d.]+)/);
      cuota = m ? parseFloat(m[1]) : null;
    }
    const selecciones = [];
    for (const row of card.querySelectorAll(".KambiBC-my-bets-summary-coupon__event-list > div")) {
      const nombres = row.querySelectorAll(".KambiBC-my-bets-summary-coupon__event-list-name");
      const sel = nombres[0]?.innerText.trim() || "";
      const partido = row.querySelector(".KambiBC-my-bets-summary-coupon__outcome-name")?.innerText.trim() || null;
      const i = sel.lastIndexOf(": ");
      selecciones.push(i > 0 ? { mercado: sel.slice(0, i), seleccion: sel.slice(i + 2), partido }
                             : { mercado: null, seleccion: sel, partido });
    }
    cupones.push({
      cupon_id: id,
      fecha: fecha(card.querySelector(".KambiBC-my-bets-summary__coupon-date")?.innerText),
      tipo, estado, cuota,
      monto: num(stakeTxt) || 0,
      pago: estado === "abierta" ? 0 : (num(campo(card, "pago:")) || 0),
      gratuita: /gratuita/i.test(stakeTxt),
      selecciones,
    });
  }
  return cupones;
})();
