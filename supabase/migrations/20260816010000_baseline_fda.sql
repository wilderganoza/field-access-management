-- Migracion base de Verificacion de Permisos (esquema fda).
-- Portada desde server/schema.sql, con tres correcciones:
--   1. El original estaba con doble codificacion UTF-8 ("PerÃƒÂº" en vez de "Peru",
--      iconos de caso corruptos). Aqui el texto va en UTF-8 correcto.
--   2. Los usuarios ya no viven aqui: Supabase Auth gestiona credenciales en
--      auth.users. Esta tabla guarda solo el perfil, referenciado por uuid.
--   3. Se eliminaron los bloques DO $$ de migracion incremental: al partir de
--      cero no hacen falta.

set search_path = fda, public;

-- Perfil de usuario. Las credenciales las gestiona Supabase Auth; aqui solo
-- guardamos los datos de organizacion que la app necesita mostrar y filtrar.
create table if not exists user_profiles (
  id          uuid primary key references auth.users(id) on delete cascade,
  full_name   varchar(255) not null default '',
  department  varchar(255) not null default '',
  position    varchar(255) not null default '',
  role        varchar(50)  not null default 'operador',
  is_active   boolean      not null default true,
  created_at  timestamptz  not null default now(),
  constraint user_profiles_role_check check (role in ('admin', 'operador'))
);

comment on table user_profiles is 'Perfil de organizacion; las credenciales viven en auth.users';

-- Casos de validacion: cada uno define un checklist distinto.
create table if not exists cases (
  id          varchar(100) primary key,
  name        varchar(255) not null,
  icon        varchar(16)  not null default '📋',
  color       varchar(7)   not null default '#4a7cff',
  description text         not null default '',
  is_default  boolean      not null default false,
  created_at  timestamptz  not null default now()
);

-- Preguntas del checklist, ordenadas, por caso.
create table if not exists case_checklist (
  id         serial primary key,
  case_id    varchar(100) not null references cases(id) on delete cascade,
  question   text    not null,
  sort_order integer not null default 0,
  unique (case_id, question)
);

create index if not exists ix_case_checklist_case_id on case_checklist (case_id, sort_order);

-- Historial de solicitudes procesadas.
create table if not exists analysis_history (
  id            varchar(100) primary key,
  user_id       uuid references user_profiles(id) on delete set null,
  request_name  varchar(500) not null default '',
  case_id       varchar(100) not null,
  case_name     varchar(255) not null,
  case_icon     varchar(16)  not null,
  case_color    varchar(7)   not null,
  email_from    text not null default 'N/A',
  email_to      text not null default 'N/A',
  email_subject text not null default 'Sin asunto',
  email_date    text not null default 'N/A',
  email_body    text not null default '',
  summary       text not null default '',
  verdict       varchar(20) not null default 'PENDIENTE',
  created_at    timestamptz not null default now(),
  constraint analysis_history_verdict_check
    check (verdict in ('APROBADO', 'RECHAZADO', 'PENDIENTE'))
);

create index if not exists ix_analysis_history_user_created
  on analysis_history (user_id, created_at desc);

create index if not exists ix_analysis_history_case on analysis_history (case_id);

-- Archivos incluidos en cada solicitud.
create table if not exists analysis_files (
  id          serial primary key,
  analysis_id varchar(100) not null references analysis_history(id) on delete cascade,
  name        varchar(500) not null,
  file_type   varchar(50)  not null,
  status      varchar(20)  not null default 'leido'
);

create index if not exists ix_analysis_files_analysis on analysis_files (analysis_id);

-- Resultado de cada pregunta del checklist, por persona o vehiculo evaluado.
create table if not exists analysis_checklist_results (
  id          serial primary key,
  analysis_id varchar(100) not null references analysis_history(id) on delete cascade,
  person_name varchar(500) not null default '',
  question    text not null,
  result      varchar(20) not null default 'PENDIENTE',
  explanation text not null default '',
  constraint analysis_checklist_results_result_check
    check (result in ('APROBADO', 'RECHAZADO', 'PENDIENTE'))
);

create index if not exists ix_analysis_checklist_analysis
  on analysis_checklist_results (analysis_id);

-- Configuracion global de la aplicacion.
-- Nota: la tabla user_settings del esquema anterior guardaba la API key de
-- OpenAI por usuario, porque el navegador llamaba directo a la API. Ahora la
-- clave vive en el .env del servidor y esa tabla desaparece.
create table if not exists global_settings (
  key        varchar(100) primary key,
  value      text not null default '',
  updated_at timestamptz not null default now()
);

-- Plantillas de prompts editables desde la interfaz.
create table if not exists prompt_templates (
  id         varchar(100) primary key,
  content    text not null,
  updated_at timestamptz not null default now()
);

-- ============================================================
-- Casos predeterminados. Solo se insertan si la tabla esta vacia,
-- para no pisar cambios hechos desde la interfaz.
-- ============================================================
insert into cases (id, name, icon, color, description, is_default)
select * from (values
  ('NO_CONDUCTOR', 'Personal No Conductor', '👤', '#4a7cff',
   'Habilitación de personal que no conduce vehículos en Lote X', true),
  ('CONDUCTOR', 'Personal Conductor', '🚗', '#fbbf24',
   'Habilitación de personal que conduce vehículos dentro del Lote X', true),
  ('VEHICULO', 'Vehículos / Equipos', '🚙', '#a78bfa',
   'Habilitación de vehículos y equipos para ingreso a Lote X', true)
) as v(id, name, icon, color, description, is_default)
where not exists (select 1 from cases);

insert into case_checklist (case_id, question, sort_order)
select * from (values
  ('NO_CONDUCTOR', '¿El SCTR está vigente y el personal está inscrito correctamente?', 1),
  ('NO_CONDUCTOR', '¿El DNI escaneado es legible y los datos corresponden al personal declarado?', 2),
  ('NO_CONDUCTOR', '¿El Anexo A está completo y firmado por el supervisor?', 3),
  ('NO_CONDUCTOR', '¿El personal aprobó el curso de Inducción OIG?', 4),
  ('NO_CONDUCTOR', '¿Los datos del personal son consistentes en todos los documentos?', 5),
  ('NO_CONDUCTOR', '¿La documentación fue enviada por el proveedor correcto?', 6),
  ('NO_CONDUCTOR', '¿No hay documentos vencidos en la solicitud?', 7),
  ('CONDUCTOR', '¿El SCTR del conductor está vigente?', 1),
  ('CONDUCTOR', '¿El brevete está vigente y es de la categoría correcta para el vehículo?', 2),
  ('CONDUCTOR', '¿El certificado de manejo defensivo externo está vigente?', 3),
  ('CONDUCTOR', '¿El examen teórico de manejo fue aprobado?', 4),
  ('CONDUCTOR', '¿El examen práctico de manejo fue aprobado?', 5),
  ('CONDUCTOR', '¿Se adjunta contrato del personal para verificar vínculo laboral?', 6),
  ('CONDUCTOR', '¿Los datos coinciden en brevete, DNI y SCTR?', 7),
  ('CONDUCTOR', '¿El conductor tiene el Anexo C si es renovación?', 8),
  ('VEHICULO', '¿El Anexo H (checklist vehicular) está incluido y firmado?', 1),
  ('VEHICULO', '¿El SOAT está vigente?', 2),
  ('VEHICULO', '¿La tarjeta de propiedad o contrato de arrendamiento está incluido?', 3),
  ('VEHICULO', '¿La inspección vehicular fue aprobada por QHSE?', 4),
  ('VEHICULO', '¿El vehículo cumple con el checklist de inspección OIG?', 5),
  ('VEHICULO', '¿Los documentos del conductor asignado están incluidos?', 6),
  ('VEHICULO', '¿Placa, marca y modelo son consistentes en todos los documentos?', 7),
  ('VEHICULO', '¿Se usó Anexo D si es renovación?', 8)
) as v(case_id, question, sort_order)
where not exists (select 1 from case_checklist);
