/* ============================================= */
/* CONFIGURACIÓN DE CONEXIÓN A POSTGRESQL        */
/* Pool de conexiones reutilizable               */
/* ============================================= */
const { Pool } = require('pg');
require('dotenv').config();

/* Crear pool de conexiones.
   En Render se provee DATABASE_URL (connection string completo).
   En desarrollo local se usan variables individuales. */
const pool = process.env.DATABASE_URL
  ? new Pool({
      connectionString: process.env.DATABASE_URL,
      ssl: { rejectUnauthorized: false },
    })
  : new Pool({
      host: process.env.DB_HOST || 'localhost',
      port: parseInt(process.env.DB_PORT || '5432'),
      database: process.env.DB_NAME || 'control_permisos',
      user: process.env.DB_USER || 'postgres',
      password: process.env.DB_PASSWORD || 'postgres',
    });

/* Verificar la conexión al iniciar */
pool.on('connect', () => {
  console.log('[DB] Conexión a PostgreSQL establecida');
});

/* Manejar errores del pool */
pool.on('error', (err) => {
  console.error('[DB] Error inesperado en el pool:', err);
});

module.exports = pool;
