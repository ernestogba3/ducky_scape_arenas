import { apiPost } from "../api.js";
export default class ThemeScene extends Phaser.Scene {
  constructor() {
    super("ThemeScene");
  }

  init(data) {
    this.theme = data.theme;
    this.selectedIndex = 0;
  }

  create() {
    const W = this.scale.width;
    const H = this.scale.height;

    // ===== Fondo (mismo estilo del hub) =====
    this.drawBackground();

    // ===== Título del tema =====
    this.add
      .text(W / 2, 60, this.theme.label, {
        fontFamily: "monospace",
        fontSize: "52px",
        color: "#ffd54f",
        stroke: "#000",
        strokeThickness: 5,
      })
      .setOrigin(0.5);

    const n = this.theme.rooms.length;
    this.add
      .text(
        W / 2,
        110,
        `${n} aventura${n > 1 ? "s" : ""} disponible${n > 1 ? "s" : ""}`,
        {
          fontFamily: "monospace",
          fontSize: "18px",
          color: "#b0b0cc",
        },
      )
      .setOrigin(0.5);

    // ===== Flechas de navegación =====
    this.leftArrow = this.add
      .text(140, H / 2, "◀", {
        fontFamily: "monospace",
        fontSize: "48px",
        color: "#ffd54f",
        stroke: "#000",
        strokeThickness: 3,
      })
      .setOrigin(0.5);
    this.rightArrow = this.add
      .text(W - 140, H / 2, "▶", {
        fontFamily: "monospace",
        fontSize: "48px",
        color: "#ffd54f",
        stroke: "#000",
        strokeThickness: 3,
      })
      .setOrigin(0.5);

    if (n <= 1) {
      this.leftArrow.setAlpha(0.2);
      this.rightArrow.setAlpha(0.2);
    }

    // ===== Tarjeta central (se repinta al cambiar selección) =====
    this.cardElements = [];
    this.renderCard();

    // ===== Barra inferior con instrucciones =====
    this.add.rectangle(W / 2, H - 40, W, 50, 0x000000, 0.6);
    this.add
      .text(
        W / 2,
        H - 40,
        "◀ ▶  navegar      ENTER  entrar      ESC  volver al hub",
        {
          fontFamily: "monospace",
          fontSize: "18px",
          color: "#fff",
        },
      )
      .setOrigin(0.5);

    // ===== Controles =====
    this.input.keyboard.on("keydown-LEFT", () => this.changeSelection(-1));
    this.input.keyboard.on("keydown-RIGHT", () => this.changeSelection(+1));
    this.input.keyboard.on("keydown-ESC", () => this.scene.start("HubScene"));
    this.input.keyboard.on("keydown-ENTER", () => this.enterRoom());
    this.add
      .text(
        10,
        this.scale.height - 10,
        "⚠ Arte provisional — pendiente de imágenes finales",
        {
          fontFamily: "monospace",
          fontSize: "11px",
          color: "#555",
        },
      )
      .setOrigin(0, 1);
  }

  drawBackground() {
    const W = this.scale.width;
    const H = this.scale.height;
    const bg = this.add.graphics();
    bg.fillGradientStyle(0x1a1a3a, 0x1a1a3a, 0x3d2b4e, 0x3d2b4e, 1);
    bg.fillRect(0, 0, W, H);
    for (let i = 0; i < 50; i++) {
      const x = Phaser.Math.Between(0, W);
      const y = Phaser.Math.Between(0, H);
      const size = Phaser.Math.FloatBetween(0.5, 2);
      const alpha = Phaser.Math.FloatBetween(0.3, 1);
      this.add.circle(x, y, size, 0xffffff, alpha);
    }
  }

  renderCard() {
    this.cardElements.forEach((el) => el.destroy());
    this.cardElements = [];

    const room = this.theme.rooms[this.selectedIndex];
    const W = this.scale.width;
    const cx = W / 2;
    const cy = 360;

    // Contador "2 / 5"
    const counter = this.add
      .text(cx, 165, `${this.selectedIndex + 1} / ${this.theme.rooms.length}`, {
        fontFamily: "monospace",
        fontSize: "18px",
        color: "#aaa",
      })
      .setOrigin(0.5);

    // Sombra + fondo + marco
    const shadow = this.add.rectangle(cx + 6, cy + 8, 560, 320, 0x000000, 0.4);
    const card = this.add.rectangle(cx, cy, 560, 320, 0x2a2a44, 0.95);
    const border = this.add
      .rectangle(cx, cy, 560, 320, 0x000000, 0)
      .setStrokeStyle(4, 0xffd54f);

    // Badge de era arriba
    const badgeY = cy - 125;
    const badge = this.add.rectangle(cx, badgeY, 280, 36, 0xffd54f, 1);
    const badgeText = this.add
      .text(cx, badgeY, `ERA ${room.era} · ${room.era_display.toUpperCase()}`, {
        fontFamily: "monospace",
        fontSize: "16px",
        color: "#000",
        fontStyle: "bold",
      })
      .setOrigin(0.5);

    // Nombre
    const name = this.add
      .text(cx, cy - 60, room.name, {
        fontFamily: "monospace",
        fontSize: "26px",
        color: "#fff",
        wordWrap: { width: 520 },
        align: "center",
      })
      .setOrigin(0.5);

    // Descripción
    const desc = this.add
      .text(cx, cy + 10, room.description, {
        fontFamily: "monospace",
        fontSize: "15px",
        color: "#b0b0cc",
        wordWrap: { width: 520 },
        align: "center",
      })
      .setOrigin(0.5);

    // Meta
    const meta = this.add
      .text(
        cx,
        cy + 115,
        `Dificultad: ${room.difficulty_display}      ·      Duración: ~${room.estimated_duration} min`,
        { fontFamily: "monospace", fontSize: "16px", color: "#ffd54f" },
      )
      .setOrigin(0.5);

    this.cardElements.push(
      counter,
      shadow,
      card,
      border,
      badge,
      badgeText,
      name,
      desc,
      meta,
    );
  }

  changeSelection(delta) {
    const n = this.theme.rooms.length;
    if (n <= 1) return;
    this.selectedIndex = (this.selectedIndex + delta + n) % n;
    this.renderCard();
    const arrow = delta > 0 ? this.rightArrow : this.leftArrow;
    this.tweens.add({ targets: arrow, scale: 1.4, duration: 120, yoyo: true });
  }

  async enterRoom() {
    const room = this.theme.rooms[this.selectedIndex];
    const W = this.scale.width;
    const H = this.scale.height;

    const flash = this.add.rectangle(W / 2, H / 2, W, H, 0xffd54f, 0);
    this.tweens.add({
      targets: flash,
      alpha: { from: 0, to: 0.6 },
      duration: 150,
      yoyo: true,
    });

    const loadingBg = this.add
      .rectangle(W / 2, H / 2, 520, 120, 0x000000, 0.9)
      .setStrokeStyle(3, 0xffd54f);
    const loadingTxt = this.add
      .text(W / 2, H / 2, "Arrancando aventura...", {
        fontFamily: "monospace",
        fontSize: "20px",
        color: "#fff",
      })
      .setOrigin(0.5);

    try {
      const res = await apiPost("/escape/api/session/start/", {
        escape_room_id: room.id,
      });
      if (!res.ok) throw new Error(res.error || "Error desconocido");

      // Si es una reanudación, avisamos al usuario
      if (res.resumed) {
        loadingTxt.setText("Reanudando partida anterior...");
        loadingTxt.setColor("#64b5f6");
        await new Promise((r) => setTimeout(r, 700));
      }

      loadingBg.destroy();
      loadingTxt.destroy();

      this.scene.start("RoomScene", {
        sessionId: res.session_id,
        resumed: res.resumed,
        escapeRoom: res.escape_room || room,
      });
    } catch (err) {
      console.error(err);
      loadingTxt.setText("Error: " + err.message);
      loadingTxt.setColor("#ff6b6b");
      this.time.delayedCall(3000, () => {
        loadingBg.destroy();
        loadingTxt.destroy();
      });
    }
  }
}
