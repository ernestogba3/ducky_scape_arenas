import BootScene from "./scenes/BootScene.js";
import HubScene from "./scenes/HubScene.js";
import ThemeScene from "./scenes/ThemeScene.js";

const config = {
  type: Phaser.AUTO,
  parent: "game",
  width: 1280,
  height: 720,
  backgroundColor: "#1a1a2e",
  pixelArt: true,
  scale: {
    mode: Phaser.Scale.FIT,
    autoCenter: Phaser.Scale.CENTER_BOTH,
  },
  physics: {
    default: "arcade",
    arcade: { debug: false },
  },
  scene: [BootScene, HubScene, ThemeScene],
};

new Phaser.Game(config);
