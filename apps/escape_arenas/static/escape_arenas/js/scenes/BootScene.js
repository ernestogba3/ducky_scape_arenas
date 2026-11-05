export default class BootScene extends Phaser.Scene {
  constructor() {
    super("BootScene");
  }

  preload() {
    // De momento no cargamos assets reales; usamos rectángulos.
    // Cuando tengamos sprites:
    // this.load.image("duck", DUCKY.staticBase + "img/duck.png");
  }

  create() {
    this.scene.start("HubScene");
  }
}
