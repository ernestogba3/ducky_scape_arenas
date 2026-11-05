import { apiGet, apiPost } from "../api.js";
import { openPuzzleModal } from "../ui/puzzle-modal.js";

const ERA_COLORS = {
  1: { top: 0x3a2f20, bottom: 0x1a1308 },
  2: { top: 0x1e3a5f, bottom: 0x0a1c33 },
  3: { top: 0x5f1e1e, bottom: 0x330a0a },
  4: { top: 0x2a2a3a, bottom: 0x14141f },
  5: { top: 0x3f2c5f, bottom: 0x1f1430 },
  6: { top: 0x2b2420, bottom: 0x140e0a },
  7: { top: 0x1a2b3f, bottom: 0x0a1420 },
};

export default class RoomScene extends Phaser.Scene {
  constructor() {
    super("RoomScene");
  }

  init(data) {
    this.sessionId = data.sessionId;
    this.escapeRoom = data.escapeRoom;
    this.resumed = !!data.resumed;
    this.state = null;
    this.modalApi = null;
    this.expireChecked = false;
  }

  async create() {
    const W = this.scale.width;
    const H = this.scale.height;

    // Fondo con color por era
    const era = (this.escapeRoom && this.escapeRoom.era) || 1;
    const c = ERA_COLORS[era] || ERA_COLORS[1];
    const bg = this.add.graphics();
    bg.fillGradientStyle(c.top, c.top, c.bottom, c.bottom, 1);
    bg.fillRect(0, 0, W, H);
    for (let i = 0; i < 40; i++) {
      const x = Phaser.Math.Between(0, W);
      const y = Phaser.Math.Between(0, H * 0.5);
      this.add.circle(
        x,
        y,
        Phaser.Math.FloatBetween(0.5, 1.5),
        0xffffff,
        Phaser.Math.FloatBetween(0.2, 0.6),
      );
    }

    this.loadingText = this.add
      .text(W / 2, H / 2, "Cargando partida...", {
        fontFamily: "monospace",
        fontSize: "22px",
        color: "#fff",
      })
      .setOrigin(0.5);

    // ESC → hub
    this.input.keyboard.on("keydown-ESC", () => {
      this.closeModal();
      this.scene.start("HubScene");
    });

    // Al volver a la pestaña después de un rato, refrescar estado
    this._visibilityHandler = () => {
      if (
        document.visibilityState === "visible" &&
        this.state &&
        !this.state.finished
      ) {
        this.silentRefresh();
      }
    };
    document.addEventListener("visibilitychange", this._visibilityHandler);
    this.events.once("shutdown", () => {
      document.removeEventListener("visibilitychange", this._visibilityHandler);
      this.closeModal();
    });

    try {
      await this.loadState();
      this.loadingText.destroy();
      if (this.state.finished) {
        if (this.state.session.status === "COMPLETED") this.showVictory();
        else this.showDefeat();
        return;
      }
      this.renderHUD();
      this.renderStageInfo();
      if (this.resumed) {
        this.showToast("📋 Partida reanudada", "#64b5f6");
      }
    } catch (err) {
      this.loadingText.setText("Error: " + err.message);
      this.loadingText.setColor("#ff6b6b");
      console.error(err);
    }
  }

  async loadState() {
    this.state = await apiGet(`/escape/api/session/${this.sessionId}/state/`);
    if (!this.state.ok)
      throw new Error(this.state.error || "Error del backend");
  }

  async silentRefresh() {
    // Refresca state sin repintar la escena (solo para detectar expiración).
    try {
      const old = this.state;
      await this.loadState();
      if (this.state.finished && !old.finished) {
        this.closeModal();
        this.scene.restart({
          sessionId: this.sessionId,
          escapeRoom: this.escapeRoom,
        });
      } else if (!this.state.finished) {
        // Sincroniza el reloj por si el backend dice menos tiempo
        this.state.session.remaining_seconds =
          this.state.session.remaining_seconds;
      }
    } catch (err) {
      console.warn("silentRefresh:", err);
    }
  }

  renderHUD() {
    const W = this.scale.width;
    const s = this.state;

    this.add.rectangle(W / 2, 30, W, 60, 0x000000, 0.75);

    this.add.text(20, 20, s.session.escape_room.name, {
      fontFamily: "monospace",
      fontSize: "18px",
      color: "#ffd54f",
    });
    this.add.text(
      20,
      42,
      `Era ${s.session.escape_room.era} · ${s.session.escape_room.era_display}`,
      {
        fontFamily: "monospace",
        fontSize: "13px",
        color: "#bbb",
      },
    );

    this.add
      .text(
        W / 2,
        30,
        `Fase ${s.progress.completed_stages + 1} / ${s.progress.total_stages}`,
        {
          fontFamily: "monospace",
          fontSize: "18px",
          color: "#fff",
        },
      )
      .setOrigin(0.5);

    const mm = Math.floor(s.session.remaining_seconds / 60);
    const ss = s.session.remaining_seconds % 60;
    this.timerText = this.add
      .text(W - 20, 20, `⏱ ${mm}:${ss.toString().padStart(2, "0")}`, {
        fontFamily: "monospace",
        fontSize: "18px",
        color: "#ffd54f",
      })
      .setOrigin(1, 0);
    this.add
      .text(W - 20, 42, `Score: ${s.session.score}`, {
        fontFamily: "monospace",
        fontSize: "13px",
        color: "#bbb",
      })
      .setOrigin(1, 0);

    // Botón "Abandonar" pequeño abajo a la izquierda del HUD
    this.abandonBtn = this.add
      .text(20, 68, "✕ Abandonar aventura", {
        fontFamily: "monospace",
        fontSize: "12px",
        color: "#ff8787",
        stroke: "#000",
        strokeThickness: 2,
      })
      .setInteractive({ useHandCursor: true });
    this.abandonBtn.on("pointerover", () =>
      this.abandonBtn.setColor("#ffb0b0"),
    );
    this.abandonBtn.on("pointerout", () => this.abandonBtn.setColor("#ff8787"));
    this.abandonBtn.on("pointerdown", () => this.confirmAbandon());

    // Timer que decrementa cada segundo + auto-chequeo al expirar
    this.timerEvent = this.time.addEvent({
      delay: 1000,
      loop: true,
      callback: () => this._tickTimer(),
    });
  }

  async _tickTimer() {
    if (!this.state || this.state.finished) return;
    this.state.session.remaining_seconds = Math.max(
      0,
      this.state.session.remaining_seconds - 1,
    );
    const sec = this.state.session.remaining_seconds;
    const m = Math.floor(sec / 60);
    const s = sec % 60;
    this.timerText.setText(`⏱ ${m}:${s.toString().padStart(2, "0")}`);
    // Color según urgencia
    if (sec <= 30) this.timerText.setColor("#ff6b6b");
    else if (sec <= 60) this.timerText.setColor("#ff9800");
    else this.timerText.setColor("#ffd54f");

    // Al expirar, pregunta al backend una vez
    if (sec === 0 && !this.expireChecked) {
      this.expireChecked = true;
      await this.silentRefresh();
    }
  }

  renderStageInfo() {
    const W = this.scale.width;
    const H = this.scale.height;
    const s = this.state;

    this.add
      .text(W / 2, 110, s.room.name, {
        fontFamily: "monospace",
        fontSize: "24px",
        color: "#fff",
        stroke: "#000",
        strokeThickness: 3,
      })
      .setOrigin(0.5);
    this.add
      .text(W / 2, 145, s.stage.name, {
        fontFamily: "monospace",
        fontSize: "18px",
        color: "#ffd54f",
      })
      .setOrigin(0.5);

    this.add
      .rectangle(W / 2, 230, 900, 100, 0x000000, 0.5)
      .setStrokeStyle(2, 0x555555);
    this.add
      .text(W / 2, 230, s.stage.description, {
        fontFamily: "monospace",
        fontSize: "15px",
        color: "#ddd",
        wordWrap: { width: 860 },
        align: "center",
      })
      .setOrigin(0.5);

    // Objeto interactuable con glow pulsante
    const objX = W / 2;
    const objY = 450;
    this.interactObj = this.add
      .rectangle(objX, objY, 140, 140, 0x8b6f47)
      .setStrokeStyle(4, 0xffd54f)
      .setInteractive({ useHandCursor: true });
    this.tweens.add({
      targets: this.interactObj,
      scale: { from: 1, to: 1.08 },
      duration: 900,
      yoyo: true,
      repeat: -1,
      ease: "Sine.easeInOut",
    });
    this.add.text(objX, objY, "📜", { fontSize: "64px" }).setOrigin(0.5);

    this.interactObj.on("pointerover", () =>
      this.interactObj.setStrokeStyle(5, 0xffffff),
    );
    this.interactObj.on("pointerout", () =>
      this.interactObj.setStrokeStyle(4, 0xffd54f),
    );
    this.interactObj.on("pointerdown", () => this.openPuzzle());

    this.add
      .text(W / 2, 540, "Haz click en el objeto para resolver la prueba", {
        fontFamily: "monospace",
        fontSize: "14px",
        color: "#aaa",
      })
      .setOrigin(0.5);

    this.add
      .text(W / 2, H - 30, "ESC vuelve al hub (la partida queda en curso)", {
        fontFamily: "monospace",
        fontSize: "13px",
        color: "#666",
      })
      .setOrigin(0.5);
  }

  // ─── Modal del puzzle ─────────────────────────────────────────

  openPuzzle() {
    if (this.modalApi) return;
    if (this.state.finished) return;
    this.input.keyboard.enabled = false;

    this.modalApi = openPuzzleModal(this.state, {
      onSubmit: (answer, api) => this.submitAnswer(answer, api),
      onHintRequest: (api) => this.requestHint(api),
      onCancel: () => this.closeModal(),
    });
  }

  closeModal() {
    if (this.modalApi) {
      this.modalApi.close();
      this.modalApi = null;
    }
    this.input.keyboard.enabled = true;
  }

  async submitAnswer(answer, api) {
    api.disable();
    try {
      const res = await apiPost(
        `/escape/api/session/${this.sessionId}/submit/`,
        {
          puzzle_id: this.state.puzzle.id,
          answer: answer,
        },
      );

      if (!res.ok) {
        api.showFeedback("⚠ " + (res.error || "Error desconocido"), "#ff9800");
        api.enable();
        // Si el error es de sesión no activa, cerrar y refrescar
        if (res.status && res.status !== "PLAYING") {
          this.time.delayedCall(1800, () => {
            this.closeModal();
            this.scene.restart({
              sessionId: this.sessionId,
              escapeRoom: this.escapeRoom,
            });
          });
        }
        return;
      }

      if (res.is_correct) {
        api.showFeedback("✓ ¡Correcto!", "#4caf50");
        this.time.delayedCall(1200, () => {
          this.closeModal();
          this.scene.restart({
            sessionId: this.sessionId,
            escapeRoom: this.escapeRoom,
          });
        });
      } else {
        api.shake();
        api.showFeedback("✗ Incorrecto. Intenta de nuevo.", "#ff6b6b");
        if (res.failed) {
          this.time.delayedCall(1500, () => {
            this.closeModal();
            this.scene.restart({
              sessionId: this.sessionId,
              escapeRoom: this.escapeRoom,
            });
          });
        } else {
          api.enable();
        }
      }
    } catch (err) {
      console.error(err);
      api.showFeedback("Error de red: " + err.message, "#ff6b6b");
      api.enable();
    }
  }

  async requestHint(api) {
    try {
      const res = await apiPost(
        `/escape/api/session/${this.sessionId}/hint/`,
        {},
      );
      if (!res.ok) {
        api.showFeedback(
          "⚠ " + (res.error || "No hay pista disponible"),
          "#ff9800",
        );
        return;
      }
      const h = res.hint;
      api.appendHintText(
        `${h.text}<br><span style="color:#888;font-size:12px">(−${h.penalty_seconds}s · −${h.penalty_points} pts)</span>`,
      );
    } catch (err) {
      console.error(err);
      api.showFeedback("Error de red: " + err.message, "#ff6b6b");
    }
  }

  // ─── Abandono ────────────────────────────────────────────────

  confirmAbandon() {
    if (this.modalApi) return;
    this.input.keyboard.enabled = false;

    const overlay = document.createElement("div");
    overlay.id = "abandon-modal";
    overlay.style.cssText = `
      position: fixed; inset: 0; background: rgba(0,0,0,0.85);
      display: flex; align-items: center; justify-content: center;
      z-index: 1000; font-family: monospace;`;

    const panel = document.createElement("div");
    panel.style.cssText = `
      background: #2a2a44; border: 4px solid #ff6b6b; border-radius: 8px;
      padding: 28px 32px; max-width: 480px; color: #fff; text-align: center;
      box-shadow: 0 10px 40px rgba(0,0,0,0.8);`;
    panel.innerHTML = `
      <h2 style="margin:0 0 12px; color:#ff6b6b; font-size:22px;">¿Abandonar la aventura?</h2>
      <p style="margin:0 0 24px; font-size:14px; color:#ddd; line-height:1.5;">
        Perderás el progreso de esta partida.<br>La aventura quedará marcada como abandonada.
      </p>
      <div style="display:flex; gap:12px; justify-content:center;">
        <button id="abandon-no" style="padding:10px 20px; font-size:14px; font-family:monospace;
          background:#555; color:#fff; border:none; border-radius:4px; cursor:pointer; font-weight:bold;">Cancelar</button>
        <button id="abandon-yes" style="padding:10px 20px; font-size:14px; font-family:monospace;
          background:#ff6b6b; color:#fff; border:none; border-radius:4px; cursor:pointer; font-weight:bold;">Sí, abandonar</button>
      </div>`;
    overlay.appendChild(panel);
    document.body.appendChild(overlay);

    const cleanup = () => {
      overlay.remove();
      this.input.keyboard.enabled = true;
    };

    const onKey = (e) => {
      if (e.key === "Escape") {
        e.preventDefault();
        cleanup();
        document.removeEventListener("keydown", onKey);
      }
    };
    document.addEventListener("keydown", onKey);

    document.getElementById("abandon-no").onclick = () => {
      cleanup();
      document.removeEventListener("keydown", onKey);
    };
    document.getElementById("abandon-yes").onclick = async () => {
      cleanup();
      document.removeEventListener("keydown", onKey);
      try {
        const res = await apiPost(
          `/escape/api/session/${this.sessionId}/abandon/`,
          {},
        );
        if (!res.ok) throw new Error(res.error || "No se pudo abandonar");
        await this.loadState();
        this.scene.restart({
          sessionId: this.sessionId,
          escapeRoom: this.escapeRoom,
        });
      } catch (err) {
        console.error(err);
        this.showToast("Error al abandonar: " + err.message, "#ff6b6b");
      }
    };
  }

  // ─── Toast ────────────────────────────────────────────────────

  showToast(text, color = "#ff6b6b") {
    const W = this.scale.width;
    const H = this.scale.height;
    const bg = this.add
      .rectangle(W / 2, H - 100, 600, 50, 0x000000, 0.92)
      .setStrokeStyle(2, color);
    const txt = this.add
      .text(W / 2, H - 100, text, {
        fontFamily: "monospace",
        fontSize: "15px",
        color: color,
      })
      .setOrigin(0.5);
    this.tweens.add({
      targets: [bg, txt],
      alpha: { from: 1, to: 0 },
      delay: 2500,
      duration: 600,
      onComplete: () => {
        bg.destroy();
        txt.destroy();
      },
    });
  }

  // ─── Pantallas finales ────────────────────────────────────────

  showVictory() {
    const W = this.scale.width;
    const H = this.scale.height;

    this.add.rectangle(W / 2, H / 2, W, H, 0x000000, 0.92);
    this.add
      .text(W / 2, 160, "¡HAS ESCAPADO!", {
        fontFamily: "monospace",
        fontSize: "68px",
        color: "#4caf50",
        stroke: "#000",
        strokeThickness: 6,
      })
      .setOrigin(0.5);
    this.add
      .text(W / 2, 240, this.state.session.escape_room.name, {
        fontFamily: "monospace",
        fontSize: "22px",
        color: "#fff",
      })
      .setOrigin(0.5);

    const s = this.state.settlement;
    if (s) {
      this.add
        .text(W / 2, 330, `XP Bruta: ${s.gross_xp}`, {
          fontFamily: "monospace",
          fontSize: "20px",
          color: "#fff",
        })
        .setOrigin(0.5);
      this.add
        .text(W / 2, 365, `Penalización: −${s.penalty_xp}`, {
          fontFamily: "monospace",
          fontSize: "20px",
          color: "#ff9800",
        })
        .setOrigin(0.5);
      this.add
        .text(W / 2, 400, `Bonus: +${s.bonus_xp}`, {
          fontFamily: "monospace",
          fontSize: "20px",
          color: "#64b5f6",
        })
        .setOrigin(0.5);
      this.add
        .text(W / 2, 480, `XP TOTAL: ${s.final_xp}`, {
          fontFamily: "monospace",
          fontSize: "36px",
          color: "#ffd54f",
          stroke: "#000",
          strokeThickness: 4,
        })
        .setOrigin(0.5);
    }

    const st = this.state.stats || {};
    this.add
      .text(
        W / 2,
        560,
        `Intentos: ${st.attempts || 0}  ·  Fallos: ${st.fails || 0}  ·  Pistas: ${st.hints_used || 0}`,
        {
          fontFamily: "monospace",
          fontSize: "16px",
          color: "#aaa",
        },
      )
      .setOrigin(0.5);

    this.add
      .text(W / 2, H - 50, "Pulsa ESC para volver al hub", {
        fontFamily: "monospace",
        fontSize: "15px",
        color: "#888",
      })
      .setOrigin(0.5);
  }

  showDefeat() {
    const W = this.scale.width;
    const H = this.scale.height;

    this.add.rectangle(W / 2, H / 2, W, H, 0x000000, 0.92);
    this.add
      .text(W / 2, 220, "AVENTURA TERMINADA", {
        fontFamily: "monospace",
        fontSize: "52px",
        color: "#ff6b6b",
        stroke: "#000",
        strokeThickness: 5,
      })
      .setOrigin(0.5);

    const reasonText = {
      TIME_EXPIRED: "Se agotó el tiempo.",
      FAILED: "Demasiados intentos fallidos.",
      ABANDONED: "Has abandonado la aventura.",
      COMPLETED: "Aventura completada.",
    };
    const reason =
      (this.state.settlement && this.state.settlement.reason) ||
      this.state.session.status;
    this.add
      .text(W / 2, 300, reasonText[reason] || "La partida ha terminado.", {
        fontFamily: "monospace",
        fontSize: "20px",
        color: "#ddd",
      })
      .setOrigin(0.5);

    const st = this.state.stats || {};
    this.add
      .text(
        W / 2,
        400,
        `Intentos: ${st.attempts || 0}  ·  Fallos: ${st.fails || 0}  ·  Pistas: ${st.hints_used || 0}`,
        {
          fontFamily: "monospace",
          fontSize: "18px",
          color: "#aaa",
        },
      )
      .setOrigin(0.5);

    this.add
      .text(W / 2, H - 50, "Pulsa ESC para volver al hub", {
        fontFamily: "monospace",
        fontSize: "15px",
        color: "#888",
      })
      .setOrigin(0.5);
  }
}
