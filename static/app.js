document.querySelectorAll('form').forEach(form => {
  form.addEventListener('submit', event => {
    if (form.dataset.confirm && !window.confirm(form.dataset.confirm)) {
      event.preventDefault(); return;
    }
    const button = event.submitter;
    if (button) {
      button.disabled = true;
      button.dataset.original = button.textContent;
      button.textContent = 'Memproses…';
      // Unduhan tidak mengganti halaman. Izinkan unduh ulang setelah permintaan dimulai.
      setTimeout(() => {button.disabled=false;button.textContent=button.dataset.original;}, 4000);
    }
  });
});
document.querySelectorAll('[data-back]').forEach(button => button.addEventListener('click', () => history.length > 1 ? history.back() : location.assign('/')));
window.addEventListener('pageshow', () => document.querySelectorAll('button[data-original]').forEach(button => {button.disabled=false;button.textContent=button.dataset.original;}));

document.querySelectorAll('[data-password-toggle]').forEach(button => {
  const input = document.getElementById(button.dataset.passwordToggle);
  if (!input) return;
  button.hidden = false;
  button.addEventListener('click', () => {
    const visible = input.type === 'password';
    input.type = visible ? 'text' : 'password';
    button.setAttribute('aria-pressed', String(visible));
    button.setAttribute('aria-label', visible ? 'Sembunyikan kata sandi' : 'Tampilkan kata sandi');
  });
});

const startCamera = document.getElementById('start-camera');
if (startCamera) {
  const stopCamera = document.getElementById('stop-camera');
  const video = document.getElementById('camera');
  const status = document.getElementById('scanner-status');
  let stream;
  let running = false;

  function stop() {
    running = false;
    if (stream) stream.getTracks().forEach(track => track.stop());
    video.srcObject = null;
    startCamera.disabled = false;
    stopCamera.disabled = true;
  }

  startCamera.addEventListener('click', async () => {
    if (!('BarcodeDetector' in window) || !navigator.mediaDevices) {
      status.textContent = 'Pemindai kamera belum didukung pada browser ini. Gunakan pencarian manual atau pemindai QR bawaan ponsel.';
      return;
    }
    try {
      const detector = new BarcodeDetector({formats: ['qr_code']});
      stream = await navigator.mediaDevices.getUserMedia({video: {facingMode: 'environment'}});
      video.srcObject = stream;
      await video.play();
      running = true;
      startCamera.disabled = true;
      stopCamera.disabled = false;
      status.textContent = 'Arahkan kamera ke QR pada kartu peserta.';
      async function scanFrame() {
        if (!running) return;
        try {
          const codes = await detector.detect(video);
          for (const code of codes) {
            const url = new URL(code.rawValue, location.origin);
            if (url.origin === location.origin && /^\/absensi\/[A-Za-z0-9_-]+$/.test(url.pathname)) {
              stop();
              location.assign(url.pathname);
              return;
            }
            status.textContent = 'QR ini bukan kartu peserta dari portal ini.';
          }
        } catch (_) {
          status.textContent = 'QR belum terbaca. Dekatkan kartu atau gunakan pencarian manual.';
        }
        if (running) setTimeout(scanFrame, 300);
      }
      scanFrame();
    } catch (_) {
      stop();
      status.textContent = 'Kamera tidak dapat diakses. Periksa izin browser atau gunakan pencarian manual.';
    }
  });
  stopCamera.addEventListener('click', () => {stop();status.textContent = 'Kamera dihentikan.';});
  window.addEventListener('pagehide', stop);
}

// Rincian biaya: setiap nama dan nominal dikirim sebagai pasangan ke server.
document.querySelectorAll('[data-fee-editor]').forEach(editor => {
  const rows = editor.querySelector('[data-fee-rows]');
  const add = editor.querySelector('[data-fee-add]');
  const currency = new Intl.NumberFormat('id-ID', {style: 'currency', currency: 'IDR', maximumFractionDigits: 0});
  function update() {
    const items = [...rows.children];
    let total = 0;
    items.forEach(row => {
      const input = row.querySelector('[name="component_amount"]');
      if (input.validity.valid && input.value) total += Number(input.value);
      row.querySelector('[data-fee-remove]').disabled = items.length === 1;
    });
    editor.querySelector('[data-fee-total]').textContent = currency.format(total);
    add.disabled = items.length >= 100;
  }
  add.addEventListener('click', () => {
    if (rows.children.length >= 100) return;
    const row = rows.firstElementChild.cloneNode(true);
    row.querySelectorAll('input').forEach(input => {input.value = '';});
    rows.append(row);
    update();
    row.querySelector('input').focus();
  });
  rows.addEventListener('click', event => {
    const remove = event.target.closest('[data-fee-remove]');
    if (remove && rows.children.length > 1) {
      remove.closest('.fee-row').remove();
      update();
      add.focus();
    }
  });
  rows.addEventListener('input', update);
  update();
});
