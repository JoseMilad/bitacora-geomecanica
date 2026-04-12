/* ═══════════════════════════════════════════════════════════
   Bitácora Geomecánica — main.js
   ═══════════════════════════════════════════════════════════ */

// ── Reusable Labor Typeahead Component ───────────────────────────────────────
/**
 * Initializes a typeahead autocomplete on a text input for labor filtering.
 * @param {string} inputId - ID of the text input element
 * @param {string} dropdownId - ID of the dropdown container element
 * @param {string[]} laboresList - Array of labor names
 * @param {object} [options] - Optional config
 * @param {function} [options.onSelect] - Callback when a labor is selected
 * @param {boolean} [options.showAll] - Show "Todas las labores" option (default: false)
 * @param {number} [options.maxResults] - Max results to show (default: 10)
 */
function initLaborTypeahead(inputId, dropdownId, laboresList, options) {
  const input = document.getElementById(inputId);
  const dropdown = document.getElementById(dropdownId);
  if (!input || !dropdown) return;

  const opts = Object.assign({ onSelect: null, showAll: false, maxResults: 10 }, options || {});

  function filterAndShow(texto) {
    dropdown.innerHTML = '';
    const filtradas = texto
      ? laboresList.filter(function(l) { return l.toLowerCase().includes(texto.toLowerCase()); })
      : laboresList;

    if (opts.showAll) {
      var allItem = document.createElement('a');
      allItem.href = '#';
      allItem.className = 'list-group-item list-group-item-action py-2 px-3';
      allItem.style.fontSize = '0.9rem';
      allItem.innerHTML = '<em class="text-muted">Todas las labores</em>';
      allItem.addEventListener('click', function(e) {
        e.preventDefault();
        input.value = '';
        dropdown.style.display = 'none';
        if (opts.onSelect) opts.onSelect('');
      });
      dropdown.appendChild(allItem);
    }

    if (filtradas.length === 0 && !opts.showAll) {
      dropdown.style.display = 'none';
      return;
    }

    filtradas.slice(0, opts.maxResults).forEach(function(labor) {
      var item = document.createElement('a');
      item.href = '#';
      item.className = 'list-group-item list-group-item-action py-2 px-3';
      item.style.fontSize = '0.9rem';
      item.textContent = labor;
      item.addEventListener('click', function(e) {
        e.preventDefault();
        input.value = labor;
        dropdown.style.display = 'none';
        if (opts.onSelect) opts.onSelect(labor);
      });
      dropdown.appendChild(item);
    });
    dropdown.style.display = 'block';
  }

  input.addEventListener('input', function() { filterAndShow(this.value); });
  input.addEventListener('focus', function() { filterAndShow(this.value); });

  document.addEventListener('click', function(e) {
    if (!dropdown.contains(e.target) && e.target !== input) {
      dropdown.style.display = 'none';
    }
  });
}

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
      // Sync preference to server config (fire-and-forget)
      fetch('/configuracion/modo-oscuro', {
        method: 'POST',
        headers: {'Content-Type': 'application/x-www-form-urlencoded'},
        body: 'modo_oscuro=' + (activo ? 'on' : 'off'),
      }).catch(function() {});
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
