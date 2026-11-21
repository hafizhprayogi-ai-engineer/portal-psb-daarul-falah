(() => {
  const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)');
  const detailsStates = new Map();
  let restoredPageAnimation;

  // Batalkan efek sebelum mengukur ulang, lalu lepaskan tinggi yang dianimasikan.
  function finishDetails(details, state) {
    if (state.animation) {
      state.animation.onfinish = null;
      state.animation.cancel();
      state.animation = null;
    }
    details.open = state.wantOpen;
    details.classList.remove('details-animating');
  }

  function settleDetails() {
    detailsStates.forEach((state, details) => {
      if (state.animation) finishDetails(details, state);
    });
  }

  document.querySelectorAll('details').forEach(details => {
    const summary = details.querySelector(':scope > summary');
    if (!summary) return;
    const state = { wantOpen: details.open, animation: null };
    detailsStates.set(details, state);

    details.addEventListener('toggle', () => {
      if (!state.animation) state.wantOpen = details.open;
    });

    summary.addEventListener('click', event => {
      if (event.defaultPrevented || reducedMotion.matches || !details.animate) return;
      if (event.target.closest('a, button, input, select, textarea, label')) return;
      event.preventDefault();

      const startHeight = details.getBoundingClientRect().height;
      const opening = !(state.animation ? state.wantOpen : details.open);
      if (state.animation) {
        state.animation.onfinish = null;
        state.animation.cancel();
        state.animation = null;
      }
      state.wantOpen = opening;

      // Pengukuran tertutup/terbuka selesai dalam satu frame sebelum browser melukis.
      details.classList.remove('details-animating');
      details.open = opening;
      const endHeight = details.getBoundingClientRect().height;
      details.open = true;
      details.classList.add('details-animating');

      try {
        state.animation = details.animate(
          [{ height: `${startHeight}px` }, { height: `${endHeight}px` }],
          { duration: 220, easing: 'cubic-bezier(0.2, 0.7, 0.2, 1)' }
        );
        state.animation.onfinish = () => finishDetails(details, state);
      } catch (_) {
        finishDetails(details, state);
      }
    });
  });

  reducedMotion.addEventListener('change', () => {
    if (reducedMotion.matches) {
      settleDetails();
      restoredPageAnimation?.cancel();
    }
  });

  window.addEventListener('resize', settleDetails, { passive: true });
  window.addEventListener('pagehide', settleDetails);

  // Halaman yang dipulihkan dari cache riwayat harus langsung dapat digunakan.
  window.addEventListener('pageshow', event => {
    settleDetails();
    const main = document.getElementById('utama');
    if (event.persisted && main?.animate && !reducedMotion.matches) {
      restoredPageAnimation?.cancel();
      restoredPageAnimation = main.animate(
        [{ opacity: 0.65 }, { opacity: 1 }],
        { duration: 180, easing: 'ease-out' }
      );
    }
  });
})();
