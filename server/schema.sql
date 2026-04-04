-- ============================================= --
-- ESQUEMA DE BASE DE DATOS                      --
-- Control de Permisos - OIG PerÃƒÂº                --
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


-- Migraciones para tablas existentes
DO $$ BEGIN
  ALTER TABLE analysis_checklist_results ADD COLUMN IF NOT EXISTS person_name VARCHAR(500) NOT NULL DEFAULT '';
  ALTER TABLE analysis_history ADD COLUMN IF NOT EXISTS request_name VARCHAR(500) NOT NULL DEFAULT '';
EXCEPTION WHEN OTHERS THEN NULL;
END $$;

-- Tabla de casos de validaciÃƒÂ³n
CREATE TABLE IF NOT EXISTS cases (
  id          VARCHAR(100) PRIMARY KEY,
  name        VARCHAR(255) NOT NULL,
  icon        VARCHAR(10) NOT NULL DEFAULT 'Ã°Å¸â€œâ€¹',
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
  status          VARCHAR(20) NOT NULL DEFAULT 'leÃƒÂ­do'
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

-- Tabla de configuraciÃƒÂ³n por usuario (API key, etc.)
CREATE TABLE IF NOT EXISTS user_settings (
  id          SERIAL PRIMARY KEY,
  user_id     INTEGER UNIQUE NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  api_key     TEXT DEFAULT ''
);

-- Tabla de configuraciÃƒÂ³n global (API key compartida, etc.)
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
-- Solo se ejecuta si la tabla cases estÃƒÂ¡ vacÃƒÂ­a,  --
-- asÃƒÂ­ los cambios del usuario nunca se pierden   --
-- ============================================= --
DO $$ BEGIN
  IF (SELECT COUNT(*) FROM cases) = 0 THEN

    INSERT INTO cases (id, name, icon, color, description, is_default) VALUES
      ('NO_CONDUCTOR', 'Personal No Conductor', 'Ã°Å¸â€˜Â¤', '#3B9EFF', 'HabilitaciÃƒÂ³n de personal que no conduce vehÃƒÂ­culos en Lote X', TRUE),
      ('CONDUCTOR',    'Personal Conductor',    'Ã°Å¸Å¡â€”', '#F5C842', 'HabilitaciÃƒÂ³n de personal que conduce vehÃƒÂ­culos dentro del Lote X', TRUE),
      ('VEHICULO',     'VehÃƒÂ­culos / Equipos',   'Ã°Å¸Å¡â„¢', '#B07EFF', 'HabilitaciÃƒÂ³n de vehÃƒÂ­culos y equipos para ingreso a Lote X', TRUE);

    INSERT INTO case_checklist (case_id, question, sort_order) VALUES
      ('NO_CONDUCTOR', 'Ã‚Â¿El SCTR estÃƒÂ¡ vigente y el personal estÃƒÂ¡ inscrito correctamente?', 1),
      ('NO_CONDUCTOR', 'Ã‚Â¿El DNI escaneado es legible y los datos corresponden al personal declarado?', 2),
      ('NO_CONDUCTOR', 'Ã‚Â¿El Anexo A estÃƒÂ¡ completo y firmado por el supervisor?', 3),
      ('NO_CONDUCTOR', 'Ã‚Â¿El personal aprobÃƒÂ³ el curso de InducciÃƒÂ³n OIG?', 4),
      ('NO_CONDUCTOR', 'Ã‚Â¿Los datos del personal son consistentes en todos los documentos?', 5),
      ('NO_CONDUCTOR', 'Ã‚Â¿La documentaciÃƒÂ³n fue enviada por el proveedor correcto?', 6),
      ('NO_CONDUCTOR', 'Ã‚Â¿No hay documentos vencidos en la solicitud?', 7),
      ('CONDUCTOR', 'Ã‚Â¿El SCTR del conductor estÃƒÂ¡ vigente?', 1),
      ('CONDUCTOR', 'Ã‚Â¿El brevete estÃƒÂ¡ vigente y es de la categorÃƒÂ­a correcta para el vehÃƒÂ­culo?', 2),
      ('CONDUCTOR', 'Ã‚Â¿El certificado de manejo defensivo externo estÃƒÂ¡ vigente?', 3),
      ('CONDUCTOR', 'Ã‚Â¿El examen teÃƒÂ³rico de manejo fue aprobado?', 4),
      ('CONDUCTOR', 'Ã‚Â¿El examen prÃƒÂ¡ctico de manejo fue aprobado?', 5),
      ('CONDUCTOR', 'Ã‚Â¿Se adjunta contrato del personal para verificar vÃƒÂ­nculo laboral?', 6),
      ('CONDUCTOR', 'Ã‚Â¿Los datos coinciden en brevete, DNI y SCTR?', 7),
      ('CONDUCTOR', 'Ã‚Â¿El conductor tiene el Anexo C si es renovaciÃƒÂ³n?', 8),
      ('VEHICULO', 'Ã‚Â¿El Anexo H (checklist vehicular) estÃƒÂ¡ incluido y firmado?', 1),
      ('VEHICULO', 'Ã‚Â¿El SOAT estÃƒÂ¡ vigente?', 2),
      ('VEHICULO', 'Ã‚Â¿La tarjeta de propiedad o contrato de arrendamiento estÃƒÂ¡ incluido?', 3),
      ('VEHICULO', 'Ã‚Â¿La inspecciÃƒÂ³n vehicular fue aprobada por QHSE?', 4),
      ('VEHICULO', 'Ã‚Â¿El vehÃƒÂ­culo cumple con el checklist de inspecciÃƒÂ³n OIG?', 5),
      ('VEHICULO', 'Ã‚Â¿Los documentos del conductor asignado estÃƒÂ¡n incluidos?', 6),
      ('VEHICULO', 'Ã‚Â¿Placa, marca y modelo son consistentes en todos los documentos?', 7),
      ('VEHICULO', 'Ã‚Â¿Se usÃƒÂ³ Anexo D si es renovaciÃƒÂ³n?', 8);

  END IF;
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