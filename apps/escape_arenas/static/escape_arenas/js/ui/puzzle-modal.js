// Overlay HTML flotante encima del canvas de Phaser.
// Expone openPuzzleModal(state, handlers) que devuelve una api
// para que RoomScene actualice el modal según respuestas del backend.

export function openPuzzleModal(state, handlers) {
  const { puzzle, hint } = state;
  const { onSubmit, onHintRequest, onCancel } = handlers;

  // Limpia modal previo si quedara
  const prev = document.getElementById("puzzle-modal");
  if (prev) prev.remove();

  // Backdrop
  const overlay = document.createElement("div");
  overlay.id = "puzzle-modal";
  overlay.style.cssText = `
    position: fixed; inset: 0; background: rgba(0,0,0,0.85);
    display: flex; align-items: center; justify-content: center;
    z-index: 1000; font-family: monospace;`;

  // Panel central
  const panel = document.createElement("div");
  panel.style.cssText = `
    background: #2a2a44; border: 4px solid #ffd54f; border-radius: 8px;
    padding: 28px 32px; width: 92%; max-width: 640px; color: #fff;
    box-shadow: 0 10px 40px rgba(0,0,0,0.8); box-sizing: border-box;`;

  // Título
  const titleEl = document.createElement("h2");
  titleEl.textContent = puzzle.title;
  titleEl.style.cssText = "margin: 0 0 6px; color: #ffd54f; font-size: 26px;";
  panel.appendChild(titleEl);

  // Intentos
  if (puzzle.max_attempts) {
    const att = document.createElement("div");
    att.textContent = `Intentos: ${puzzle.attempts_used} / ${puzzle.max_attempts}`;
    att.style.cssText = "font-size: 13px; color: #aaa; margin-bottom: 16px;";
    panel.appendChild(att);
  } else {
    const spacer = document.createElement("div");
    spacer.style.cssText = "height: 8px;";
    panel.appendChild(spacer);
  }

  // Descripción
  const desc = document.createElement("p");
  desc.textContent = puzzle.description;
  desc.style.cssText =
    "margin: 0 0 20px; font-size: 15px; line-height: 1.5; color: #ddd;";
  panel.appendChild(desc);

  // Respuesta (según tipo)
  let getAnswer, inputEl;
  if (puzzle.type === "MULTIPLE_CHOICE") {
    const optsBox = document.createElement("div");
    puzzle.options.forEach((opt, i) => {
      const label = document.createElement("label");
      label.style.cssText = `
        display: block; padding: 12px; margin-bottom: 8px;
        background: #1a1a30; border: 2px solid #444; border-radius: 4px;
        cursor: pointer; font-size: 15px;`;
      const radio = document.createElement("input");
      radio.type = "radio";
      radio.name = "answer";
      radio.value = opt;
      if (i === 0) radio.checked = true;
      radio.style.marginRight = "10px";
      label.appendChild(radio);
      label.appendChild(document.createTextNode(opt));
      optsBox.appendChild(label);
    });
    panel.appendChild(optsBox);
    getAnswer = () => {
      const c = panel.querySelector('input[name="answer"]:checked');
      return c ? c.value : "";
    };
  } else {
    inputEl = document.createElement("input");
    inputEl.type = puzzle.type === "NUMBER" ? "number" : "text";
    inputEl.placeholder = "Escribe tu respuesta...";
    inputEl.autocomplete = "off";
    inputEl.style.cssText = `
      width: 100%; padding: 14px; font-size: 18px; background: #1a1a30;
      border: 2px solid #ffd54f; border-radius: 4px; color: #fff;
      font-family: monospace; box-sizing: border-box;`;
    panel.appendChild(inputEl);
    getAnswer = () => inputEl.value;
    setTimeout(() => inputEl.focus(), 50);
    inputEl.addEventListener("keydown", (e) => {
      if (e.key === "Enter") submitBtn.click();
    });
  }

  // Feedback
  const feedback = document.createElement("div");
  feedback.style.cssText =
    "min-height: 24px; margin: 16px 0 10px; text-align: center; font-size: 15px; font-weight: bold;";
  panel.appendChild(feedback);

  // Área donde se insertará el texto de la pista al usarla
  const hintBox = document.createElement("div");
  panel.appendChild(hintBox);

  // Botones
  const btnBar = document.createElement("div");
  btnBar.style.cssText =
    "display: flex; gap: 12px; justify-content: space-between; margin-top: 12px;";

  const mkBtn = (label, bg, color = "#000") => {
    const b = document.createElement("button");
    b.textContent = label;
    b.style.cssText = `
      padding: 12px 20px; font-size: 15px; font-family: monospace;
      background: ${bg}; color: ${color}; border: none; border-radius: 4px;
      cursor: pointer; font-weight: bold;`;
    return b;
  };

  const hintBtn = mkBtn(
    hint ? "💡 Pista" : "Sin pistas",
    hint ? "#64b5f6" : "#555",
    "#fff",
  );
  if (!hint) {
    hintBtn.disabled = true;
    hintBtn.style.cursor = "not-allowed";
    hintBtn.style.opacity = "0.6";
  }
  const cancelBtn = mkBtn("Cancelar", "#555", "#fff");
  const submitBtn = mkBtn("Enviar ▶", "#ffd54f");

  btnBar.appendChild(hintBtn);
  const right = document.createElement("div");
  right.style.cssText = "display: flex; gap: 12px;";
  right.appendChild(cancelBtn);
  right.appendChild(submitBtn);
  btnBar.appendChild(right);
  panel.appendChild(btnBar);

  overlay.appendChild(panel);
  document.body.appendChild(overlay);

  // Keyframes para shake (una sola vez)
  if (!document.getElementById("puzzle-modal-styles")) {
    const style = document.createElement("style");
    style.id = "puzzle-modal-styles";
    style.textContent = `
      @keyframes shake-panel {
        0%, 100% { transform: translateX(0); }
        20% { transform: translateX(-12px); }
        40% { transform: translateX(12px); }
        60% { transform: translateX(-8px); }
        80% { transform: translateX(8px); }
      }`;
    document.head.appendChild(style);
  }

  // ESC cierra
  function onKey(e) {
    if (e.key === "Escape") {
      e.preventDefault();
      api.close();
      onCancel();
    }
  }
  document.addEventListener("keydown", onKey);

  // API expuesta a RoomScene
  const api = {
    showFeedback(text, color) {
      feedback.textContent = text;
      feedback.style.color = color;
    },
    shake() {
      panel.style.animation = "shake-panel 0.4s";
      setTimeout(() => {
        panel.style.animation = "";
      }, 420);
    },
    disable() {
      submitBtn.disabled = true;
      submitBtn.style.opacity = "0.5";
      hintBtn.disabled = true;
      hintBtn.style.opacity = "0.5";
    },
    enable() {
      submitBtn.disabled = false;
      submitBtn.style.opacity = "1";
      if (hint) {
        hintBtn.disabled = false;
        hintBtn.style.opacity = "1";
      }
      if (inputEl) {
        inputEl.focus();
        inputEl.select && inputEl.select();
      }
    },
    appendHintText(text) {
      const h = document.createElement("div");
      h.innerHTML = "💡 " + text;
      h.style.cssText = `
        margin-top: 8px; padding: 12px; background: #1a2a44;
        border-left: 4px solid #64b5f6; color: #cde; font-size: 14px;
        line-height: 1.5;`;
      hintBox.appendChild(h);
      hintBtn.disabled = true;
      hintBtn.style.opacity = "0.5";
      hintBtn.textContent = "Pista usada";
    },
    close() {
      document.removeEventListener("keydown", onKey);
      overlay.remove();
    },
  };

  submitBtn.addEventListener("click", () => {
    const ans = getAnswer().toString().trim();
    if (!ans) {
      api.showFeedback("Escribe una respuesta", "#ff9800");
      return;
    }
    onSubmit(ans, api);
  });
  hintBtn.addEventListener("click", () => {
    if (hint) onHintRequest(api);
  });
  cancelBtn.addEventListener("click", () => {
    api.close();
    onCancel();
  });

  return api;
}
