const applicationMenu = document.getElementById('app-menu-dialog');
if (applicationMenu) {
  document.querySelectorAll('[data-app-menu-open]').forEach(button => {
    button.addEventListener('click', event => {
      if (typeof applicationMenu.showModal !== 'function') return;
      event.preventDefault();
      applicationMenu.showModal();
    });
  });
  document.querySelectorAll('[data-app-menu-close]').forEach(button => {
    button.addEventListener('click', () => applicationMenu.close());
  });
  applicationMenu.addEventListener('click', event => {
    if (event.target === applicationMenu || event.target.closest('a[href]')) applicationMenu.close();
  });
}

// Pertahankan tautan kartu/pesan lama yang masih memakai penanda bagian.
const oldSections = new Set(['biodata','jadwal','hasil','berkas','pembayaran','dokumen','notifikasi','absensi']);
const oldParticipantPath = location.pathname.match(/^\/peserta\/(\d+)$/);
const oldSection = location.hash.slice(1);
if (oldParticipantPath && oldSections.has(oldSection)) {
  location.replace(`/peserta/${oldParticipantPath[1]}/menu/${oldSection}`);
}

document.querySelectorAll('[data-parent-fields]').forEach(group => {
  const unavailable = group.querySelector('[data-parent-unavailable]');
  const note = group.querySelector('[data-parent-note]');
  function updateRequired() {
    group.querySelectorAll('.formgrid input, .formgrid select').forEach(field => {
      field.required = !unavailable.checked;
    });
    note.required = unavailable.checked;
  }
  unavailable.addEventListener('change', updateRequired);
  updateRequired();
});

document.querySelectorAll('[data-mi-school]').forEach(form => {
  const fields = [...form.querySelectorAll('[name="school"], [name="school_address"], [name="school_npsn"]')];
  function updateRequired() {
    const hasSchool = fields.some(field => field.value.trim());
    fields.forEach(field => {field.required = hasSchool;});
  }
  fields.forEach(field => field.addEventListener('input', updateRequired));
  updateRequired();
});
