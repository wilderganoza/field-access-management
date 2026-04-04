/* ============================================= */
/* PÁGINA DE CONFIGURACIÓN DE API KEY            */
/* Permite al usuario ingresar y gestionar       */
/* su clave de API de OpenAI                     */
/* ============================================= */
import { useState } from 'react';
import { useApp } from '../context/AppContext';

export default function ApiKeyPage() {
  /* Obtener el estado de la API key y las funciones del contexto */
  const { apiKeyConfigured, apiKeyHint, setApiKey, removeApiKey, showToast } = useApp();
  /* Estado local para el campo de entrada */
  const [inputKey, setInputKey] = useState('');
  /* Estado de carga */
  const [saving, setSaving] = useState(false);

  /* Manejar el guardado de la API key */
  const handleSave = async () => {
    /* Validar que el campo no esté vacío */
    if (!inputKey.trim()) {
      showToast('Ingresa una API key válida', 'warning');
      return;
    }
    /* Activar indicador de carga */
    setSaving(true);
    /* Guardar la API key en el backend */
    const success = await setApiKey(inputKey.trim());
    if (success) {
      /* Limpiar el campo de entrada */
      setInputKey('');
      /* Mostrar confirmación al usuario */
      showToast('API Key guardada correctamente', 'success');
    } else {
      showToast('Error al guardar la API Key', 'error');
    }
    /* Desactivar indicador de carga */
    setSaving(false);
  };

  /* Manejar la eliminación de la API key */
  const handleRemove = async () => {
    /* Eliminar la API key del backend */
    const success = await removeApiKey();
    if (success) {
      /* Notificar al usuario */
      showToast('API Key eliminada', 'info');
    } else {
      showToast('Error al eliminar la API Key', 'error');
    }
  };

  /* Construir la cadena enmascarada de la key */
  const maskedKey = apiKeyConfigured ? `••••••••${apiKeyHint}` : '';

  return (
    <div>
      {/* Encabezado de la página */}
      <div className="page-header">
        <h2>Configuración de API Key</h2>
        <p>Configura tu clave de API de OpenAI para habilitar el análisis con IA</p>
      </div>

      {/* Card principal de configuración */}
      <div className="card" style={{ maxWidth: '560px' }}>
        <div className="card-body">
          {/* Indicador del estado actual de la API key */}
          <div className={`api-status ${apiKeyConfigured ? 'configured' : 'not-configured'}`}>
            {apiKeyConfigured ? (
              /* Estado: API key configurada */
              <>
                <span>✓</span>
                <span>API Key configurada: <span className="api-key-hint">{maskedKey}</span></span>
              </>
            ) : (
              /* Estado: API key no configurada */
              <>
                <span>⚠</span>
                <span>No hay API Key configurada</span>
              </>
            )}
          </div>

          {/* Campo para ingresar nueva API key */}
          <div className="form-group">
            <label className="form-label">
              {apiKeyConfigured ? 'Actualizar API Key' : 'Ingresar API Key'}
            </label>
            <input
              type="password"
              className="form-input"
              placeholder="sk-..."
              value={inputKey}
              onChange={(e) => setInputKey(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleSave()}
              disabled={saving}
            />
          </div>

          {/* Botones de acción */}
          <div style={{ display: 'flex', gap: '12px' }}>
            {/* Botón para guardar la key */}
            <button className="btn btn-primary" onClick={handleSave} disabled={saving}>
              {saving ? 'Guardando...' : 'Guardar API Key'}
            </button>
            {/* Botón para eliminar la key (solo si existe una) */}
            {apiKeyConfigured && (
              <button className="btn btn-danger" onClick={handleRemove} disabled={saving}>
                Eliminar
              </button>
            )}
          </div>

          {/* Nota informativa sobre seguridad */}
          <div style={{ marginTop: '24px', fontSize: '13px', color: 'var(--color-text-secondary)', lineHeight: '1.6' }}>
            <strong>Nota:</strong> La API Key se almacena de forma segura en el servidor.
            Necesitas una cuenta de OpenAI con acceso al modelo GPT-4.1 para usar el análisis multimodal (1M tokens de contexto).
          </div>
        </div>
      </div>
    </div>
  );
}
