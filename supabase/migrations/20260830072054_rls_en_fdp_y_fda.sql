-- Activa RLS en las dos aplicaciones y escribe sus politicas.
--
-- Cada tabla se gobierna por el modulo que la declara en `modules.table_name`,
-- y `puede(tabla, accion)` traduce eso al perfil de quien pregunta. Asi las
-- politicas no hay que mantenerlas a mano tabla por tabla: cambian solas cuando
-- se cambia un permiso en la pantalla de perfiles.
--
-- Esto NO afecta todavia a las aplicaciones: se conectan como `postgres`, que
-- ignora RLS. Empieza a regir cuando la capa de datos pase por PostgREST con el
-- token del usuario. Se activa antes a proposito: exponer los esquemas sin
-- politicas dejaria las tablas abiertas a cualquier autenticado.
--
-- `force row level security` para que ni el dueño de la tabla se las salte.

do $$
declare
  esq   text;
  t     text;
  op    text;
  accion text;
  cuerpo text;
  expr  text;
begin
  foreach esq in array array['fdp', 'fda'] loop
    for t in
      select table_name from information_schema.tables
       where table_schema = esq and table_type = 'BASE TABLE'
       order by table_name
    loop
      execute format('alter table %I.%I enable row level security', esq, t);
      execute format('alter table %I.%I force  row level security', esq, t);

      -- `modules` y `role_permissions` se quedan sin politica a proposito: las
      -- lee `puede()`, que es SECURITY DEFINER, y nadie mas debe tocarlas
      if t in ('modules', 'role_permissions') then
        continue;
      end if;

      foreach op in array array['select', 'insert', 'update', 'delete'] loop
        accion := case op
                    when 'select' then 'view'
                    when 'insert' then 'create'
                    when 'update' then 'edit'
                    else 'delete'
                  end;

        expr := format('%I.puede(%L, %L)', esq, t, accion);

        cuerpo := case op
                    when 'insert' then 'with check (' || expr || ')'
                    when 'update' then 'using (' || expr || ') with check (' || expr || ')'
                    else 'using (' || expr || ')'
                  end;

        execute format('drop policy if exists %I on %I.%I', t || '_' || op, esq, t);
        execute format('create policy %I on %I.%I for %s to authenticated %s',
                       t || '_' || op, esq, t, op, cuerpo);
      end loop;
    end loop;
  end loop;
end $$;
