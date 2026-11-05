export default class HubScene extends Phaser.Scene {
  constructor() {
    super("HubScene");
  }

  create() {
    // Título
    this.add
      .text(640, 40, "DuckyEscape", {
        fontFamily: "monospace",
        fontSize: "32px",
        color: "#ffd54f",
      })
      .setOrigin(0.5);
    this.add
      .text(640, 78, "Elige temática", {
        fontFamily: "monospace",
        fontSize: "18px",
        color: "#aaa",
      })
      .setOrigin(0.5);

    // Pato (placeholder)
    this.player = this.add.rectangle(640, 600, 40, 40, 0xffeb3b);
    this.physics.add.existing(this.player);
    this.player.body.setCollideWorldBounds(true);

    this.hint = this.add
      .text(640, 680, "", {
        fontFamily: "monospace",
        fontSize: "20px",
        color: "#fff",
      })
      .setOrigin(0.5);

    this.cursors = this.input.keyboard.createCursorKeys();
    this.enterKey = this.input.keyboard.addKey(
      Phaser.Input.Keyboard.KeyCodes.ENTER,
    );

    this.portals = [];
    this.overlayOpen = false;

    // Estado inicial: cargando
    this.loadingText = this.add
      .text(640, 360, "Cargando temáticas...", {
        fontFamily: "monospace",
        fontSize: "22px",
        color: "#fff",
      })
      .setOrigin(0.5);

    this.loadHub();
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
    const COLORS = {
      PRISON: 0xe57373,
      SCHOOL: 0x81c784,
      LAB: 0x64b5f6,
    };

    const positions = this.spreadX(themes.length, 260);
    themes.forEach((theme, i) => {
      const x = positions[i];
      const y = 340;
      const available = theme.rooms.length > 0;
      const baseColor = COLORS[theme.key] || 0x9e9e9e;

      // Portal (rectángulo grande)
      const rect = this.add
        .rectangle(x, y, 200, 240, baseColor, available ? 1 : 0.3)
        .setStrokeStyle(4, available ? 0xffffff : 0x555555);

      // Etiqueta del tema
      this.add
        .text(x, y + 150, theme.label, {
          fontFamily: "monospace",
          fontSize: "24px",
          color: available ? "#fff" : "#777",
        })
        .setOrigin(0.5);

      // Subtítulo: nº de aventuras o "Próximamente"
      const subtitle = available
        ? `${theme.rooms.length} aventura${theme.rooms.length > 1 ? "s" : ""}`
        : "Próximamente";
      this.add
        .text(x, y + 180, subtitle, {
          fontFamily: "monospace",
          fontSize: "16px",
          color: available ? "#ffd54f" : "#555",
        })
        .setOrigin(0.5);

      this.physics.add.existing(rect, true); // static body
      rect.themeData = theme;
      rect.themeAvailable = available;
      this.portals.push(rect);
    });
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

    // Si hay overlay abierto, el pato se queda quieto
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

    // Detectar portal bajo el pato
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
          `Pulsa ENTER para entrar en: ${active.themeData.label}`,
        );
      } else {
        this.hint.setText(
          `${active.themeData.label} aún no tiene aventuras disponibles`,
        );
      }
    } else {
      this.hint.setText("");
    }

    if (
      active &&
      active.themeAvailable &&
      Phaser.Input.Keyboard.JustDown(this.enterKey)
    ) {
      this.showThemeOverview(active.themeData);
    }
  }

  showThemeOverview(theme) {
    this.overlayOpen = true;

    const bg = this.add.rectangle(640, 360, 1280, 720, 0x000000, 0.8);
    const title = this.add
      .text(640, 110, theme.label, {
        fontFamily: "monospace",
        fontSize: "44px",
        color: "#ffd54f",
      })
      .setOrigin(0.5);
    const subtitle = this.add
      .text(
        640,
        160,
        `${theme.rooms.length} aventura${theme.rooms.length > 1 ? "s" : ""} disponible${theme.rooms.length > 1 ? "s" : ""}`,
        { fontFamily: "monospace", fontSize: "18px", color: "#ccc" },
      )
      .setOrigin(0.5);

    const items = theme.rooms.map((room, i) => {
      const y = 230 + i * 56;
      return this.add
        .text(
          640,
          y,
          `Era ${room.era} · ${room.era_display}   —   ${room.name}`,
          { fontFamily: "monospace", fontSize: "20px", color: "#fff" },
        )
        .setOrigin(0.5);
    });

    const footer = this.add
      .text(640, 650, "Pulsa ESC para volver", {
        fontFamily: "monospace",
        fontSize: "16px",
        color: "#888",
      })
      .setOrigin(0.5);

    const escKey = this.input.keyboard.addKey(
      Phaser.Input.Keyboard.KeyCodes.ESC,
    );
    escKey.once("down", () => {
      bg.destroy();
      title.destroy();
      subtitle.destroy();
      items.forEach((t) => t.destroy());
      footer.destroy();
      this.overlayOpen = false;
    });
  }
}
