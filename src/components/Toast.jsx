/* ============================================= */
/* COMPONENTE DE NOTIFICACIONES TOAST            */
/* Muestra notificaciones temporales apiladas    */
/* en la esquina superior derecha                */
/* ============================================= */
import { useApp } from '../context/AppContext';

/* Mapa de íconos según el tipo de toast */
const TOAST_ICONS = {
  success: '✓',
  error: '✕',
  warning: '⚠',
  info: 'ℹ',
};

export default function Toast() {
  /* Obtener los toasts activos y la función para eliminarlos */
  const { toasts, removeToast } = useApp();

  /* Si no hay toasts, no renderizar nada */
  if (toasts.length === 0) return null;

  return (
    /* Contenedor fijo en la esquina superior derecha */
    <div className="toast-container">
      {/* Renderizar cada toast activo */}
      {toasts.map(toast => (
        <div
          key={toast.id}
          className={`toast toast-${toast.type}`}
          onClick={() => removeToast(toast.id)}
        >
          {/* Ícono del tipo de toast */}
          <span>{TOAST_ICONS[toast.type]}</span>
          {/* Mensaje del toast */}
          <span>{toast.message}</span>
        </div>
      ))}
    </div>
  );
}
