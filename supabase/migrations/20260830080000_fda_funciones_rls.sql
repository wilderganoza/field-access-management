-- Funciones que evaluan una politica RLS.
--
-- Dentro de una politica solo se dispone de los claims del token que PostgREST
-- ya verifico. `current_user_id()` saca de ahi el identificador entero de
-- `users`, y `puede()` lo traduce al perfil de esa cuenta.
--
-- SECURITY DEFINER porque `authenticated` no tiene permiso de lectura sobre
-- `users`, `roles` ni `role_permissions`: la politica necesita consultarlas, el
-- usuario no debe poder leerlas.
--
-- `search_path` vacio: en una funcion SECURITY DEFINER un path heredado deja
-- que quien la llama anteponga un esquema propio con tablas falsas y se conceda
-- a si mismo lo que quiera.
--
-- STABLE para que el planificador la evalue una vez por sentencia y no una vez
-- por fila. Con RLS activo esa diferencia decide si un listado tarda
-- milisegundos o segundos.

CREATE OR REPLACE FUNCTION fda.current_user_id()
 RETURNS integer
 LANGUAGE sql
 STABLE
AS $function$
        -- El nullif va ANTES del cast: sin token, `request.jwt.claims` es la
        -- cadena vacia, y ''::jsonb no es json vacio, es un error de sintaxis
        -- que tumbaba la politica entera en vez de negar el acceso.
        select nullif(
                 nullif(current_setting('request.jwt.claims', true), '')::jsonb ->> 'app_user_id',
                 ''
               )::integer
      $function$
;

CREATE OR REPLACE FUNCTION fda.puede(p_tabla text, p_accion text)
 RETURNS boolean
 LANGUAGE sql
 STABLE SECURITY DEFINER
 SET search_path TO ''
AS $function$
        with yo as (
          select u.role_id
            from fda.users u
           where u.id = fda.current_user_id()
             and u.is_active
        ),
        -- El modulo que gobierna esa tabla, y su padre por si hereda
        objetivo as (
          select m.id, m.parent_id
            from fda.modules m
           where m.table_name = p_tabla
             and m.is_active
        )
        select exists (
          select 1
            from fda.role_permissions rp
            join yo on yo.role_id = rp.role_id
            join objetivo o on rp.module_id in (o.id, o.parent_id)
           where case p_accion
                   when 'view'     then rp.can_view
                   when 'create'   then rp.can_create
                   when 'edit'     then rp.can_edit
                   when 'delete'   then rp.can_delete
                   when 'download' then rp.can_download
                   else false
                 end
        )
      $function$
;

CREATE OR REPLACE FUNCTION fda.purgar_documentos_vencidos()
 RETURNS integer
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO ''
AS $function$
declare
  borrados integer := 0;
begin
  -- Se retiran del indice de Storage los objetos cuyo plazo vencio
  with vencidos as (
    select f.id, f.storage_path
      from fda.analysis_files f
     where f.storage_path is not null
       and f.retain_until is not null
       and f.retain_until < now()
  ),
  quitados as (
    delete from storage.objects o
     using vencidos v
     where o.bucket_id = 'fda-documentos'
       and o.name = v.storage_path
    returning o.name
  )
  select count(*) into borrados from quitados;

  -- Y se suelta la referencia: la fila queda como constancia de que ese
  -- documento existio y se analizo, sin apuntar a un archivo que ya no esta
  update fda.analysis_files
     set storage_path = null,
         status = 'caducado'
   where storage_path is not null
     and retain_until is not null
     and retain_until < now();

  if borrados > 0 then
    raise log 'Retencion FDA: % documento(s) retirados por vencimiento', borrados;
  end if;

  return borrados;
end $function$
;

grant execute on function fda.current_user_id() to authenticated;
grant execute on function fda.puede(text, text) to authenticated;
