// Efectos de sonido sintéticos con Web Audio API.
// Sin assets externos, cero CORS, cero descargas.

let ctx;

function getCtx() {
  if (!ctx) {
    const AC = window.AudioContext || window.webkitAudioContext;
    if (!AC) return null;
    ctx = new AC();
  }
  // Políticas de autoplay: si el contexto está suspendido, intentamos reanudarlo.
  if (ctx.state === "suspended") ctx.resume().catch(() => {});
  return ctx;
}

function playSequence(notes, type = "sine") {
  const c = getCtx();
  if (!c) return;
  let t = c.currentTime;
  notes.forEach(([freq, dur, vol = 0.25]) => {
    const osc = c.createOscillator();
    const gain = c.createGain();
    osc.type = type;
    osc.frequency.value = freq;
    gain.gain.setValueAtTime(vol, t);
    gain.gain.exponentialRampToValueAtTime(0.001, t + dur);
    osc.connect(gain);
    gain.connect(c.destination);
    osc.start(t);
    osc.stop(t + dur);
    t += dur;
  });
}

export const SFX = {
  // Al abrir el modal del puzzle: un "clic" agudo
  open: () => playSequence([[660, 0.08, 0.15]], "sine"),

  // Al acertar: pequeño arpegio ascendente DO-MI-SOL
  correct: () =>
    playSequence(
      [
        [523, 0.1],
        [659, 0.1],
        [784, 0.25],
      ],
      "triangle",
    ),

  // Al fallar: dos notas descendentes con onda tosca
  wrong: () =>
    playSequence(
      [
        [300, 0.1, 0.25],
        [200, 0.2, 0.25],
      ],
      "sawtooth",
    ),

  // Al pedir pista: un "ding" claro
  hint: () => playSequence([[880, 0.15, 0.2]], "sine"),

  // Victoria: fanfare ascendente
  victory: () =>
    playSequence(
      [
        [523, 0.12],
        [659, 0.12],
        [784, 0.12],
        [1046, 0.35, 0.3],
      ],
      "triangle",
    ),

  // Derrota: notas descendentes largas
  defeat: () =>
    playSequence(
      [
        [400, 0.15, 0.25],
        [350, 0.15, 0.25],
        [300, 0.15, 0.25],
        [200, 0.45, 0.25],
      ],
      "sawtooth",
    ),
};
// ─── Música de fondo ───────────────────────────────────────────
// Loop ambient minimalista en La menor. Volumen bajo para no molestar.

let bgPlaying = false;
let bgTimeout = null;

function playBgNote(
  freq,
  startTime,
  duration,
  type = "triangle",
  volume = 0.04,
) {
  const c = getCtx();
  if (!c) return;
  const osc = c.createOscillator();
  const gain = c.createGain();
  osc.type = type;
  osc.frequency.value = freq;
  gain.gain.setValueAtTime(0, startTime);
  gain.gain.linearRampToValueAtTime(volume, startTime + 0.08);
  gain.gain.exponentialRampToValueAtTime(0.001, startTime + duration);
  osc.connect(gain);
  gain.connect(c.destination);
  osc.start(startTime);
  osc.stop(startTime + duration + 0.05);
}

function scheduleBgLoop() {
  if (!bgPlaying) return;
  const c = getCtx();
  if (!c) return;
  const now = c.currentTime;

  // Melodía ambient 12s en A menor pentatónica
  // [freq, offset_s, duration_s]
  const melody = [
    [220.0, 0.0, 1.4], // A3
    [261.63, 1.5, 1.2], // C4
    [329.63, 3.0, 1.4], // E4
    [293.66, 4.5, 1.0], // D4
    [220.0, 6.0, 1.4], // A3
    [196.0, 7.5, 1.2], // G3
    [174.61, 9.0, 1.4], // F3
    [220.0, 10.5, 1.4], // A3
  ];
  melody.forEach(([freq, offset, dur]) => {
    playBgNote(freq, now + offset, dur, "triangle", 0.04);
  });

  // Nota baja sostenida de fondo (drone) - una sola nota larga
  playBgNote(110.0, now, 12, "sine", 0.015);

  bgTimeout = setTimeout(scheduleBgLoop, 12000);
}

export const Music = {
  start() {
    if (bgPlaying) return;
    bgPlaying = true;
    scheduleBgLoop();
  },
  stop() {
    bgPlaying = false;
    if (bgTimeout) {
      clearTimeout(bgTimeout);
      bgTimeout = null;
    }
  },
};
