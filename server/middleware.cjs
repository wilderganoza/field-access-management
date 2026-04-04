/* ============================================= */
/* MIDDLEWARE DE AUTENTICACIÓN JWT                */
/* Verifica el token en cada petición protegida  */
/* ============================================= */
const jwt = require('jsonwebtoken');
require('dotenv').config();

/* Clave secreta para verificar tokens */
const JWT_SECRET = process.env.JWT_SECRET || 'oig_peru_secret';

/* Middleware que verifica el token JWT del header Authorization */
function authMiddleware(req, res, next) {
  /* Extraer el header de autorización */
  const authHeader = req.headers.authorization;
  /* Verificar que exista y tenga formato Bearer */
  if (!authHeader || !authHeader.startsWith('Bearer ')) {
    return res.status(401).json({ error: 'Token no proporcionado' });
  }
  /* Extraer el token del header */
  const token = authHeader.split(' ')[1];
  try {
    /* Verificar y decodificar el token */
    const decoded = jwt.verify(token, JWT_SECRET);
    /* Adjuntar los datos del usuario al request */
    req.user = decoded;
    /* Continuar al siguiente middleware/ruta */
    next();
  } catch (err) {
    /* Token inválido o expirado */
    return res.status(401).json({ error: 'Token inválido o expirado' });
  }
}

module.exports = { authMiddleware, JWT_SECRET };
