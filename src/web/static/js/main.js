/* ═══════════════════════════════════════════════════════════
   Bitácora Geomecánica — main.js
   ═══════════════════════════════════════════════════════════ */

// ── Autocompletar datos de labor ──────────────────────────────────────────────
async function autocompletarLabor(nombre) {
  if (!nombre) return;
  try {
    const res = await fetch(`/labores/${encodeURIComponent(nombre)}/datos`);
    if (!res.ok) return;
    const datos = await res.json();
    if (datos.error) return;

    const gsiInput    = document.getElementById('inputGSI');
    const rmrInput    = document.getElementById('inputRMR');
    const soporteInput = document.getElementById('inputSoporte');
    const infoLbl     = document.getElementById('infoUltimoRegistro');

    if (gsiInput && datos.GSI !== undefined)     gsiInput.value    = datos.GSI    || '';
    if (rmrInput && datos.RMR !== undefined)     rmrInput.value    = datos.RMR    || '';
    if (soporteInput && datos.Soporte !== undefined) soporteInput.value = datos.Soporte || '';
    if (infoLbl && datos.Tipo)  infoLbl.textContent = `Tipo: ${datos.Tipo}`;

    // Si RMR fue rellenado, calcular soporte
    if (rmrInput && rmrInput.value && typeof calcularSoporte === 'function') {
      setTimeout(calcularSoporte, 200);
    }
  } catch (err) {
    console.warn('autocompletarLabor error:', err);
  }
}

// ── Confirmar eliminación (bitácora / sostenimiento) ─────────────────────────
function confirmarEliminacion(id, tipo) {
  const modalEl = document.getElementById('modalEliminar');
  if (!modalEl) return;
  const form = document.getElementById('formEliminar');
  if (form) {
    form.action = `/${tipo}/${id}/eliminar`;
  }
  const modal = new bootstrap.Modal(modalEl);
  modal.show();
}

// ── Modo Oscuro ───────────────────────────────────────────────────────────────
function aplicarModoOscuro(activo) {
  const html = document.documentElement;
  const icon = document.getElementById('darkModeIcon');
  if (activo) {
    html.classList.add('dark-mode');
    if (icon) { icon.className = 'fa-solid fa-sun'; }
  } else {
    html.classList.remove('dark-mode');
    if (icon) { icon.className = 'fa-solid fa-moon'; }
  }
}

// ── Toggle sidebar ────────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', function () {
  // Inicializar tooltips de Bootstrap
  const tooltipEls = document.querySelectorAll('[data-bs-toggle="tooltip"]');
  tooltipEls.forEach(el => new bootstrap.Tooltip(el));

  // Toggle sidebar
  const toggleBtn = document.getElementById('sidebarToggle');
  const sidebar   = document.getElementById('sidebar');
  if (toggleBtn && sidebar) {
    toggleBtn.addEventListener('click', function () {
      sidebar.classList.toggle('collapsed');
    });
  }

  // Dark mode: inicializar desde localStorage
  const darkSaved = localStorage.getItem('bitacoraGeo_darkMode') === 'true';
  aplicarModoOscuro(darkSaved);

  // Dark mode toggle button
  const dmBtn = document.getElementById('darkModeToggle');
  if (dmBtn) {
    dmBtn.addEventListener('click', function () {
      const activo = !document.documentElement.classList.contains('dark-mode');
      aplicarModoOscuro(activo);
      localStorage.setItem('bitacoraGeo_darkMode', activo ? 'true' : 'false');
    });
  }

  // Auto-cerrar alertas después de 5 s (excepto warnings, que requieren acción del usuario)
  const alerts = document.querySelectorAll('.alert:not(.alert-warning)');
  alerts.forEach(alert => {
    setTimeout(() => {
      const bsAlert = bootstrap.Alert.getOrCreateInstance(alert);
      if (bsAlert) bsAlert.close();
    }, 5000);
  });
});
