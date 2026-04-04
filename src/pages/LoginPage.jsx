/* ============================================= */
/* PAGINA DE LOGIN                               */
/* Pantalla de autenticacion para iniciar sesion */
/* ============================================= */
import { useState } from 'react';
import { useApp } from '../context/AppContext';
import logoImg from '../assets/logo.png';

function SunIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" aria-hidden="true">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 3v2m0 14v2m9-9h-2M5 12H3m15.364 6.364-1.414-1.414M7.05 7.05 5.636 5.636m12.728 0-1.414 1.414M7.05 16.95l-1.414 1.414M12 8a4 4 0 1 0 0 8 4 4 0 0 0 0-8Z" />
    </svg>
  );
}

function MoonIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" aria-hidden="true">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 12.79A9 9 0 1 1 11.21 3c.4 0 .6.48.33.77A7 7 0 0 0 20.23 12c.29-.27.77-.07.77.33Z" />
    </svg>
  );
}

export default function LoginPage({ theme, onToggleTheme }) {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const { login, showToast } = useApp();
  const isDark = theme === 'dark';

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    if (!username.trim() || !password.trim()) {
      setError('Completa todos los campos');
      return;
    }
    setSubmitting(true);
    const result = await login(username.trim(), password);
    if (!result.success) {
      setError(result.error || 'Credenciales incorrectas');
    } else {
      showToast('Bienvenido de vuelta', 'success');
    }
    setSubmitting(false);
  };

  return (
    <div className="login-container">
      <div className="login-card-wrap">
        <button
          className="theme-toggle login-theme-toggle"
          onClick={onToggleTheme}
          title={isDark ? 'Cambiar a tema claro' : 'Cambiar a tema oscuro'}
          aria-label={isDark ? 'Cambiar a tema claro' : 'Cambiar a tema oscuro'}
        >
          {isDark ? <SunIcon /> : <MoonIcon />}
        </button>

        <div className="login-card">
          <div style={{ textAlign: 'center', marginBottom: '24px' }}>
            <img src={logoImg} alt="OIG Peru" style={{ maxWidth: '180px', height: 'auto' }} />
          </div>
          <form onSubmit={handleSubmit}>
            <div className="form-group">
              <label className="form-label">Usuario</label>
              <input
                type="text"
                className="form-input"
                placeholder="Ingresa tu usuario"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                autoFocus
                disabled={submitting}
              />
            </div>
            <div className="form-group">
              <label className="form-label">Contrasena</label>
              <input
                type="password"
                className="form-input"
                placeholder="Ingresa tu contrasena"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                disabled={submitting}
              />
            </div>
            {error && (
              <div style={{ color: 'var(--color-error)', fontSize: '13px', marginBottom: '16px' }}>
                {error}
              </div>
            )}
            <button type="submit" className="btn btn-primary btn-block btn-lg" disabled={submitting}>
              {submitting ? 'Procesando...' : 'Iniciar Sesion'}
            </button>
          </form>
        </div>
      </div>
    </div>
  );
}
