/* ═══════════════════════════════════════════════════════════
   RockLog — main.js
   ═══════════════════════════════════════════════════════════ */

// ── Browser timezone auto-detection ──────────────────────────────────────────
// Detect the user's local timezone and store it in a cookie so the server can
// use it when auto-selecting the current shift (Día/Noche).
(function () {
  try {
    var tz = Intl.DateTimeFormat().resolvedOptions().timeZone;
    if (tz) {
      document.cookie = 'user_tz=' + encodeURIComponent(tz) + '; path=/; SameSite=Lax; max-age=' + (365 * 24 * 3600);
    }
  } catch (e) { /* ignore */ }
})();
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
      const allItem = document.createElement('a');
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
      const item = document.createElement('a');
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
    let soporteLabor = '';
    if (soporteInput && datos.Soporte !== undefined) {
      soporteInput.value = datos.Soporte || '';
      soporteLabor = (datos.Soporte || '').toString().trim();
    }
    if (infoLbl && datos.Tipo)  infoLbl.textContent = `Tipo: ${datos.Tipo}`;

    // Issue 2: Pre-select the reference system stored for this labor
    const sistemaRef = datos.Sistema_Referencia || '';
    if (sistemaRef) {
      const selRef = document.getElementById('selectSistemaReferencia');
      if (selRef) {
        // Only update if the labor's system is in the list
        const opt = Array.from(selRef.options).find(o => o.value === sistemaRef);
        if (opt) {
          selRef.value = sistemaRef;
          // Sync the hidden field
          const hidden = document.getElementById('hiddenSistemaRefBitacora');
          if (hidden) hidden.value = sistemaRef;
        }
      }
    }

    // Si hay un campo de referencia activo y tiene valor, calcular soporte
    if (typeof calcularSoporte === 'function' && !soporteLabor) {
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

// ── Toast Notifications ───────────────────────────────────────────────────────
/**
 * Muestra una notificación toast estética.
 * @param {string} message - Mensaje a mostrar
 * @param {string} type - Tipo: 'success', 'error', 'warning', 'info'
 * @param {string} [title] - Título opcional
 * @param {number} [duration] - Duración en ms (default: 4000)
 */
function showToast(message, type, title, duration) {
  type = type || 'info';
  duration = duration || 4000;
  
  // Ensure toast container exists
  let container = document.getElementById('toastContainer');
  if (!container) {
    container = document.createElement('div');
    container.id = 'toastContainer';
    document.body.appendChild(container);
  }
  
  // Icon mapping
  const icons = {
    success: '<i class="fa-solid fa-circle-check"></i>',
    error: '<i class="fa-solid fa-circle-xmark"></i>',
    warning: '<i class="fa-solid fa-triangle-exclamation"></i>',
    info: '<i class="fa-solid fa-circle-info"></i>'
  };
  
  // Title mapping
  const titles = {
    success: title || 'Éxito',
    error: title || 'Error',
    warning: title || 'Advertencia',
    info: title || 'Información'
  };
  
  // Create toast element
  const toast = document.createElement('div');
  toast.className = `custom-toast toast-${type}`;
  toast.innerHTML = `
    <div class="toast-icon">${icons[type]}</div>
    <div class="toast-content">
      <div class="toast-title">${titles[type]}</div>
      <div class="toast-message">${message}</div>
    </div>
    <button class="toast-close" aria-label="Cerrar">&times;</button>
  `;
  
  container.appendChild(toast);
  
  // Close button handler
  const closeBtn = toast.querySelector('.toast-close');
  closeBtn.addEventListener('click', function() {
    removeToast(toast);
  });
  
  // Auto-remove after duration
  if (duration > 0) {
    setTimeout(function() {
      removeToast(toast);
    }, duration);
  }
  
  return toast;
}

/**
 * Remueve un toast con animación.
 * @param {HTMLElement} toast - Elemento toast a remover
 */
function removeToast(toast) {
  toast.classList.add('toast-hiding');
  setTimeout(function() {
    if (toast.parentNode) {
      toast.parentNode.removeChild(toast);
    }
  }, 200);
}

// ── Confirmation Dialog ───────────────────────────────────────────────────────
/**
 * Escapa caracteres HTML para prevenir XSS.
 * @param {string} str - String a escapar
 * @returns {string} String escapado
 */
function escapeHtml(str) {
  const div = document.createElement('div');
  div.textContent = str;
  return div.innerHTML;
}

/**
 * Muestra un diálogo de confirmación estético en lugar de window.confirm().
 * @param {string} message - Mensaje de confirmación
 * @param {function} onConfirm - Callback si el usuario confirma
 * @param {function} [onCancel] - Callback opcional si el usuario cancela
 * @param {object} [options] - Opciones: { title, confirmText, cancelText, danger }
 */
function showConfirm(message, onConfirm, onCancel, options) {
  options = options || {};
  const title = escapeHtml(options.title || '¿Confirmar acción?');
  const confirmText = escapeHtml(options.confirmText || 'Confirmar');
  const cancelText = escapeHtml(options.cancelText || 'Cancelar');
  const danger = options.danger || false;
  
  // Allow HTML in message but escape by default if not explicitly marked as safe
  const messageHtml = message;
  
  // Create modal backdrop
  const backdrop = document.createElement('div');
  backdrop.className = 'modal-backdrop fade show';
  document.body.appendChild(backdrop);
  
  // Create modal
  const modal = document.createElement('div');
  modal.className = 'modal fade show confirm-modal';
  modal.style.display = 'block';
  modal.setAttribute('tabindex', '-1');
  modal.setAttribute('role', 'dialog');
  
  const modalDialog = document.createElement('div');
  modalDialog.className = 'modal-dialog modal-dialog-centered';
  
  const modalContent = document.createElement('div');
  modalContent.className = 'modal-content';
  
  const modalHeader = document.createElement('div');
  modalHeader.className = 'modal-header';
  const modalTitle = document.createElement('h5');
  modalTitle.className = 'modal-title';
  modalTitle.textContent = options.title || '¿Confirmar acción?';
  const closeBtn = document.createElement('button');
  closeBtn.type = 'button';
  closeBtn.className = 'btn-close';
  closeBtn.setAttribute('data-dismiss', 'modal');
  closeBtn.setAttribute('aria-label', 'Cerrar');
  modalHeader.appendChild(modalTitle);
  modalHeader.appendChild(closeBtn);
  
  const modalBody = document.createElement('div');
  modalBody.className = 'modal-body';
  // Use textContent to prevent XSS - if HTML is needed, it should be explicitly escaped
  modalBody.textContent = message;
  
  const modalFooter = document.createElement('div');
  modalFooter.className = 'modal-footer';
  const cancelBtn = document.createElement('button');
  cancelBtn.type = 'button';
  cancelBtn.className = 'btn btn-secondary';
  cancelBtn.setAttribute('data-action', 'cancel');
  cancelBtn.textContent = options.cancelText || 'Cancelar';
  const confirmBtn = document.createElement('button');
  confirmBtn.type = 'button';
  confirmBtn.className = danger ? 'btn btn-danger' : 'btn btn-primary';
  confirmBtn.setAttribute('data-action', 'confirm');
  confirmBtn.textContent = options.confirmText || 'Confirmar';
  modalFooter.appendChild(cancelBtn);
  modalFooter.appendChild(confirmBtn);
  
  modalContent.appendChild(modalHeader);
  modalContent.appendChild(modalBody);
  modalContent.appendChild(modalFooter);
  modalDialog.appendChild(modalContent);
  modal.appendChild(modalDialog);
  
  document.body.appendChild(modal);
  document.body.classList.add('modal-open');
  
  // Function to close and cleanup
  function closeModal() {
    modal.classList.remove('show');
    backdrop.classList.remove('show');
    setTimeout(function() {
      if (modal.parentNode) modal.parentNode.removeChild(modal);
      if (backdrop.parentNode) backdrop.parentNode.removeChild(backdrop);
      document.body.classList.remove('modal-open');
    }, 150);
  }
  
  // Handle buttons
  confirmBtn.addEventListener('click', function() {
    closeModal();
    if (onConfirm) onConfirm();
  });
  
  cancelBtn.addEventListener('click', function() {
    closeModal();
    if (onCancel) onCancel();
  });
  
  closeBtn.addEventListener('click', function() {
    closeModal();
    if (onCancel) onCancel();
  });
  
  // Close on backdrop click
  backdrop.addEventListener('click', function() {
    closeModal();
    if (onCancel) onCancel();
  });
  
  // Show animation
  setTimeout(function() {
    modal.classList.add('show');
  }, 10);
}

// Override window.alert and window.confirm to use our custom functions
(function() {
  window._originalAlert = window.alert;
  window._originalConfirm = window.confirm;
  
  window.alert = function(message) {
    showToast(message, 'info', 'Aviso', 5000);
  };
  
  // window.confirm is trickier - we can't make it async, so we keep the original
  // but provide showConfirm as a replacement that should be used instead
})();
