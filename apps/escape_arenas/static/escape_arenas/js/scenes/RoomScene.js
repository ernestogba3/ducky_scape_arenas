import { apiGet } from "../api.js";

// Paleta de fondo por era
const ERA_COLORS = {
  1: { top: 0x3a2f20, bottom: 0x1a1308 }, // Prehistórico
  2: { top: 0x1e3a5f, bottom: 0x0a1c33 }, // Griego
  3: { top: 0x5f1e1e, bottom: 0x330a0a }, // Romano
  4: { top: 0x2a2a3a, bottom: 0x14141f }, // Medieval
  5: { top: 0x3f2c5f, bottom: 0x1f1430 }, // Renacentista
  6: { top: 0x2b2420, bottom: 0x140e0a }, // Rev. Industrial
  7: { top: 0x1a2b3f, bottom: 0x0a1420 }, // Siglo XX
};

export default class RoomScene extends Phaser.Scene {
  constructor() {
    super("RoomScene");
  }

  init(data) {
    this.sessionId = data.sessionId;
    this.escapeRoom = data.escapeRoom; // info del hub (name, era, era_display, theme)
    this.state = null;
  }

  async create() {
    const W = this.scale.width;
    const H = this.scale.height;

    // Fondo con color por era
    const era = (this.escapeRoom && this.escapeRoom.era) || 1;
    const colors = ERA_COLORS[era] || ERA_COLORS[1];
    const bg = this.add.graphics();
    bg.fillGradientStyle(
      colors.top,
      colors.top,
      colors.bottom,
      colors.bottom,
      1,
    );
    bg.fillRect(0, 0, W, H);

    // Estrellas tenues
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

    // Loading
    this.loadingText = this.add
      .text(W / 2, H / 2, "Cargando partida...", {
        fontFamily: "monospace",
        fontSize: "22px",
        color: "#fff",
      })
      .setOrigin(0.5);

    // ESC para abandonar (por ahora, volver al hub)
    this.input.keyboard.on("keydown-ESC", () => this.scene.start("HubScene"));

    try {
      await this.loadState();
      this.loadingText.destroy();
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

    // Barra superior
    this.add.rectangle(W / 2, 30, W, 60, 0x000000, 0.75);

    // Nombre del escape room
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

    // Progreso centro
    const progressText = `Fase ${s.progress.completed_stages + 1} / ${s.progress.total_stages}`;
    this.add
      .text(W / 2, 30, progressText, {
        fontFamily: "monospace",
        fontSize: "18px",
        color: "#fff",
      })
      .setOrigin(0.5);

    // Tiempo + score derecha
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

    // Tick de reloj cada segundo (solo visual; el backend es el que decide)
    this.time.addEvent({
      delay: 1000,
      loop: true,
      callback: () => {
        if (!this.state) return;
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

    // Nombre de la sala y stage
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
      .text(W / 2, 135, `${s.stage.name}`, {
        fontFamily: "monospace",
        fontSize: "18px",
        color: "#ffd54f",
      })
      .setOrigin(0.5);

    // Descripción de la stage (cuadro)
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

    // Placeholder del "objeto interactuable" (lo activaremos en el Paso 9)
    const objX = W / 2;
    const objY = 450;
    this.interactObj = this.add
      .rectangle(objX, objY, 120, 120, 0x8b6f47)
      .setStrokeStyle(4, 0xffd54f);
    // Pulso suave
    this.tweens.add({
      targets: this.interactObj,
      alpha: { from: 0.85, to: 1 },
      duration: 900,
      yoyo: true,
      repeat: -1,
    });
    this.add
      .text(objX, objY + 90, "📜", {
        fontSize: "48px",
      })
      .setOrigin(0.5);

    // Hint abajo
    this.add
      .text(W / 2, H - 60, "(Paso 9: click en el objeto abrirá el puzzle)", {
        fontFamily: "monospace",
        fontSize: "14px",
        color: "#999",
      })
      .setOrigin(0.5);
    this.add
      .text(W / 2, H - 30, "ESC vuelve al hub", {
        fontFamily: "monospace",
        fontSize: "14px",
        color: "#666",
      })
      .setOrigin(0.5);
  }
}
