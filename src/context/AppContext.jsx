/* ============================================= */
/* CONTEXTO GLOBAL DE LA APLICACIÓN              */
/* Maneja: autenticación, API key, casos,        */
/* historial y notificaciones toast               */
/* Persistencia: PostgreSQL vía API REST         */
/* ============================================= */
import { createContext, useContext, useState, useEffect, useCallback } from 'react';
import {
  apiLogin, apiLogout, apiGetMe,
  apiGetCases, apiCreateCase, apiUpdateCase, apiDeleteCase,
  apiGetHistory, apiSaveHistory, apiDeleteHistory,
  apiGetApiKeyStatus, apiSaveApiKey, apiDeleteApiKey, apiGetFullApiKey,
  apiGetUsers, apiCreateUser, apiUpdateUser, apiDeleteUser,
  apiGetPromptsForCase,
} from '../utils/api';

/* Crear el contexto */
const AppContext = createContext(null);

/* ============================================= */
/* PROVEEDOR DEL CONTEXTO                        */
/* ============================================= */
export function AppProvider({ children }) {
  /* --- Estado de autenticación --- */
  const [user, setUser] = useState(null);
  /* --- Indicador de carga inicial (verificar sesión existente) --- */
  const [loading, setLoading] = useState(true);
  /* --- Estado de la API Key (solo hint: últimos 4 caracteres) --- */
  const [apiKeyConfigured, setApiKeyConfigured] = useState(false);
  /* --- Hint de la API Key (últimos 4 caracteres) --- */
  const [apiKeyHint, setApiKeyHint] = useState('');
  /* --- Estado de los casos --- */
  const [cases, setCases] = useState([]);
  /* --- Estado del historial de solicitudes --- */
  const [history, setHistory] = useState([]);
  /* --- Caché de prompts por caso (caseId → {read_documents, validate_and_summarize}) --- */
  const [promptsCache, setPromptsCache] = useState({});
  /* --- Estado de las notificaciones toast --- */
  const [toasts, setToasts] = useState([]);

  /* Verificar sesión existente al cargar la app */
  useEffect(() => {
    const token = localStorage.getItem('oig_token');
    if (token) {
      /* Intentar obtener el perfil del usuario con el token guardado */
      apiGetMe()
        .then(data => {
          setUser(data.user);
        })
        .catch(() => {
          /* Token inválido, limpiar localStorage */
          localStorage.removeItem('oig_token');
        })
        .finally(() => setLoading(false));
    } else {
      setLoading(false);
    }
  }, []);

  /* Cargar datos del backend cuando el usuario se autentica */
  useEffect(() => {
    if (user) {
      /* Cargar casos, historial y estado de API key en paralelo */
      loadCases();
      loadHistory();
      loadApiKeyStatus();
    }
  }, [user]);

  /* Cargar los casos desde el backend */
  const loadCases = useCallback(async () => {
    try {
      const data = await apiGetCases();
      setCases(data.cases);
    } catch (err) {
      console.error('Error al cargar casos:', err);
    }
  }, []);

  /* Cargar el historial desde el backend */
  const loadHistory = useCallback(async () => {
    try {
      const data = await apiGetHistory();
      setHistory(data.history);
    } catch (err) {
      console.error('Error al cargar historial:', err);
    }
  }, []);

  /* Obtener los prompts del caso seleccionado (con caché) */
  const getPromptsForCase = useCallback(async (caseId) => {
    /* Devolver caché si ya fue cargado */
    if (promptsCache[caseId]) return promptsCache[caseId];
    try {
      const data = await apiGetPromptsForCase(caseId);
      /* Convertir array a mapa por id para acceso rápido */
      const map = {};
      for (const p of data.prompts) {
        map[p.id] = p.content;
      }
      /* Actualizar caché */
      setPromptsCache(prev => ({ ...prev, [caseId]: map }));
      return map;
    } catch (err) {
      console.error('Error al cargar prompts del caso:', err);
      return {}; /* Devolver vacío — openaiService usará defaults hardcodeados */
    }
  }, [promptsCache]);

  /* Cargar el estado de la API key desde el backend */
  const loadApiKeyStatus = useCallback(async () => {
    try {
      const data = await apiGetApiKeyStatus();
      setApiKeyConfigured(data.configured);
      setApiKeyHint(data.hint);
    } catch (err) {
      console.error('Error al cargar estado de API key:', err);
    }
  }, []);

  /* --- Función de login --- */
  const login = useCallback(async (username, password) => {
    try {
      const data = await apiLogin(username, password);
      setUser(data.user);
      return { success: true };
    } catch (err) {
      return { success: false, error: err.message };
    }
  }, []);

  /* --- Función de logout --- */
  const logout = useCallback(() => {
    apiLogout();
    setUser(null);
    setCases([]);
    setHistory([]);
    setApiKeyConfigured(false);
    setApiKeyHint('');
  }, []);

  /* --- Función para guardar API key --- */
  const setApiKey = useCallback(async (key) => {
    try {
      const data = await apiSaveApiKey(key);
      setApiKeyConfigured(true);
      setApiKeyHint(data.hint);
      return true;
    } catch (err) {
      console.error('Error al guardar API key:', err);
      return false;
    }
  }, []);

  /* --- Función para eliminar API key --- */
  const removeApiKey = useCallback(async () => {
    try {
      await apiDeleteApiKey();
      setApiKeyConfigured(false);
      setApiKeyHint('');
      return true;
    } catch (err) {
      console.error('Error al eliminar API key:', err);
      return false;
    }
  }, []);

  /* --- Función para obtener la API key completa (para el pipeline) --- */
  const getFullApiKey = useCallback(async () => {
    try {
      const data = await apiGetFullApiKey();
      return data.apiKey;
    } catch (err) {
      console.error('Error al obtener API key:', err);
      return null;
    }
  }, []);

  /* --- Función para agregar un caso --- */
  const addCase = useCallback(async (newCase) => {
    try {
      const data = await apiCreateCase(newCase);
      /* Recargar casos desde el backend */
      await loadCases();
      return data.case;
    } catch (err) {
      console.error('Error al crear caso:', err);
      return null;
    }
  }, [loadCases]);

  /* --- Función para actualizar un caso --- */
  const updateCase = useCallback(async (id, updates) => {
    try {
      await apiUpdateCase(id, updates);
      /* Recargar casos desde el backend */
      await loadCases();
      return true;
    } catch (err) {
      console.error('Error al actualizar caso:', err);
      return false;
    }
  }, [loadCases]);

  /* --- Función para eliminar un caso --- */
  const deleteCase = useCallback(async (id) => {
    try {
      await apiDeleteCase(id);
      /* Recargar casos desde el backend */
      await loadCases();
      return true;
    } catch (err) {
      console.error('Error al eliminar caso:', err);
      return false;
    }
  }, [loadCases]);

  /* Invalidar la caché de prompts de un caso (tras guardar o resetear) */
  const invalidatePromptsCache = useCallback((caseId) => {
    setPromptsCache(prev => {
      const next = { ...prev };
      delete next[caseId];
      return next;
    });
  }, []);

  /* --- Función para agregar entrada al historial --- */
  const addToHistory = useCallback(async (entry) => {
    try {
      console.log('[HISTORY] Guardando análisis, checklistResults:', JSON.stringify(entry.checklistResults?.slice(0, 1)));
      await apiSaveHistory(entry);
      /* Recargar historial desde el backend */
      await loadHistory();
    } catch (err) {
      console.error('[HISTORY] Error al guardar en historial:', err);
      throw err; /* Re-lanzar para que AnalysisPage pueda manejarlo */
    }
  }, [loadHistory]);

  /* --- Función para eliminar una entrada del historial --- */
  const deleteFromHistory = useCallback(async (id) => {
    try {
      await apiDeleteHistory(id);
      /* Recargar historial desde el backend */
      await loadHistory();
      return true;
    } catch (err) {
      console.error('Error al eliminar del historial:', err);
      return false;
    }
  }, [loadHistory]);

  /* --- Funciones de administración de usuarios --- */
  const getUsers = useCallback(async () => {
    try {
      const data = await apiGetUsers();
      return data.users;
    } catch (err) {
      console.error('Error al obtener usuarios:', err);
      return [];
    }
  }, []);

  const createUser = useCallback(async (userData) => {
    try {
      const data = await apiCreateUser(userData);
      return { success: true, user: data.user };
    } catch (err) {
      return { success: false, error: err.message };
    }
  }, []);

  const updateUser = useCallback(async (id, userData) => {
    try {
      const data = await apiUpdateUser(id, userData);
      return { success: true, user: data.user };
    } catch (err) {
      return { success: false, error: err.message };
    }
  }, []);

  const deleteUser = useCallback(async (id) => {
    try {
      await apiDeleteUser(id);
      return { success: true };
    } catch (err) {
      return { success: false, error: err.message };
    }
  }, []);

  /* --- Función para mostrar notificación toast --- */
  const showToast = useCallback((message, type = 'info') => {
    /* Crear toast con ID único */
    const id = Date.now() + Math.random();
    setToasts(prev => [...prev, { id, message, type }]);
    /* Auto-eliminar el toast después de 4 segundos */
    setTimeout(() => {
      setToasts(prev => prev.filter(t => t.id !== id));
    }, 4000);
  }, []);

  /* --- Función para eliminar un toast manualmente --- */
  const removeToast = useCallback((id) => {
    setToasts(prev => prev.filter(t => t.id !== id));
  }, []);

  /* Valor del contexto con todos los estados y funciones */
  const value = {
    user,
    loading,
    login,
    logout,
    apiKeyConfigured,
    apiKeyHint,
    setApiKey,
    removeApiKey,
    getFullApiKey,
    cases,
    addCase,
    updateCase,
    deleteCase,
    history,
    addToHistory,
    deleteFromHistory,
    getPromptsForCase,
    invalidatePromptsCache,
    getUsers,
    createUser,
    updateUser,
    deleteUser,
    toasts,
    showToast,
    removeToast,
  };

  return <AppContext.Provider value={value}>{children}</AppContext.Provider>;
}

/* Hook personalizado para acceder al contexto */
export function useApp() {
  const ctx = useContext(AppContext);
  /* Lanzar error si se usa fuera del proveedor */
  if (!ctx) throw new Error('useApp debe usarse dentro de AppProvider');
  return ctx;
}
