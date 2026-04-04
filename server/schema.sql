-- ============================================= --
-- ESQUEMA DE BASE DE DATOS                      --
-- Control de Permisos - OIG PerÃº                --
-- ============================================= --

-- Tabla de usuarios del sistema
CREATE TABLE IF NOT EXISTS users (
  id          SERIAL PRIMARY KEY,
  username    VARCHAR(100) UNIQUE NOT NULL,
  password    VARCHAR(255) NOT NULL,
  role        VARCHAR(50) NOT NULL DEFAULT 'operador',
  full_name   VARCHAR(255) DEFAULT '',
  email       VARCHAR(255) DEFAULT '',
  department  VARCHAR(255) DEFAULT '',
  position    VARCHAR(255) DEFAULT '',
  is_active   BOOLEAN NOT NULL DEFAULT TRUE,
  created_at  TIMESTAMP DEFAULT NOW()
);

-- Agregar columnas nuevas si la tabla ya existe (migraciones)
DO $$ BEGIN
  ALTER TABLE users ADD COLUMN IF NOT EXISTS full_name VARCHAR(255) DEFAULT '';
  ALTER TABLE users ADD COLUMN IF NOT EXISTS email VARCHAR(255) DEFAULT '';
  ALTER TABLE users ADD COLUMN IF NOT EXISTS department VARCHAR(255) DEFAULT '';
  ALTER TABLE users ADD COLUMN IF NOT EXISTS position VARCHAR(255) DEFAULT '';
  ALTER TABLE users ADD COLUMN IF NOT EXISTS is_active BOOLEAN NOT NULL DEFAULT TRUE;
EXCEPTION WHEN OTHERS THEN NULL;
END $$;

-- ============================================= --
-- USUARIO BASE INICIAL (solo primera vez)       --
-- admin / hALYSibaCesc                          --
-- ============================================= --
DO $$ BEGIN
  IF (SELECT COUNT(*) FROM users) = 0 THEN
    INSERT INTO users (
      username, password, role, full_name, email, department, position, is_active
    ) VALUES (
      'admin',
      '$2b$10$R79zB2Wz9.ln4/P4Tk79ZuyDZvvUEpT3kNS/tZDwFCdq9MImfuRAm',
      'admin',
      'Administrador',
      '',
      '',
      '',
      TRUE
    );

    INSERT INTO user_settings (user_id)
    SELECT id FROM users WHERE username = 'admin'
    ON CONFLICT (user_id) DO NOTHING;
  END IF;
END $$;

-- Migraciones para tablas existentes
DO $$ BEGIN
  ALTER TABLE analysis_checklist_results ADD COLUMN IF NOT EXISTS person_name VARCHAR(500) NOT NULL DEFAULT '';
  ALTER TABLE analysis_history ADD COLUMN IF NOT EXISTS request_name VARCHAR(500) NOT NULL DEFAULT '';
EXCEPTION WHEN OTHERS THEN NULL;
END $$;

-- Tabla de casos de validaciÃ³n
CREATE TABLE IF NOT EXISTS cases (
  id          VARCHAR(100) PRIMARY KEY,
  name        VARCHAR(255) NOT NULL,
  icon        VARCHAR(10) NOT NULL DEFAULT 'ðŸ“‹',
  color       VARCHAR(7) NOT NULL DEFAULT '#3B9EFF',
  description TEXT NOT NULL DEFAULT '',
  is_default  BOOLEAN NOT NULL DEFAULT FALSE,
  created_at  TIMESTAMP DEFAULT NOW()
);

-- Tabla de preguntas del checklist por caso
CREATE TABLE IF NOT EXISTS case_checklist (
  id          SERIAL PRIMARY KEY,
  case_id     VARCHAR(100) NOT NULL REFERENCES cases(id) ON DELETE CASCADE,
  question    TEXT NOT NULL,
  sort_order  INTEGER NOT NULL DEFAULT 0,
  UNIQUE(case_id, question)
);

-- Tabla de historial de solicitudes procesadas
CREATE TABLE IF NOT EXISTS analysis_history (
  id              VARCHAR(100) PRIMARY KEY,
  user_id         INTEGER REFERENCES users(id),
  request_name    VARCHAR(500) NOT NULL DEFAULT '',
  case_id         VARCHAR(100) NOT NULL,
  case_name       VARCHAR(255) NOT NULL,
  case_icon       VARCHAR(10) NOT NULL,
  case_color      VARCHAR(7) NOT NULL,
  email_from      TEXT DEFAULT 'N/A',
  email_to        TEXT DEFAULT 'N/A',
  email_subject   TEXT DEFAULT 'Sin asunto',
  email_date      TEXT DEFAULT 'N/A',
  email_body      TEXT DEFAULT '',
  summary         TEXT DEFAULT '',
  verdict         VARCHAR(20) NOT NULL DEFAULT 'PENDIENTE',
  created_at      TIMESTAMP DEFAULT NOW()
);

-- Tabla de archivos procesados por solicitud
CREATE TABLE IF NOT EXISTS analysis_files (
  id              SERIAL PRIMARY KEY,
  analysis_id     VARCHAR(100) NOT NULL REFERENCES analysis_history(id) ON DELETE CASCADE,
  name            VARCHAR(500) NOT NULL,
  file_type       VARCHAR(50) NOT NULL,
  status          VARCHAR(20) NOT NULL DEFAULT 'leÃ­do'
);

-- Tabla de resultados del checklist por solicitud
CREATE TABLE IF NOT EXISTS analysis_checklist_results (
  id              SERIAL PRIMARY KEY,
  analysis_id     VARCHAR(100) NOT NULL REFERENCES analysis_history(id) ON DELETE CASCADE,
  person_name     VARCHAR(500) NOT NULL DEFAULT '',
  question        TEXT NOT NULL,
  result          VARCHAR(20) NOT NULL DEFAULT 'PENDIENTE',
  explanation     TEXT DEFAULT ''
);

-- Tabla de configuraciÃ³n por usuario (API key, etc.)
CREATE TABLE IF NOT EXISTS user_settings (
  id          SERIAL PRIMARY KEY,
  user_id     INTEGER UNIQUE NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  api_key     TEXT DEFAULT ''
);

-- Tabla de configuraciÃ³n global (API key compartida, etc.)
CREATE TABLE IF NOT EXISTS global_settings (
  key         VARCHAR(100) PRIMARY KEY,
  value       TEXT DEFAULT ''
);

-- Tabla de plantillas de prompts de IA (editables desde la UI)
CREATE TABLE IF NOT EXISTS prompt_templates (
  id          VARCHAR(100) PRIMARY KEY,
  content     TEXT NOT NULL,
  updated_at  TIMESTAMP DEFAULT NOW()
);

-- ============================================= --
-- INSERTAR CASOS PREDETERMINADOS (solo primera vez)
-- Solo se ejecuta si la tabla cases estÃ¡ vacÃ­a,  --
-- asÃ­ los cambios del usuario nunca se pierden   --
-- ============================================= --
DO $$ BEGIN
  IF (SELECT COUNT(*) FROM cases) = 0 THEN

    INSERT INTO cases (id, name, icon, color, description, is_default) VALUES
      ('NO_CONDUCTOR', 'Personal No Conductor', 'ðŸ‘¤', '#3B9EFF', 'HabilitaciÃ³n de personal que no conduce vehÃ­culos en Lote X', TRUE),
      ('CONDUCTOR',    'Personal Conductor',    'ðŸš—', '#F5C842', 'HabilitaciÃ³n de personal que conduce vehÃ­culos dentro del Lote X', TRUE),
      ('VEHICULO',     'VehÃ­culos / Equipos',   'ðŸš™', '#B07EFF', 'HabilitaciÃ³n de vehÃ­culos y equipos para ingreso a Lote X', TRUE);

    INSERT INTO case_checklist (case_id, question, sort_order) VALUES
      ('NO_CONDUCTOR', 'Â¿El SCTR estÃ¡ vigente y el personal estÃ¡ inscrito correctamente?', 1),
      ('NO_CONDUCTOR', 'Â¿El DNI escaneado es legible y los datos corresponden al personal declarado?', 2),
      ('NO_CONDUCTOR', 'Â¿El Anexo A estÃ¡ completo y firmado por el supervisor?', 3),
      ('NO_CONDUCTOR', 'Â¿El personal aprobÃ³ el curso de InducciÃ³n OIG?', 4),
      ('NO_CONDUCTOR', 'Â¿Los datos del personal son consistentes en todos los documentos?', 5),
      ('NO_CONDUCTOR', 'Â¿La documentaciÃ³n fue enviada por el proveedor correcto?', 6),
      ('NO_CONDUCTOR', 'Â¿No hay documentos vencidos en la solicitud?', 7),
      ('CONDUCTOR', 'Â¿El SCTR del conductor estÃ¡ vigente?', 1),
      ('CONDUCTOR', 'Â¿El brevete estÃ¡ vigente y es de la categorÃ­a correcta para el vehÃ­culo?', 2),
      ('CONDUCTOR', 'Â¿El certificado de manejo defensivo externo estÃ¡ vigente?', 3),
      ('CONDUCTOR', 'Â¿El examen teÃ³rico de manejo fue aprobado?', 4),
      ('CONDUCTOR', 'Â¿El examen prÃ¡ctico de manejo fue aprobado?', 5),
      ('CONDUCTOR', 'Â¿Se adjunta contrato del personal para verificar vÃ­nculo laboral?', 6),
      ('CONDUCTOR', 'Â¿Los datos coinciden en brevete, DNI y SCTR?', 7),
      ('CONDUCTOR', 'Â¿El conductor tiene el Anexo C si es renovaciÃ³n?', 8),
      ('VEHICULO', 'Â¿El Anexo H (checklist vehicular) estÃ¡ incluido y firmado?', 1),
      ('VEHICULO', 'Â¿El SOAT estÃ¡ vigente?', 2),
      ('VEHICULO', 'Â¿La tarjeta de propiedad o contrato de arrendamiento estÃ¡ incluido?', 3),
      ('VEHICULO', 'Â¿La inspecciÃ³n vehicular fue aprobada por QHSE?', 4),
      ('VEHICULO', 'Â¿El vehÃ­culo cumple con el checklist de inspecciÃ³n OIG?', 5),
      ('VEHICULO', 'Â¿Los documentos del conductor asignado estÃ¡n incluidos?', 6),
      ('VEHICULO', 'Â¿Placa, marca y modelo son consistentes en todos los documentos?', 7),
      ('VEHICULO', 'Â¿Se usÃ³ Anexo D si es renovaciÃ³n?', 8);

  END IF;
END $$;


