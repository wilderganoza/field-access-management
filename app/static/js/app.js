/* Comportamiento global de la aplicación: tema, sidebar y toasts.
   Todo lo demás lo resuelve HTMX desde los atributos del HTML. */

(function () {
  "use strict";

  // Alterna entre tema claro y oscuro, y lo persiste
  function setupThemeToggle() {
    var btn = document.getElementById("theme-toggle-btn");
    if (!btn) return;

    btn.addEventListener("click", function () {
      var current = document.documentElement.getAttribute("data-theme") || "dark";
      var next = current === "dark" ? "light" : "dark";
      document.documentElement.setAttribute("data-theme", next);
      localStorage.setItem("theme", next);
    });
  }

  // Muestra u oculta el sidebar y recuerda la preferencia
  function setupSidebarToggle() {
    var btn = document.getElementById("sidebar-toggle-btn");
    if (!btn) return;

    // Restauramos el estado guardado antes de enganchar el click
    var pref = document.documentElement.getAttribute("data-sidebar-pref");
    document.body.setAttribute("data-sidebar", pref === "closed" ? "closed" : "open");

    btn.addEventListener("click", function () {
      var current = document.body.getAttribute("data-sidebar");
      var next = current === "open" ? "closed" : "open";
      document.body.setAttribute("data-sidebar", next);
      localStorage.setItem("sidebarOpen", String(next === "open"));
    });
  }

  // Muestra un mensaje flotante. El servidor lo dispara con la cabecera
  // HX-Trigger: {"toast": {"message": "...", "level": "success"}}
  function showToast(message, level) {
    var container = document.getElementById("toast-container");
    if (!container) return;

    var toast = document.createElement("div");
    toast.className = "status-message " + (level || "info");
    toast.setAttribute("role", "status");
    toast.textContent = message;
    container.appendChild(toast);

    setTimeout(function () {
      toast.remove();
    }, level === "error" ? 8000 : 4000);
  }

  // HTMX no intercambia por defecto respuestas 4xx/5xx, aunque el servidor
  // haya devuelto un fragmento HTML con una explicación útil. Permitimos el
  // intercambio para que el error aparezca en el destino que corresponde.
  document.body.addEventListener("htmx:beforeSwap", function (event) {
    var xhr = event.detail.xhr;
    if (!xhr || xhr.status < 400 || !xhr.responseText.trim()) return;
    event.detail.shouldSwap = true;
  });

  function mensajeDeRespuesta(xhr) {
    if (!xhr || !xhr.responseText) return "";

    var documento = new DOMParser().parseFromString(xhr.responseText, "text/html");
    var mensaje = documento.querySelector("[role=alert], .status-message.error");
    return mensaje ? mensaje.textContent.trim().replace(/\s+/g, " ") : "";
  }

  // El aviso flotante garantiza que el error se vea incluso cuando el destino
  // del formulario está debajo de una lista larga o fuera del área visible.
  document.body.addEventListener("htmx:responseError", function (event) {
    var mensaje = mensajeDeRespuesta(event.detail.xhr) ||
      "No se pudo completar la operación. Inténtalo nuevamente.";
    showToast(mensaje, "error");
  });

  document.body.addEventListener("htmx:sendError", function () {
    showToast("No se pudo conectar con el servidor. Revisa tu conexión e inténtalo nuevamente.", "error");
  });

  document.body.addEventListener("htmx:timeout", function () {
    showToast("La operación tardó demasiado y fue interrumpida. Inténtalo nuevamente.", "error");
  });

  // Modales propios de la aplicación. No dependen de <dialog>, alert() ni
  // confirm(), de modo que conservan el mismo diseño en todos los navegadores.
  var focoPorModal = new WeakMap();
  var confirmacionPendiente = null;

  function elementosEnfocables(modal) {
    return Array.prototype.filter.call(
      modal.querySelectorAll(
        'a[href], button:not([disabled]), input:not([disabled]), ' +
        'select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])'
      ),
      function (elemento) { return elemento.offsetParent !== null; }
    );
  }

  function abrirModal(modal) {
    if (!modal) return;

    focoPorModal.set(modal, document.activeElement);
    modal.hidden = false;
    document.body.classList.add("modal-open");

    // Esperamos a que la capa sea visible antes de enfocar su primer control.
    requestAnimationFrame(function () {
      var preferido = modal.querySelector("[autofocus]") ||
        modal.querySelector("input:not([type=checkbox]), select, textarea") ||
        modal.querySelector("button");
      if (preferido) preferido.focus();
    });
  }

  function cerrarModal(modal, limpiar) {
    if (!modal) return;

    if (limpiar) {
      var formulario = modal.querySelector("form");
      if (formulario) formulario.reset();
    }

    modal.hidden = true;

    if (modal.id === "confirm-modal") {
      confirmacionPendiente = null;
    }

    if (!document.querySelector(".app-modal:not([hidden])")) {
      document.body.classList.remove("modal-open");
    }

    var focoAnterior = focoPorModal.get(modal);
    if (focoAnterior && focoAnterior.isConnected) focoAnterior.focus();
    focoPorModal.delete(modal);
  }

  // Las pantallas pueden abrir o cerrar componentes propios sin duplicar la
  // gestión de foco, teclado y bloqueo de scroll.
  window.appModal = {
    open: abrirModal,
    close: cerrarModal
  };

  document.addEventListener("click", function (event) {
    var abrir = event.target.closest("[data-modal-open]");
    if (abrir) {
      event.preventDefault();
      abrirModal(document.getElementById(abrir.getAttribute("data-modal-open")));
      return;
    }

    if (event.target.id === "confirm-modal-accept") {
      var pendiente = confirmacionPendiente;
      cerrarModal(document.getElementById("confirm-modal"), false);
      if (pendiente) pendiente.issueRequest(true);
      return;
    }

    var cerrar = event.target.closest("[data-modal-close]");
    if (cerrar) {
      cerrarModal(cerrar.closest(".app-modal"), true);
      return;
    }

    // Solo el fondo cierra; los clics dentro de la tarjeta no se propagan aquí.
    if (event.target.matches(".app-modal[data-modal-overlay]")) {
      cerrarModal(event.target, true);
    }
  });

  document.addEventListener("keydown", function (event) {
    var abiertos = document.querySelectorAll(".app-modal:not([hidden])");
    var modal = abiertos.length ? abiertos[abiertos.length - 1] : null;
    if (!modal) return;

    if (event.key === "Escape") {
      event.preventDefault();
      cerrarModal(modal, true);
      return;
    }

    // El foco no puede escapar hacia controles tapados por el modal.
    if (event.key === "Tab") {
      var enfocables = elementosEnfocables(modal);
      if (!enfocables.length) return;

      var primero = enfocables[0];
      var ultimo = enfocables[enfocables.length - 1];

      if (event.shiftKey && document.activeElement === primero) {
        event.preventDefault();
        ultimo.focus();
      } else if (!event.shiftKey && document.activeElement === ultimo) {
        event.preventDefault();
        primero.focus();
      }
    }
  });

  // Sustituimos el confirm() nativo que HTMX usaría para hx-confirm.
  document.body.addEventListener("htmx:confirm", function (event) {
    var pregunta = event.detail.question;
    if (!pregunta) return;

    event.preventDefault();
    confirmacionPendiente = event.detail;

    var modal = document.getElementById("confirm-modal");
    var mensaje = document.getElementById("confirm-modal-message");
    if (mensaje) mensaje.textContent = pregunta;
    abrirModal(modal);
  });

  // Los formularios modales se cierran solo cuando el servidor aceptó el cambio.
  document.body.addEventListener("htmx:afterRequest", function (event) {
    if (!event.detail.successful || !event.target.matches(".modal-form")) return;
    cerrarModal(event.target.closest(".app-modal"), true);
  });

  // HTMX emite este evento cuando el servidor manda HX-Trigger con clave "toast"
  document.body.addEventListener("toast", function (event) {
    var detail = event.detail || {};
    showToast(detail.message || "", detail.level);
  });

  // Exponemos showToast para las páginas que lo necesiten desde inline scripts
  window.showToast = showToast;

  setupThemeToggle();
  setupSidebarToggle();
})();
