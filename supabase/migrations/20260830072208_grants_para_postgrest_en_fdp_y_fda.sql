-- Da a `authenticated` acceso a los esquemas, ahora que RLS ya los protege.
--
-- El orden importa y este es el correcto: primero se activaron RLS y las
-- politicas, y solo despues se concede el acceso. Al reves habria una ventana
-- en la que cualquier usuario autenticado leeria y escribiria las 75 tablas.
--
-- Estos GRANT no conceden datos: conceden la POSIBILIDAD de preguntar. Que
-- filas se ven y cuales se pueden tocar lo decide la politica, que consulta el
-- perfil de quien pregunta. Sin permiso de tabla, PostgREST responde un error
-- de permisos en vez de una lista vacia, que es peor de diagnosticar.
--
-- `anon` no recibe nada: en estas dos aplicaciones no hay nada publico.

do $$
declare esq text;
begin
  foreach esq in array array['fdp', 'fda'] loop

    execute format('grant usage on schema %I to authenticated', esq);

    execute format(
      'grant select, insert, update, delete on all tables in schema %I to authenticated', esq);

    -- Las secuencias hacen falta para insertar: sin esto, un alta falla al
    -- pedir el siguiente identificador aunque la politica la permita
    execute format('grant usage, select on all sequences in schema %I to authenticated', esq);

    -- Y lo mismo para lo que se cree despues, para que una tabla nueva no
    -- quede inalcanzable hasta que alguien recuerde repetir el grant
    execute format(
      'alter default privileges in schema %I grant select, insert, update, delete on tables to authenticated', esq);
    execute format(
      'alter default privileges in schema %I grant usage, select on sequences to authenticated', esq);

  end loop;
end $$;

-- `modules` y `role_permissions` se leen solo desde `puede()`, que corre como
-- dueña. Nadie mas necesita tocarlas, y tienen RLS sin ninguna politica, asi
-- que el grant de arriba no les abre nada. Se revoca igualmente para que la
-- intencion quede escrita y no dependa de la ausencia de politicas.
revoke all on fdp.modules,          fda.modules          from authenticated;
revoke all on fdp.role_permissions, fda.role_permissions from authenticated;
