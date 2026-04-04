# Deploy en Railway

## 1) Crear proyecto
- En Railway: `New Project` -> `Deploy from GitHub repo`.
- Selecciona `wilderganoza/field-access-management`.

## 2) Base de datos
- Agrega un servicio PostgreSQL dentro del mismo proyecto Railway.
- Railway creara `DATABASE_URL` automaticamente.

## 3) Variables de entorno del servicio web
- `JWT_SECRET`: una clave larga y privada.
- `NODE_ENV`: `production`.

No configures `SERVER_PORT`; Railway inyecta `PORT` automaticamente y la app ya lo usa.

## 4) Comandos (ya configurados en `railway.json`)
- Build: `npm install --include=dev && npm run build`
- Start: `npm start`
- Healthcheck: `/api/health`

## 5) Primer acceso
En despliegues con base vacia, el esquema crea un usuario admin inicial:
- Usuario: `admin`
- Contrasena: `Admin1234!`

Cambia esa contrasena apenas ingreses.
