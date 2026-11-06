export default class BootScene extends Phaser.Scene {
  constructor() {
    super("BootScene");
  }

  preload() {
    const base = window.DUCKY.staticBase + "img/duck/";
    this.load.image("duck-down", base + "duck-down.png");
    this.load.image("duck-up", base + "duck-up.png");
    this.load.image("duck-left", base + "duck-left.png");
    this.load.image("duck-right", base + "duck-right.png");
  }

  create() {
    this.scene.start("HubScene");
  }
}
