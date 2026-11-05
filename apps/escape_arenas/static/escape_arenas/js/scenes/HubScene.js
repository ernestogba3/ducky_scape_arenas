import { Music } from "../sfx.js";
export default class HubScene extends Phaser.Scene {
  constructor() {
    super("HubScene");
  }

  create() {
    const W = this.scale.width;
    const H = this.scale.height;

    // ===== Fondo: cielo nocturno con degradado =====
    const bg = this.add.graphics();
    bg.fillGradientStyle(0x1a1a3a, 0x1a1a3a, 0x3d2b4e, 0x3d2b4e, 1);
    bg.fillRect(0, 0, W, H);

    // ===== Estrellas aleatorias =====
    for (let i = 0; i < 70; i++) {
      const x = Phaser.Math.Between(0, W);
      const y = Phaser.Math.Between(0, H * 0.6);
      const size = Phaser.Math.FloatBetween(0.5, 2);
      const alpha = Phaser.Math.FloatBetween(0.3, 1);
      this.add.circle(x, y, size, 0xffffff, alpha);
    }

    // ===== Suelo =====
    const ground = this.add.graphics();
    ground.fillGradientStyle(0x3d2b1f, 0x3d2b1f, 0x1a0e05, 0x1a0e05, 1);
    ground.fillRect(0, H * 0.78, W, H * 0.22);
    // Línea de horizonte
    ground.lineStyle(2, 0x8b6f47, 0.6);
    ground.beginPath();
    ground.moveTo(0, H * 0.78);
    ground.lineTo(W, H * 0.78);
    ground.strokePath();

    // ===== Título =====
    this.add
      .text(W / 2, 48, "DuckyEscape", {
        fontFamily: "monospace",
        fontSize: "46px",
        color: "#ffd54f",
        stroke: "#000",
        strokeThickness: 5,
      })
      .setOrigin(0.5);
    this.add
      .text(W / 2, 92, "Elige una temática para entrar", {
        fontFamily: "monospace",
        fontSize: "18px",
        color: "#b0b0cc",
      })
      .setOrigin(0.5);

    // ===== Pato =====
    this.player = this.createDuck(W / 2, H - 100);

    // ===== Hint text =====
    this.hint = this.add
      .text(W / 2, H - 30, "", {
        fontFamily: "monospace",
        fontSize: "20px",
        color: "#ffd54f",
        stroke: "#000",
        strokeThickness: 3,
      })
      .setOrigin(0.5);

    this.cursors = this.input.keyboard.createCursorKeys();
    this.enterKey = this.input.keyboard.addKey(
      Phaser.Input.Keyboard.KeyCodes.ENTER,
    );
    this.portals = [];
    this.overlayOpen = false;

    this.loadingText = this.add
      .text(W / 2, 360, "Cargando temáticas...", {
        fontFamily: "monospace",
        fontSize: "22px",
        color: "#fff",
      })
      .setOrigin(0.5);

    this.loadHub();
    Music.start();
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

  createDuck(x, y) {
    const duck = this.add.container(x, y);
    // Sombra bajo el pato
    const shadow = this.add.ellipse(0, 28, 50, 10, 0x000000, 0.35);
    // Patas
    const legL = this.add.ellipse(-8, 22, 6, 12, 0xff8f00);
    const legR = this.add.ellipse(8, 22, 6, 12, 0xff8f00);
    // Cuerpo
    const body = this.add.ellipse(0, 4, 50, 36, 0xffeb3b);
    // Ala
    const wing = this.add.ellipse(-6, 4, 24, 18, 0xffd54f);
    // Cabeza
    const head = this.add.circle(8, -18, 16, 0xffeb3b);
    // Pico
    const beak = this.add.triangle(26, -16, 0, 0, 16, 4, 0, 8, 0xff8f00);
    // Ojo
    const eye = this.add.circle(12, -22, 2.5, 0x000000);

    duck.add([shadow, legL, legR, body, wing, head, beak, eye]);

    this.physics.add.existing(duck);
    duck.body.setSize(50, 56);
    duck.body.setOffset(-25, -28);
    duck.body.setCollideWorldBounds(true);
    return duck;
  }

  async loadHub() {
    try {
      const res = await fetch("/escape/api/hub/", {
        headers: { Accept: "application/json" },
        credentials: "same-origin",
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      this.loadingText.destroy();
      this.renderPortals(data.themes);
    } catch (err) {
      this.loadingText.setText("Error cargando el hub: " + err.message);
      console.error(err);
    }
  }

  renderPortals(themes) {
    const PALETTE = {
      PRISON: { main: 0x8b4a4a, accent: 0xd47070 },
      SCHOOL: { main: 0x4a6b3a, accent: 0x7cb664 },
      LAB: { main: 0x3a5478, accent: 0x6490c4 },
    };

    const positions = this.spreadX(themes.length, 260);
    themes.forEach((theme, i) => {
      const x = positions[i];
      const y = 340;
      const available = theme.rooms.length > 0;
      const p = PALETTE[theme.key] || { main: 0x555555, accent: 0x888888 };

      // Sombra del portal
      this.add.rectangle(x + 5, y + 8, 200, 240, 0x000000, 0.45);
      // Fondo principal
      this.add.rectangle(x, y, 200, 240, p.main, available ? 1 : 0.4);
      // Panel interior
      const inner = this.add.rectangle(
        x,
        y - 25,
        160,
        150,
        p.accent,
        available ? 0.9 : 0.25,
      );
      inner.setStrokeStyle(2, 0x000000, 0.5);
      // Icono del tema
      const icon = this.add.graphics();
      this.drawThemeIcon(icon, theme.key, x, y - 30, available);
      // Marco exterior
      this.add
        .rectangle(x, y, 200, 240, 0x000000, 0)
        .setStrokeStyle(4, available ? 0xffd54f : 0x444444);

      // Etiqueta
      this.add
        .text(x, y + 72, theme.label, {
          fontFamily: "monospace",
          fontSize: "24px",
          color: available ? "#fff" : "#777",
          stroke: "#000",
          strokeThickness: 3,
        })
        .setOrigin(0.5);

      // Subtítulo
      const subtitle = available
        ? `${theme.rooms.length} aventura${theme.rooms.length > 1 ? "s" : ""}`
        : "Próximamente";
      this.add
        .text(x, y + 102, subtitle, {
          fontFamily: "monospace",
          fontSize: "15px",
          color: available ? "#ffd54f" : "#555",
        })
        .setOrigin(0.5);

      // Hitbox invisible para físicas
      const hitbox = this.add.rectangle(x, y, 200, 240, 0x000000, 0);
      this.physics.add.existing(hitbox, true);
      hitbox.themeData = theme;
      hitbox.themeAvailable = available;
      this.portals.push(hitbox);
    });
  }

  drawThemeIcon(g, key, cx, cy, available) {
    const color = available ? 0xffd54f : 0x555555;
    if (key === "PRISON") {
      // Barras de celda
      g.lineStyle(5, color, 1);
      for (let i = -1; i <= 1; i++) {
        g.beginPath();
        g.moveTo(cx + i * 18, cy - 32);
        g.lineTo(cx + i * 18, cy + 32);
        g.strokePath();
      }
      g.beginPath();
      g.moveTo(cx - 28, cy - 32);
      g.lineTo(cx + 28, cy - 32);
      g.moveTo(cx - 28, cy + 32);
      g.lineTo(cx + 28, cy + 32);
      g.strokePath();
    } else if (key === "SCHOOL") {
      // Columna griega
      g.fillStyle(color, 1);
      g.fillRect(cx - 32, cy + 28, 64, 8); // base
      g.fillRect(cx - 26, cy + 22, 52, 6);
      g.fillRect(cx - 18, cy - 20, 36, 42); // fuste
      g.fillRect(cx - 26, cy - 26, 52, 6);
      g.fillRect(cx - 32, cy - 32, 64, 6); // capitel
    } else if (key === "LAB") {
      // Matraz Erlenmeyer
      g.fillStyle(color, 1);
      g.beginPath();
      g.moveTo(cx - 10, cy - 28);
      g.lineTo(cx - 10, cy - 2);
      g.lineTo(cx - 28, cy + 30);
      g.lineTo(cx + 28, cy + 30);
      g.lineTo(cx + 10, cy - 2);
      g.lineTo(cx + 10, cy - 28);
      g.closePath();
      g.fillPath();
      // Tapón
      g.fillStyle(0x4a2e14, 1);
      g.fillRect(cx - 8, cy - 36, 16, 10);
      // Burbujas dentro
      g.fillStyle(0xffffff, 0.6);
      g.fillCircle(cx - 8, cy + 18, 3);
      g.fillCircle(cx + 5, cy + 22, 2);
      g.fillCircle(cx - 3, cy + 10, 2);
    }
  }

  spreadX(n, margin = 260) {
    const total = 1280;
    if (n <= 0) return [];
    if (n === 1) return [total / 2];
    const step = (total - 2 * margin) / (n - 1);
    return Array.from({ length: n }, (_, i) => margin + i * step);
  }

  update() {
    if (!this.player || !this.player.body) return;
    if (this.overlayOpen) {
      this.player.body.setVelocity(0);
      return;
    }

    const speed = 240;
    const body = this.player.body;
    body.setVelocity(0);
    if (this.cursors.left.isDown) body.setVelocityX(-speed);
    if (this.cursors.right.isDown) body.setVelocityX(speed);
    if (this.cursors.up.isDown) body.setVelocityY(-speed);
    if (this.cursors.down.isDown) body.setVelocityY(speed);

    let active = null;
    for (const portal of this.portals) {
      if (this.physics.overlap(this.player, portal)) {
        active = portal;
        break;
      }
    }
    this.activePortal = active;

    if (active) {
      if (active.themeAvailable) {
        this.hint.setText(
          `▶ Pulsa ENTER para entrar en: ${active.themeData.label}`,
        );
      } else {
        this.hint.setText(`${active.themeData.label} aún no tiene aventuras`);
      }
    } else {
      this.hint.setText("");
    }

    if (
      active &&
      active.themeAvailable &&
      Phaser.Input.Keyboard.JustDown(this.enterKey)
    ) {
      this.scene.start("ThemeScene", { theme: active.themeData });
    }
  }
}
