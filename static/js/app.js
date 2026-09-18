const menuToggle = document.getElementById('menuToggle');
const nav = document.getElementById('mainNav');
const modal = document.getElementById('joinGame');
const toast = document.getElementById('toast');

menuToggle.addEventListener('click', () => {
  const open = nav.classList.toggle('open');
  menuToggle.setAttribute('aria-expanded', open);
});

document.querySelectorAll('.nav a').forEach(link => {
  link.addEventListener('click', () => {
    document.querySelectorAll('.nav a').forEach(a => a.classList.remove('active'));
    link.classList.add('active');
    nav.classList.remove('open');
  });
});

document.querySelectorAll('[data-modal]').forEach(button => {
  button.addEventListener('click', () => {
    modal.classList.add('open');
    modal.setAttribute('aria-hidden', 'false');
    document.getElementById('gameCode').focus();
  });
});

function closeModal() {
  modal.classList.remove('open');
  modal.setAttribute('aria-hidden', 'true');
}
document.querySelector('.modal-close').addEventListener('click', closeModal);
modal.addEventListener('click', e => { if (e.target === modal) closeModal(); });

function showToast(message) {
  toast.textContent = message;
  toast.classList.add('show');
  setTimeout(() => toast.classList.remove('show'), 2600);
}

document.querySelectorAll('[data-toast]').forEach(button => {
  button.addEventListener('click', () => showToast(button.dataset.toast));
});

document.getElementById('joinForm').addEventListener('submit', e => {
  e.preventDefault();
  const code = document.getElementById('gameCode').value.trim();
  if (!/^\d{6}$/.test(code)) {
    showToast('Introduce un código válido de 6 dígitos.');
    return;
  }
  closeModal();
  showToast(`Entrando en la partida ${code}…`);
});
