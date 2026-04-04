/* ============================================= */
/* PÁGINA DE HISTORIAL DE SOLICITUDES            */
/* Lista todas las solicitudes procesadas        */
/* con nombre, caso, proveedor, veredicto        */
/* ============================================= */
import { useState } from 'react';
import { useApp } from '../context/AppContext';
import ConfirmModal from '../components/ConfirmModal';

export default function HistoryPage({ onViewResult }) {
  /* Obtener el historial y funciones del contexto */
  const { history, deleteFromHistory, showToast } = useApp();
  /* Estado del modal de confirmación de eliminación */
  const [confirmModal, setConfirmModal] = useState({ open: false, entry: null });

  /* Abrir modal de confirmación */
  const handleDelete = (e, entry) => {
    e.stopPropagation();
    setConfirmModal({ open: true, entry });
  };

  /* Ejecutar eliminación tras confirmar */
  const handleConfirmDelete = async () => {
    const entry = confirmModal.entry;
    setConfirmModal({ open: false, entry: null });
    const success = await deleteFromHistory(entry.id);
    if (success) {
      showToast('Análisis eliminado del historial', 'info');
    } else {
      showToast('Error al eliminar el análisis', 'error');
    }
  };

  /* Si no hay solicitudes, mostrar estado vacío */
  if (history.length === 0) {
    return (
      <div>
        {/* Encabezado de la página */}
        <div className="page-header">
          <h2>Historial</h2>
          <p>Registro de todas las solicitudes procesadas</p>
        </div>
        {/* Estado vacío */}
        <div className="empty-state">
          <div className="empty-state-icon">📁</div>
          <h3>Sin solicitudes procesadas</h3>
          <p>Las solicitudes analizadas aparecerán aquí.</p>
        </div>
      </div>
    );
  }

  return (
    <div>
      {/* Encabezado de la página */}
      <div className="page-header">
        <h2>Historial</h2>
        <p>{history.length} solicitud(es) procesada(s)</p>
      </div>

      {/* Tabla de historial */}
      <div className="card" style={{ overflow: 'hidden' }}>
        <div className="history-table-wrapper">
          <table className="history-table">
            {/* Encabezados de columna */}
            <thead>
              <tr>
                <th>Solicitud</th>
                <th>Caso</th>
                <th>Proveedor</th>
                <th>Fecha / Hora</th>
                <th>Archivos</th>
                <th>Veredicto</th>
                <th>Acciones</th>
              </tr>
            </thead>
            {/* Filas del historial */}
            <tbody>
              {history.map((entry) => {
                /* Determinar la clase del pill según veredicto */
                const pillClass = entry.verdict === 'APROBADO' ? 'pill-success'
                  : entry.verdict === 'RECHAZADO' ? 'pill-error' : 'pill-warning';
                /* Formatear la fecha */
                const date = new Date(entry.timestamp).toLocaleString('es-PE', {
                  dateStyle: 'medium',
                  timeStyle: 'short',
                });
                return (
                  <tr key={entry.id} onClick={() => onViewResult(entry)}>
                    {/* Columna: Nombre de la solicitud */}
                    <td>
                      <span style={{ fontWeight: 600 }}>
                        {entry.requestName || '—'}
                      </span>
                    </td>
                    {/* Columna: Caso con ícono */}
                    <td>
                      <span style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                        <span style={{ fontSize: '18px' }}>{entry.caseIcon}</span>
                        <span style={{ fontSize: '13px' }}>{entry.caseName}</span>
                      </span>
                    </td>
                    {/* Columna: Proveedor (remitente del correo) */}
                    <td>
                      <span style={{ fontSize: '13px' }}>
                        {entry.emailData.from}
                      </span>
                    </td>
                    {/* Columna: Fecha y hora */}
                    <td>
                      <span style={{ fontSize: '13px', color: 'var(--color-text-secondary)' }}>
                        {date}
                      </span>
                    </td>
                    {/* Columna: Cantidad de archivos */}
                    <td>
                      <span>{entry.files.length}</span>
                    </td>
                    {/* Columna: Veredicto con pill de color */}
                    <td>
                      <span className={`pill ${pillClass}`}>
                        {entry.verdict}
                      </span>
                    </td>
                    {/* Columna: Acciones */}
                    <td>
                      <button
                        className="btn btn-ghost btn-sm"
                        style={{ color: 'var(--color-error)', padding: '4px 10px' }}
                        onClick={(e) => handleDelete(e, entry)}
                        title="Eliminar análisis"
                      >
                        Eliminar
                      </button>

                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>

      {/* Modal de confirmación de eliminación */}
      <ConfirmModal
        isOpen={confirmModal.open}
        title="Eliminar análisis"
        message={
          confirmModal.entry
            ? `¿Eliminar el análisis "${confirmModal.entry.requestName || confirmModal.entry.caseName}" del ${new Date(confirmModal.entry.timestamp).toLocaleDateString('es-PE')}? Esta acción no se puede deshacer.`
            : ''
        }
        confirmLabel="Eliminar"
        onConfirm={handleConfirmDelete}
        onCancel={() => setConfirmModal({ open: false, entry: null })}
      />
    </div>
  );
}
