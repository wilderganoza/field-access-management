/* ============================================= */
/* PUNTO DE ENTRADA DE LA APLICACION             */
/* Inicializa React y envuelve la app con el     */
/* proveedor de contexto global                  */
/* ============================================= */
import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { AppProvider } from './context/AppContext';
import App from './App';
import './styles.css';

const persistedTheme = localStorage.getItem('theme') || 'light';
document.documentElement.setAttribute('data-theme', persistedTheme);

/* Renderizar la aplicacion en el elemento raiz */
createRoot(document.getElementById('root')).render(
  <StrictMode>
    {/* Proveedor de contexto global que envuelve toda la app */}
    <AppProvider>
      <App />
    </AppProvider>
  </StrictMode>
);
