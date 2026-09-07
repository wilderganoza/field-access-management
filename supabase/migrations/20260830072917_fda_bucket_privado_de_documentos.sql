-- El bucket donde viven los documentos de las solicitudes.
--
-- PRIVADO, sin excepciones. Lo que se guarda aqui son DNI, licencias de
-- conducir y polizas de personas con nombre y apellido: un bucket publico
-- significa que cualquiera con la URL los descarga, y las URL se filtran.
-- Se sirve solo por URL firmada de vida corta.
--
-- El limite de tamaño y los tipos admitidos se declaran aqui ademas de en la
-- aplicacion: la comprobacion del servidor evita el gasto, la del bucket evita
-- que nadie la salte.

insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values (
  'fda-documentos',
  'fda-documentos',
  false,
  52428800,   -- 50 MB por archivo, lo mismo que admite la pantalla
  array[
    'application/pdf',
    'image/jpeg', 'image/png', 'image/tiff',
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    'application/msword',
    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    'application/vnd.ms-excel',
    'message/rfc822',
    'application/zip', 'application/x-rar-compressed',
    'application/octet-stream'
  ]
)
on conflict (id) do update
  set public = false,
      file_size_limit = excluded.file_size_limit,
      allowed_mime_types = excluded.allowed_mime_types;
