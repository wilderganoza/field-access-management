-- FDA estrena tabla de usuarios propia, con la misma forma que la de FDP.
--
-- Hasta ahora tenia `user_profiles`: un perfil colgado del uuid de Supabase
-- Auth, sin correo ni contrasena, porque de eso se encargaba GoTrue. Al dejar
-- de usar Supabase Auth, la aplicacion necesita una tabla de usuarios de
-- verdad, y siendo hermana de FDP tiene que ser la misma tabla.
--
-- Se puede reemplazar sin cuidados especiales porque `user_profiles` esta
-- vacia y `analysis_history` no tiene ni una fila: no hay nada que preservar.

create table if not exists fda.users (
  id                   serial primary key,
  username             varchar(150) not null,
  email                varchar(255) not null,
  password_hash        varchar(255) not null default '',
  full_name            varchar(255) not null default '',
  department           varchar(255) not null default '',
  position             varchar(255) not null default '',
  role_id              integer references fda.roles(id) on delete set null,
  is_active            boolean      not null default true,
  -- Una cuenta creada por un administrador entra con contrasena ajena: se le
  -- exige cambiarla antes de dejarla llegar a ningun otro sitio
  must_change_password boolean      not null default true,
  reset_token          varchar(255),
  reset_token_expires  timestamptz,
  last_login_at        timestamptz,
  created_at           timestamptz  not null default now(),
  updated_at           timestamptz  not null default now()
);

-- Correo y usuario son unicos sin distinguir mayusculas: si no, `Ana@x.com` y
-- `ana@x.com` serian dos cuentas distintas y el login resolveria una u otra
create unique index if not exists ux_users_email_lower    on fda.users (lower(email));
create unique index if not exists ux_users_username_lower on fda.users (lower(username));
create index        if not exists ix_users_role_id        on fda.users (role_id);

-- El historial pasa a apuntar a la tabla nueva. La columna era uuid porque
-- referenciaba el perfil de Auth; ahora es el entero de `fda.users`.
alter table fda.analysis_history drop constraint if exists analysis_history_user_id_fkey;
alter table fda.analysis_history drop column if exists user_id;
alter table fda.analysis_history add column user_id integer;

alter table fda.analysis_history
  add constraint analysis_history_user_id_fkey
  foreign key (user_id) references fda.users(id) on delete set null;

create index if not exists ix_analysis_history_user_id on fda.analysis_history (user_id);

-- Y se retira la tabla anterior, que ya no tiene contenido ni quien la apunte
drop table if exists fda.user_profiles;
