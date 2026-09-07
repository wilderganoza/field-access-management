-- Modelo de perfiles y permisos, con la MISMA forma en las dos aplicaciones.
--
-- Tres tablas por esquema:
--   modules            el arbol de modulos y submodulos que se ve en el menu
--   roles              el perfil: un conjunto de permisos con nombre
--   role_permissions   la matriz, con las cinco acciones
--
-- `modules.table_name` es la pieza que permite que una politica RLS sepa que
-- modulo gobierna cada tabla. Sin ella habria que escribir las politicas a mano,
-- tabla por tabla, y mantenerlas sincronizadas para siempre.
--
-- Un submodulo hereda del padre: si el perfil no tiene fila propia para
-- «Assets > Wells» pero si para «Assets», vale la del padre. Asi se puede dar
-- acceso grueso sin enumerar los 34 submodulos de FDP.

do $$
declare
  esq text;
begin
  foreach esq in array array['fdp', 'fda'] loop

    -- El arbol de modulos
    execute format($f$
      create table if not exists %I.modules (
        id          serial primary key,
        key         varchar(100) not null unique,
        name        varchar(150) not null,
        parent_id   integer references %I.modules(id) on delete cascade,
        table_name  varchar(100),
        sort_order  integer not null default 0,
        is_active   boolean not null default true
      )$f$, esq, esq);

    execute format(
      'create index if not exists ix_modules_parent_id on %I.modules (parent_id)', esq);
    execute format(
      'create index if not exists ix_modules_table_name on %I.modules (table_name)', esq);

    -- El perfil
    execute format($f$
      create table if not exists %I.roles (
        id          serial primary key,
        key         varchar(50)  not null unique,
        name        varchar(100) not null,
        description text         not null default '',
        -- Un perfil de sistema no se puede borrar desde la pantalla: si se
        -- pudiera, alguien se quedaria sin forma de administrar la aplicacion
        is_system   boolean      not null default false,
        created_at  timestamptz  not null default now()
      )$f$, esq);

    -- La matriz de permisos
    execute format($f$
      create table if not exists %I.role_permissions (
        role_id      integer not null references %I.roles(id)   on delete cascade,
        module_id    integer not null references %I.modules(id) on delete cascade,
        can_view     boolean not null default false,
        can_create   boolean not null default false,
        can_edit     boolean not null default false,
        can_delete   boolean not null default false,
        can_download boolean not null default false,
        primary key (role_id, module_id)
      )$f$, esq, esq, esq);

    execute format(
      'create index if not exists ix_role_permissions_module_id on %I.role_permissions (module_id)', esq);

  end loop;
end $$;
