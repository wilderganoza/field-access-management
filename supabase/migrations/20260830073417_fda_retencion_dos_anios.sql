-- La retencion de dos anios, ejecutada sola.
--
-- El borrado al eliminar un caso lo hace la aplicacion contra la API de
-- Storage, que es la via que retira el archivo de verdad. Esto es lo otro: el
-- vencimiento del plazo, que no lo dispara ninguna accion del usuario y por eso
-- necesita correr por su cuenta.
--
-- Lo que hace es retirar el objeto del indice de Storage y soltar la referencia
-- en `analysis_files`. La fila del historial se conserva -- que hubo un DNI y
-- que se verifico es justamente lo que hay que poder auditar; lo que caduca es
-- el documento, no el hecho.

create extension if not exists pg_cron;

create or replace function fda.purgar_documentos_vencidos()
returns integer
language plpgsql
security definer
set search_path = ''
as $$
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
end $$;

comment on function fda.purgar_documentos_vencidos() is
  'Retira los documentos cuyo plazo de conservacion de dos anios vencio.';

-- Una vez al dia, de madrugada. No hay prisa: un documento que vence hoy puede
-- retirarse esta noche.
select cron.unschedule('fda-retencion-documentos')
 where exists (select 1 from cron.job where jobname = 'fda-retencion-documentos');

select cron.schedule(
  'fda-retencion-documentos',
  '30 3 * * *',
  $$ select fda.purgar_documentos_vencidos() $$
);
