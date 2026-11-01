/**
 * Generador de Alertas Sonoras Cuantitativas usando Web Audio API nativo.
 * No requiere archivos externos .mp3 ni dependencias pesadas.
 */

class SoundEffects {
  private ctx: AudioContext | null = null;
  public enabled: boolean = true;

  private getContext(): AudioContext | null {
    if (!this.enabled) return null;
    if (!this.ctx) {
      const AudioContextClass = window.AudioContext || (window as any).webkitAudioContext;
      if (AudioContextClass) {
        this.ctx = new AudioContextClass();
      }
    }
    if (this.ctx && this.ctx.state === 'suspended') {
      this.ctx.resume();
    }
    return this.ctx;
  }

  /**
   * Alerta Especial de Campana Resonante para Probabilidades > 90% (Campana Tubular / Chime Metálico)
   */
  playBellAlert() {
    const ctx = this.getContext();
    if (!ctx) return;

    const t = ctx.currentTime;
    // Espectro de armónicos de campana metálica (hum, fundamental, tercera menor, quinta, octava y parciales superiores)
    const partials = [
      { ratio: 0.5, gain: 0.28, decay: 1.8 },   // Hum tone subarmónico
      { ratio: 1.0, gain: 0.45, decay: 2.2 },   // Fundamental principal
      { ratio: 1.19, gain: 0.22, decay: 1.6 },  // Tercera menor (carácter de campana)
      { ratio: 1.5, gain: 0.25, decay: 1.7 },   // Quinta justa
      { ratio: 2.0, gain: 0.28, decay: 1.3 },   // Octava
      { ratio: 2.76, gain: 0.16, decay: 0.9 },  // Armónico metálico inarmónico
      { ratio: 4.07, gain: 0.12, decay: 0.5 },  // Shimmer metálico agudo
    ];

    // Primera campanada: Tono A5 (880 Hz)
    const baseFreq1 = 880.0;
    partials.forEach(({ ratio, gain, decay }) => {
      const osc = ctx.createOscillator();
      const gainNode = ctx.createGain();

      osc.type = 'sine';
      osc.frequency.setValueAtTime(baseFreq1 * ratio, t);

      gainNode.gain.setValueAtTime(0.0001, t);
      // Ataque percusivo inmediato de badajo de campana (6ms)
      gainNode.gain.exponentialRampToValueAtTime(gain * 0.35, t + 0.006);
      // Decaimiento natural largo
      gainNode.gain.exponentialRampToValueAtTime(0.0001, t + decay);

      osc.connect(gainNode);
      gainNode.connect(ctx.destination);

      osc.start(t);
      osc.stop(t + decay);
    });

    // Segunda campanada resonante: Tono C6 (1046.5 Hz) a los 0.28s (Efecto Ding-Dong triunfal)
    const t2 = t + 0.28;
    const baseFreq2 = 1046.50;
    partials.forEach(({ ratio, gain, decay }) => {
      const osc = ctx.createOscillator();
      const gainNode = ctx.createGain();

      osc.type = 'sine';
      osc.frequency.setValueAtTime(baseFreq2 * ratio, t2);

      gainNode.gain.setValueAtTime(0.0001, t2);
      gainNode.gain.exponentialRampToValueAtTime(gain * 0.40, t2 + 0.006);
      gainNode.gain.exponentialRampToValueAtTime(0.0001, t2 + decay);

      osc.connect(gainNode);
      gainNode.connect(ctx.destination);

      osc.start(t2);
      osc.stop(t2 + decay);
    });
  }

  /**
   * Alerta de Valor Cuantitativo Elevado (Chime armónico ascendente)
   */
  playValueAlert() {
    const ctx = this.getContext();
    if (!ctx) return;

    const notes = [523.25, 659.25, 783.99, 1046.50]; // C5, E5, G5, C6 (Acorde mayor)
    notes.forEach((freq, idx) => {
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();

      const startTime = ctx.currentTime + idx * 0.08;
      const duration = 0.35;

      osc.type = 'sine';
      osc.frequency.setValueAtTime(freq, startTime);

      gain.gain.setValueAtTime(0.001, startTime);
      gain.gain.exponentialRampToValueAtTime(0.18, startTime + 0.03);
      gain.gain.exponentialRampToValueAtTime(0.0001, startTime + duration);

      osc.connect(gain);
      gain.connect(ctx.destination);

      osc.start(startTime);
      osc.stop(startTime + duration);
    });
  }

  /**
   * Sonido de canasta o actualización de marcador (Plink seco sutil)
   */
  playScoreTick() {
    const ctx = this.getContext();
    if (!ctx) return;

    const osc = ctx.createOscillator();
    const gain = ctx.createGain();

    const t = ctx.currentTime;
    osc.type = 'triangle';
    osc.frequency.setValueAtTime(440, t);
    osc.frequency.exponentialRampToValueAtTime(880, t + 0.08);

    gain.gain.setValueAtTime(0.08, t);
    gain.gain.exponentialRampToValueAtTime(0.001, t + 0.09);

    osc.connect(gain);
    gain.connect(ctx.destination);

    osc.start(t);
    osc.stop(t + 0.09);
  }

  /**
   * Alerta de Peligro / Advertencia de Ritmo (Tono descendente)
   */
  playWarning() {
    const ctx = this.getContext();
    if (!ctx) return;

    const osc = ctx.createOscillator();
    const gain = ctx.createGain();

    const t = ctx.currentTime;
    osc.type = 'sawtooth';
    osc.frequency.setValueAtTime(600, t);
    osc.frequency.exponentialRampToValueAtTime(250, t + 0.25);

    gain.gain.setValueAtTime(0.12, t);
    gain.gain.exponentialRampToValueAtTime(0.001, t + 0.25);

    osc.connect(gain);
    gain.connect(ctx.destination);

    osc.start(t);
    osc.stop(t + 0.25);
  }
}

export const sounds = new SoundEffects();
