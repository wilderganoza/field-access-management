/* ============================================= */
/* SERVIDOR PRINCIPAL EXPRESS                    */
/* Backend de Control de Permisos - OIG Perú     */
/* ============================================= */
const express = require('express');
const cors = require('cors');
const fs = require('fs');
const path = require('path');
require('dotenv').config();

const pool = require('./db.cjs');
const authRoutes = require('./routes/auth.cjs');
const casesRoutes = require('./routes/cases.cjs');
const historyRoutes = require('./routes/history.cjs');
const settingsRoutes = require('./routes/settings.cjs');
const adminRoutes = require('./routes/admin.cjs');
const extractRoutes = require('./routes/extract.cjs');
const promptsRoutes = require('./routes/prompts.cjs');

/* Crear la aplicación Express */
const app = express();

/* Puerto del servidor desde variables de entorno */
/* Render asigna el puerto en la variable PORT */
const PORT = process.env.PORT || process.env.SERVER_PORT || 3001;

/* Middleware de CORS para permitir peticiones del frontend */
app.use(cors());

/* Middleware para parsear JSON en el body de las peticiones */
app.use(express.json({ limit: '50mb' }));

/* ============================================= */
/* RUTAS DE LA API                               */
/* ============================================= */
app.use('/api/auth', authRoutes);
app.use('/api/cases', casesRoutes);
app.use('/api/history', historyRoutes);
app.use('/api/settings', settingsRoutes);
app.use('/api/admin', adminRoutes);
app.use('/api/extract', extractRoutes);
app.use('/api/prompts', promptsRoutes);

/* Ruta de salud del servidor */
app.get('/api/health', (req, res) => {
  res.json({ status: 'ok', timestamp: new Date().toISOString() });
});

/* ============================================= */
/* SERVIR FRONTEND EN PRODUCCIÓN                 */
/* En Render, el backend sirve los archivos      */
/* estáticos generados por Vite (dist/)          */
/* ============================================= */
const distPath = path.join(__dirname, '..', 'dist');
if (fs.existsSync(distPath)) {
  app.use(express.static(distPath));
  /* Cualquier ruta que no sea /api → devuelve index.html (SPA) */
  app.get('{*path}', (req, res, next) => {
    if (req.path.startsWith('/api')) return next();
    res.sendFile(path.join(distPath, 'index.html'));
  });
  console.log('[SERVER] Sirviendo frontend estático desde dist/');
}

/* ============================================= */
/* INICIALIZACIÓN DE LA BASE DE DATOS            */
/* Ejecuta el esquema SQL al iniciar             */
/* ============================================= */
async function initDatabase() {
  try {
    /* Leer el archivo de esquema SQL */
    const schemaPath = path.join(__dirname, 'schema.sql');
    const schema = fs.readFileSync(schemaPath, 'utf8');
    /* Ejecutar el esquema en la base de datos */
    await pool.query(schema);
    console.log('[DB] Esquema de base de datos inicializado correctamente');
  } catch (err) {
    console.error('[DB] Error al inicializar la base de datos:', err.message);
    console.error('[DB] Asegúrate de que PostgreSQL esté corriendo y la base de datos exista');
    console.error('[DB] Ejecuta: createdb control_permisos');
  }
}

/* ============================================= */
/* INICIAR EL SERVIDOR                           */
/* ============================================= */
async function start() {
  /* Inicializar la base de datos */
  await initDatabase();
  /* Iniciar el servidor HTTP */
  app.listen(PORT, () => {
    console.log(`[SERVER] Servidor corriendo en http://localhost:${PORT}`);
    console.log(`[SERVER] API disponible en http://localhost:${PORT}/api`);
  });
}

/* Ejecutar el inicio del servidor */
start();
