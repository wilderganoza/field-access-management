-- Quien puede tocar los documentos del bucket.
--
-- Se apoya en el mismo perfil que todo lo demas: `fda.puede()` sobre la tabla
-- `analysis_files`, que cuelga del modulo Historial. Asi un perfil sin permiso
-- de descarga tampoco obtiene los archivos, y no hay dos sitios donde decidir
-- lo mismo de forma distinta.
--
-- `anon` no aparece: aqui no hay nada publico.

do $$
declare op text;
begin
  foreach op in array array['select','insert','update','delete'] loop
    execute format('drop policy if exists %I on storage.objects', 'fda_documentos_' || op);
  end loop;
end $$;

-- Ver y descargar: exige permiso de descarga sobre el modulo del historial
create policy "fda_documentos_select" on storage.objects
  for select to authenticated
  using (
    bucket_id = 'fda-documentos'
    and fda.puede('analysis_files', 'download')
  );

-- Subir: exige poder crear una solicitud, que es cuando se suben
create policy "fda_documentos_insert" on storage.objects
  for insert to authenticated
  with check (
    bucket_id = 'fda-documentos'
    and fda.puede('analysis_files', 'create')
  );

-- Reemplazar un archivo ya subido
create policy "fda_documentos_update" on storage.objects
  for update to authenticated
  using (
    bucket_id = 'fda-documentos'
    and fda.puede('analysis_files', 'edit')
  )
  with check (
    bucket_id = 'fda-documentos'
    and fda.puede('analysis_files', 'edit')
  );

-- Y borrar, que es lo que ocurre al eliminar un caso o al vencer la retencion
create policy "fda_documentos_delete" on storage.objects
  for delete to authenticated
  using (
    bucket_id = 'fda-documentos'
    and fda.puede('analysis_files', 'delete')
  );

-- `puede()` es SECURITY DEFINER y vive en el esquema fda; storage necesita
-- poder invocarla desde sus politicas
grant usage on schema fda to authenticated;
grant execute on function fda.puede(text, text) to authenticated;
