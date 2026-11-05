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
    this.state = null;
    this.modalApi = null;
  }

  async create() {
    const W = this.scale.width;
    const H = this.scale.height;

    // Fondo
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

    this.time.addEvent({
      delay: 1000,
      loop: true,
      callback: () => {
        if (!this.state || this.state.finished) return;
        this.state.session.remaining_seconds = Math.max(
          0,
          this.state.session.remaining_seconds - 1,
        );
        const m = Math.floor(this.state.session.remaining_seconds / 60);
        const s2 = this.state.session.remaining_seconds % 60;
        this.timerText.setText(`⏱ ${m}:${s2.toString().padStart(2, "0")}`);
      },
    });
  }

  renderStageInfo() {
    const W = this.scale.width;
    const H = this.scale.height;
    const s = this.state;

    this.add
      .text(W / 2, 100, s.room.name, {
        fontFamily: "monospace",
        fontSize: "24px",
        color: "#fff",
        stroke: "#000",
        strokeThickness: 3,
      })
      .setOrigin(0.5);
    this.add
      .text(W / 2, 135, s.stage.name, {
        fontFamily: "monospace",
        fontSize: "18px",
        color: "#ffd54f",
      })
      .setOrigin(0.5);

    this.add
      .rectangle(W / 2, 220, 900, 100, 0x000000, 0.5)
      .setStrokeStyle(2, 0x555555);
    this.add
      .text(W / 2, 220, s.stage.description, {
        fontFamily: "monospace",
        fontSize: "15px",
        color: "#ddd",
        wordWrap: { width: 860 },
        align: "center",
      })
      .setOrigin(0.5);

    // Objeto interactuable con glow
    const objX = W / 2;
    const objY = 450;
    this.interactObj = this.add
      .rectangle(objX, objY, 140, 140, 0x8b6f47)
      .setStrokeStyle(4, 0xffd54f)
      .setInteractive({ useHandCursor: true });

    // Glow pulsante
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
      .text(W / 2, H - 30, "ESC vuelve al hub", {
        fontFamily: "monospace",
        fontSize: "13px",
        color: "#666",
      })
      .setOrigin(0.5);
  }

  openPuzzle() {
    if (this.modalApi) return;
    // Desactiva el teclado de Phaser mientras el modal está arriba
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
        api.showFeedback("Error: " + (res.error || "desconocido"), "#ff6b6b");
        api.enable();
        return;
      }

      if (res.is_correct) {
        api.showFeedback("✓ ¡Correcto!", "#4caf50");
        this.time.delayedCall(1200, () => {
          this.closeModal();
          if (res.completed) {
            this.scene.restart({
              sessionId: this.sessionId,
              escapeRoom: this.escapeRoom,
            });
          } else {
            this.scene.restart({
              sessionId: this.sessionId,
              escapeRoom: this.escapeRoom,
            });
          }
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
      api.showFeedback("Error: " + err.message, "#ff6b6b");
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
          "Error: " + (res.error || "No hay pista disponible"),
          "#ff6b6b",
        );
        return;
      }
      const h = res.hint;
      api.appendHintText(
        `${h.text}<br><span style="color:#888;font-size:12px">(−${h.penalty_seconds}s · −${h.penalty_points} pts)</span>`,
      );
    } catch (err) {
      api.showFeedback("Error: " + err.message, "#ff6b6b");
    }
  }

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
      .text(W / 2, 220, "AVENTURA FALLIDA", {
        fontFamily: "monospace",
        fontSize: "56px",
        color: "#ff6b6b",
        stroke: "#000",
        strokeThickness: 5,
      })
      .setOrigin(0.5);
    this.add
      .text(W / 2, 300, "La partida ha terminado.", {
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
