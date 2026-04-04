/* ============================================= */
/* COMPONENTE SIDEBAR DE NAVEGACION              */
/* Menu lateral fijo con secciones principales   */
/* y de configuracion                            */
/* ============================================= */
import { useApp } from '../context/AppContext';
import logo from '../assets/logo.png';

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

function PowerIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" aria-hidden="true">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 3v10m5.657-7.071A8 8 0 1 1 6.343 5.929" />
    </svg>
  );
}

function FileIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" aria-hidden="true">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 3h7l5 5v13H7a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2Z" />
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M14 3v5h5" />
    </svg>
  );
}

function FolderIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" aria-hidden="true">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V7Z" />
    </svg>
  );
}

function SettingsIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" aria-hidden="true">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10.325 4.317a1 1 0 0 1 1.35-.936l.14.063 1.002.47a1 1 0 0 0 .847 0l1.002-.47a1 1 0 0 1 1.414.873l.07 1.105a1 1 0 0 0 .54.813l.957.53a1 1 0 0 1 .256 1.55l-.732.826a1 1 0 0 0-.242.813l.2 1.097a1 1 0 0 1-1.123 1.163l-1.104-.157a1 1 0 0 0-.798.268l-.8.761a1 1 0 0 1-1.553-.207l-.56-.94a1 1 0 0 0-.828-.511l-1.106-.032a1 1 0 0 1-.912-1.39l.406-1.03a1 1 0 0 0-.073-.84l-.563-.938a1 1 0 0 1 .182-1.556l.856-.699a1 1 0 0 0 .35-.767l.04-1.105Z" />
      <circle cx="12" cy="12" r="3" strokeWidth={2} />
    </svg>
  );
}

function KeyIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" aria-hidden="true">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 7a4 4 0 1 0 0 8 4 4 0 0 0 0-8Zm0 0 6-2v4l-2 1v2h-2v-2h-2" />
    </svg>
  );
}

function RobotIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" aria-hidden="true">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 3v3m-6 4h12a2 2 0 0 1 2 2v5a3 3 0 0 1-3 3H7a3 3 0 0 1-3-3v-5a2 2 0 0 1 2-2Z" />
      <circle cx="9" cy="14" r="1" />
      <circle cx="15" cy="14" r="1" />
    </svg>
  );
}

function UsersIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" aria-hidden="true">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M16 21v-1a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v1M9 12a4 4 0 1 0 0-8 4 4 0 0 0 0 8Zm13 9v-1a4 4 0 0 0-3-3.87M16 3.13a4 4 0 0 1 0 7.75" />
    </svg>
  );
}

export default function Sidebar({ currentPage, onNavigate, mobileOpen, onCloseMobile, theme, onToggleTheme }) {
  const { user, logout, history } = useApp();

  const handleNav = (page) => {
    onNavigate(page);
    onCloseMobile();
  };

  const initials = user?.username?.substring(0, 2).toUpperCase() || 'U';
  const isDark = theme === 'dark';

  return (
    <>
      <div className={`sidebar-overlay ${mobileOpen ? 'visible' : ''}`} onClick={onCloseMobile} />
      <aside className={`sidebar ${mobileOpen ? 'open' : ''}`}>
        <div className="sidebar-brand">
          <div className="sidebar-logo-wrap">
            <img className="sidebar-logo" src={logo} alt="OIG Peru - Control de Permisos" />
          </div>
        </div>

        <div className="sidebar-section">
          <div className="sidebar-section-label">Principal</div>
          <button className={`sidebar-item ${currentPage === 'nueva-solicitud' ? 'active' : ''}`} onClick={() => handleNav('nueva-solicitud')}>
            <span className="sidebar-item-icon"><FileIcon /></span>
            <span>Nueva Solicitud</span>
          </button>
          <button className={`sidebar-item ${currentPage === 'historial' ? 'active' : ''}`} onClick={() => handleNav('historial')}>
            <span className="sidebar-item-icon"><FolderIcon /></span>
            <span>Historial</span>
            {history.length > 0 && <span className="sidebar-badge">{history.length}</span>}
          </button>
        </div>

        <div className="sidebar-section">
          <div className="sidebar-section-label">Configuracion</div>
          <button className={`sidebar-item ${currentPage === 'casos' ? 'active' : ''}`} onClick={() => handleNav('casos')}>
            <span className="sidebar-item-icon"><SettingsIcon /></span>
            <span>Casos</span>
          </button>
          <button className={`sidebar-item ${currentPage === 'api-key' ? 'active' : ''}`} onClick={() => handleNav('api-key')}>
            <span className="sidebar-item-icon"><KeyIcon /></span>
            <span>API Key</span>
          </button>
          <button className={`sidebar-item ${currentPage === 'prompts' ? 'active' : ''}`} onClick={() => handleNav('prompts')}>
            <span className="sidebar-item-icon"><RobotIcon /></span>
            <span>Prompts IA</span>
          </button>
        </div>

        {user?.role === 'admin' && (
          <div className="sidebar-section">
            <div className="sidebar-section-label">Administracion</div>
            <button className={`sidebar-item ${currentPage === 'admin-users' ? 'active' : ''}`} onClick={() => handleNav('admin-users')}>
              <span className="sidebar-item-icon"><UsersIcon /></span>
              <span>Usuarios</span>
            </button>
          </div>
        )}

        <div className="sidebar-user">
          <div className="sidebar-user-avatar">{initials}</div>
          <div className="sidebar-user-meta">
            <div className="sidebar-user-name">{user?.username}</div>
            <div className="sidebar-user-role">{user?.role || 'Operador'}</div>
          </div>
          <div className="sidebar-user-actions">
            <button
              className="theme-toggle"
              onClick={onToggleTheme}
              title={isDark ? 'Cambiar a tema claro' : 'Cambiar a tema oscuro'}
              aria-label={isDark ? 'Cambiar a tema claro' : 'Cambiar a tema oscuro'}
            >
              {isDark ? <SunIcon /> : <MoonIcon />}
            </button>
            <button className="sidebar-logout" onClick={logout} title="Cerrar sesion" aria-label="Cerrar sesion">
              <PowerIcon />
            </button>
          </div>
        </div>
      </aside>
    </>
  );
}
