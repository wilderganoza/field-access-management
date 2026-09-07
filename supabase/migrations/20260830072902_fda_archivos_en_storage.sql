-- Los archivos de una solicitud pasan a conservarse.
--
-- Hasta ahora `analysis_files` guardaba solo el nombre y el tipo: los bytes se
-- leian en memoria, se mandaban al modelo y se descartaban. Un caso del
-- historial decia QUE archivos hubo, pero no dejaba abrir ninguno, asi que no
-- habia forma de auditar sobre que se decidio.
--
-- RETENCION: dos años. Y se borran con el caso, sin esperar a que venza el
-- plazo -- son documentos de identidad de personas y no deben sobrevivir al
-- expediente que los justificaba.

alter table fda.analysis_files
  -- Ruta dentro del bucket: `{analysis_id}/{nombre}`. Nula mientras no se haya
  -- subido, para no romper las filas que ya existen.
  add column if not exists storage_path text,

  -- Tamaño real, para poder mostrarlo sin ir al bucket
  add column if not exists size_bytes bigint,

  -- Huella del contenido. Un mismo DNI subido en seis solicitudes se guarda una
  -- vez: con el hash se reconoce que ya esta.
  add column if not exists content_hash varchar(64),

  -- Cuando caduca su conservacion. Se calcula al subir, no al consultar, para
  -- que cambiar la politica no reescriba el pasado en silencio.
  add column if not exists retain_until timestamptz;

create index if not exists ix_analysis_files_storage_path on fda.analysis_files (storage_path);
create index if not exists ix_analysis_files_content_hash on fda.analysis_files (content_hash);
create index if not exists ix_analysis_files_retain_until on fda.analysis_files (retain_until);

comment on column fda.analysis_files.retain_until is
  'Fin del periodo de conservacion (2 anios desde la subida). Los documentos se
   borran antes si se elimina el caso que los justifica.';
