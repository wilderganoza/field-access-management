/* ============================================= */
/* CLIENTE HTTP PARA COMUNICACIÓN CON EL BACKEND */
/* Wrapper sobre fetch con manejo de tokens JWT  */
/* ============================================= */

/* URL base del backend */
/* En producción (Render) usa rutas relativas /api, en desarrollo apunta a localhost:3001 */
const API_BASE = import.meta.env.VITE_API_URL || (import.meta.env.DEV ? 'http://localhost:3001/api' : '/api');

/* Obtener el token JWT almacenado en localStorage */
function getToken() {
  return localStorage.getItem('oig_token') || '';
}

/* Realizar una petición autenticada al backend */
async function request(endpoint, options = {}) {
  /* Construir los headers con el token de autorización */
  const headers = {
    'Content-Type': 'application/json',
    ...options.headers,
  };
  /* Agregar el token JWT si existe */
  const token = getToken();
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }
  /* Realizar la petición fetch */
  const response = await fetch(`${API_BASE}${endpoint}`, {
    ...options,
    headers,
  });
  /* Parsear la respuesta como JSON */
  const data = await response.json();
  /* Si la respuesta no es exitosa, lanzar error */
  if (!response.ok) {
    throw new Error(data.error || `Error ${response.status}`);
  }
  return data;
}

/* ============================================= */
/* FUNCIONES DE AUTENTICACIÓN                    */
/* ============================================= */

/* Iniciar sesión */
export async function apiLogin(username, password) {
  const data = await request('/auth/login', {
    method: 'POST',
    body: JSON.stringify({ username, password }),
  });
  /* Guardar el token en localStorage */
  localStorage.setItem('oig_token', data.token);
  return data;
}

/* Obtener el perfil del usuario autenticado */
export async function apiGetMe() {
  return await request('/auth/me');
}

/* Cerrar sesión (eliminar token local) */
export function apiLogout() {
  localStorage.removeItem('oig_token');
}

/* ============================================= */
/* FUNCIONES DE GESTIÓN DE CASOS                 */
/* ============================================= */

/* Obtener todos los casos */
export async function apiGetCases() {
  return await request('/cases');
}

/* Crear un nuevo caso */
export async function apiCreateCase(caseData) {
  return await request('/cases', {
    method: 'POST',
    body: JSON.stringify(caseData),
  });
}

/* Actualizar un caso existente */
export async function apiUpdateCase(id, caseData) {
  return await request(`/cases/${id}`, {
    method: 'PUT',
    body: JSON.stringify(caseData),
  });
}

/* Eliminar un caso */
export async function apiDeleteCase(id) {
  return await request(`/cases/${id}`, {
    method: 'DELETE',
  });
}

/* ============================================= */
/* FUNCIONES DE HISTORIAL                        */
/* ============================================= */

/* Obtener todo el historial */
export async function apiGetHistory() {
  return await request('/history');
}

/* Guardar un nuevo análisis en el historial */
export async function apiSaveHistory(entry) {
  return await request('/history', {
    method: 'POST',
    body: JSON.stringify(entry),
  });
}

/* Eliminar un análisis del historial */
export async function apiDeleteHistory(id) {
  return await request(`/history/${id}`, {
    method: 'DELETE',
  });
}

/* ============================================= */
/* FUNCIONES DE CONFIGURACIÓN                    */
/* ============================================= */

/* Obtener el estado de la API key */
export async function apiGetApiKeyStatus() {
  return await request('/settings/api-key');
}

/* Guardar la API key */
export async function apiSaveApiKey(apiKey) {
  return await request('/settings/api-key', {
    method: 'PUT',
    body: JSON.stringify({ apiKey }),
  });
}

/* Eliminar la API key */
export async function apiDeleteApiKey() {
  return await request('/settings/api-key', {
    method: 'DELETE',
  });
}

/* Obtener la API key completa (para el pipeline de IA) */
export async function apiGetFullApiKey() {
  return await request('/settings/api-key/full');
}

/* ============================================= */
/* FUNCIONES DE ADMINISTRACIÓN DE USUARIOS       */
/* ============================================= */

/* Obtener todos los usuarios */
export async function apiGetUsers() {
  return await request('/admin/users');
}

/* Crear un nuevo usuario */
export async function apiCreateUser(userData) {
  return await request('/admin/users', {
    method: 'POST',
    body: JSON.stringify(userData),
  });
}

/* Actualizar un usuario existente */
export async function apiUpdateUser(id, userData) {
  return await request(`/admin/users/${id}`, {
    method: 'PUT',
    body: JSON.stringify(userData),
  });
}

/* Eliminar un usuario */
export async function apiDeleteUser(id) {
  return await request(`/admin/users/${id}`, {
    method: 'DELETE',
  });
}

/* ============================================= */
/* FUNCIONES DE PROMPTS DE IA (por caso)         */
/* ============================================= */

/* Obtener los prompts para un caso específico */
export async function apiGetPromptsForCase(caseId) {
  return await request(`/prompts/case/${caseId}`);
}

/* Guardar un prompt personalizado para un caso */
export async function apiUpdateCasePrompt(caseId, promptId, content) {
  return await request(`/prompts/case/${caseId}/${promptId}`, {
    method: 'PUT',
    body: JSON.stringify({ content }),
  });
}

/* Eliminar el override de un caso (restaura al default) */
export async function apiResetCasePrompt(caseId, promptId) {
  return await request(`/prompts/case/${caseId}/${promptId}`, {
    method: 'DELETE',
  });
}

/* Obtener los defaults globales (para mostrar como referencia) */
export async function apiGetDefaultPrompts() {
  return await request('/prompts');
}

/* ============================================= */
/* FUNCIONES DE EXTRACCIÓN DE ARCHIVOS           */
/* ============================================= */

/* Extraer archivos de un RAR en el servidor */
export async function apiExtractRar(file) {
  const formData = new FormData();
  formData.append('file', file);
  const token = getToken();
  const response = await fetch(`${API_BASE}/extract`, {
    method: 'POST',
    headers: token ? { 'Authorization': `Bearer ${token}` } : {},
    body: formData,
  });
  const data = await response.json();
  if (!response.ok) {
    throw new Error(data.error || `Error ${response.status}`);
  }
  return data;
}
