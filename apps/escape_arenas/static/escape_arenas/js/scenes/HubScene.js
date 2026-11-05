export default class HubScene extends Phaser.Scene {
  constructor() {
    super("HubScene");
  }

  create() {
    // Título de debug
    this.add
      .text(640, 40, "DuckyEscape — Hub (spike)", {
        fontFamily: "monospace",
        fontSize: "28px",
        color: "#ffd54f",
      })
      .setOrigin(0.5);

    // Tres "portales" temporales como rectángulos de colores
    const themes = [
      { key: "PRISON", label: "Cárcel", x: 320, y: 360, color: 0xe57373 },
      { key: "SCHOOL", label: "Colegio", x: 640, y: 360, color: 0x81c784 },
      { key: "LAB", label: "Laboratorio", x: 960, y: 360, color: 0x64b5f6 },
    ];
    this.portals = themes.map((t) => {
      const rect = this.add
        .rectangle(t.x, t.y, 180, 220, t.color)
        .setStrokeStyle(4, 0xffffff);
      this.add
        .text(t.x, t.y + 140, t.label, {
          fontFamily: "monospace",
          fontSize: "22px",
          color: "#fff",
        })
        .setOrigin(0.5);
      rect.themeKey = t.key;
      return this.physics.add.existing(rect, true);
    });

    // Pato: un rectángulo amarillo que se moverá con las flechas
    this.player = this.add.rectangle(640, 600, 40, 40, 0xffeb3b);
    this.physics.add.existing(this.player);
    this.player.body.setCollideWorldBounds(true);

    // Overlap: si el pato pisa un portal, texto de aviso
    this.hint = this.add
      .text(640, 680, "", {
        fontFamily: "monospace",
        fontSize: "20px",
        color: "#fff",
      })
      .setOrigin(0.5);

    this.physics.add.overlap(this.player, this.portals, (_p, portal) => {
      this.hint.setText(`Pulsa ENTER para entrar en: ${portal.themeKey}`);
      this.activePortal = portal;
    });

    this.cursors = this.input.keyboard.createCursorKeys();
    this.enterKey = this.input.keyboard.addKey(
      Phaser.Input.Keyboard.KeyCodes.ENTER,
    );
  }

  update() {
    const speed = 240;
    const body = this.player.body;
    body.setVelocity(0);

    if (this.cursors.left.isDown) body.setVelocityX(-speed);
    if (this.cursors.right.isDown) body.setVelocityX(speed);
    if (this.cursors.up.isDown) body.setVelocityY(-speed);
    if (this.cursors.down.isDown) body.setVelocityY(speed);

    // Limpieza del aviso si ya no solapa
    if (!this.physics.overlap(this.player, this.portals)) {
      this.hint.setText("");
      this.activePortal = null;
    }

    if (this.activePortal && Phaser.Input.Keyboard.JustDown(this.enterKey)) {
      console.log("Entrando en el tema:", this.activePortal.themeKey);
      // En el Paso 4 esto hará: this.scene.start("ThemeScene", { theme: this.activePortal.themeKey });
    }
  }
}
