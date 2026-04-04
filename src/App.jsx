/* ============================================= */
/* COMPONENTE PRINCIPAL DE LA APLICACION         */
/* Maneja la navegacion entre modulos y el       */
/* layout general con sidebar                    */
/* ============================================= */
import { useState, useEffect } from 'react';
import { useApp } from './context/AppContext';
import Sidebar from './components/Sidebar';
import Toast from './components/Toast';
import LoginPage from './pages/LoginPage';
import NewRequestPage from './pages/NewRequestPage';
import AnalysisPage from './pages/AnalysisPage';
import ResultsPage from './pages/ResultsPage';
import HistoryPage from './pages/HistoryPage';
import CasesPage from './pages/CasesPage';
import ApiKeyPage from './pages/ApiKeyPage';
import AdminPage from './pages/AdminPage';
import PromptsPage from './pages/PromptsPage';

export default function App() {
  /* Obtener el usuario autenticado y el estado de API key del contexto */
  const { user, loading, apiKeyConfigured, showToast } = useApp();
  /* Tema activo de la aplicacion */
  const [theme, setTheme] = useState(() => localStorage.getItem('theme') || 'light');
  /* Pagina actual visible */
  const [currentPage, setCurrentPage] = useState('nueva-solicitud');
  /* Estado del sidebar en dispositivos moviles */
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  /* Archivos para el pipeline de analisis */
  const [analysisFiles, setAnalysisFiles] = useState(null);
  /* Nombre de la solicitud para el pipeline */
  const [analysisRequestName, setAnalysisRequestName] = useState('');
  /* ID del caso seleccionado para el pipeline */
  const [analysisCaseId, setAnalysisCaseId] = useState('');
  /* Resultado seleccionado para la vista de resultados */
  const [selectedResult, setSelectedResult] = useState(null);

  /* Redirigir a configuracion de API key si no esta configurada */
  useEffect(() => {
    if (user && !apiKeyConfigured) {
      setCurrentPage('api-key');
    }
  }, [user, apiKeyConfigured]);

  /* Persistir y aplicar el tema actual en el documento */
  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme);
    localStorage.setItem('theme', theme);
  }, [theme]);

  const toggleTheme = () => {
    setTheme((prev) => (prev === 'dark' ? 'light' : 'dark'));
  };

  /* Mostrar pantalla de carga mientras se verifica la sesion */
  if (loading) {
    return (
      <div className="login-container">
        <div style={{ textAlign: 'center' }}>
          <div className="spinner" style={{ margin: '0 auto 16px' }} />
          <p style={{ color: 'var(--color-text-secondary)' }}>Cargando...</p>
        </div>
      </div>
    );
  }

  /* Si no hay usuario autenticado, mostrar la pantalla de login */
  if (!user) {
    return (
      <>
        <LoginPage theme={theme} onToggleTheme={toggleTheme} />
        <Toast />
      </>
    );
  }

  /* Iniciar el pipeline de analisis con los archivos cargados */
  const handleStartAnalysis = (files, requestName = '', caseId = '') => {
    /* Verificar que la API key este configurada */
    if (!apiKeyConfigured) {
      showToast('Configura tu API Key antes de analizar', 'error');
      setCurrentPage('api-key');
      return;
    }
    /* Guardar los archivos, nombre, caso y navegar al pipeline */
    setAnalysisFiles(files);
    setAnalysisRequestName(requestName);
    setAnalysisCaseId(caseId);
    setCurrentPage('analisis');
  };

  /* Manejar la finalizacion del analisis */
  const handleAnalysisComplete = (result) => {
    /* Guardar el resultado y navegar a la vista de resultados */
    setSelectedResult(result);
    setAnalysisFiles(null);
    setCurrentPage('resultados');
  };

  /* Manejar la seleccion de un resultado desde el historial */
  const handleViewResult = (result) => {
    setSelectedResult(result);
    setCurrentPage('resultados');
  };

  /* Renderizar la pagina actual segun la navegacion */
  const renderPage = () => {
    switch (currentPage) {
      /* Pagina principal: carga de archivos */
      case 'nueva-solicitud':
        return <NewRequestPage onStartAnalysis={handleStartAnalysis} />;
      /* Pipeline de analisis en progreso */
      case 'analisis':
        return analysisFiles ? (
          <AnalysisPage files={analysisFiles} requestName={analysisRequestName} selectedCaseId={analysisCaseId} onComplete={handleAnalysisComplete} />
        ) : (
          <NewRequestPage onStartAnalysis={handleStartAnalysis} />
        );
      /* Vista de resultados de un analisis */
      case 'resultados':
        return <ResultsPage result={selectedResult} />;
      /* Historial de solicitudes procesadas */
      case 'historial':
        return <HistoryPage onViewResult={handleViewResult} />;
      /* Gestion de casos de validacion */
      case 'casos':
        return <CasesPage />;
      /* Configuracion de API key */
      case 'api-key':
        return <ApiKeyPage />;
      /* Administracion de usuarios (solo admin) */
      case 'admin-users':
        return <AdminPage />;
      /* Editor de prompts de IA */
      case 'prompts':
        return <PromptsPage />;
      /* Pagina por defecto */
      default:
        return <NewRequestPage onStartAnalysis={handleStartAnalysis} />;
    }
  };

  return (
    <div className="app-layout">
      {/* Boton hamburguesa para abrir sidebar en movil */}
      <button
        className="mobile-menu-btn"
        onClick={() => setMobileMenuOpen(true)}
      >
        ?
      </button>
      {/* Sidebar de navegacion */}
      <Sidebar
        currentPage={currentPage}
        onNavigate={setCurrentPage}
        mobileOpen={mobileMenuOpen}
        onCloseMobile={() => setMobileMenuOpen(false)}
        theme={theme}
        onToggleTheme={toggleTheme}
      />
      {/* Contenido principal */}
      <main className="main-content">
        {renderPage()}
      </main>
      {/* Sistema de notificaciones toast */}
      <Toast />
    </div>
  );
}
