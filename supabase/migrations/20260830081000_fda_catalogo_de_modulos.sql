-- Catalogo de modulos y perfiles de `fda`.
--
-- Es el arbol que se ve en el menu y la matriz de permisos que lo
-- gobierna. Se versiona para que un despliegue nuevo arranque con los
-- mismos modulos: sin esto la pantalla de perfiles saldria vacia y no
-- habria nada que conceder.
--
-- Idempotente: `on conflict` deja renombrar un modulo desde la
-- aplicacion sin que volver a aplicar la migracion lo revierta.

insert into fda.modules (key, name, parent_id, table_name, sort_order) values ('requests', 'Nueva solicitud', null, 'analysis_history', 10) on conflict (key) do update set name=excluded.name, parent_id=excluded.parent_id, table_name=excluded.table_name, sort_order=excluded.sort_order;
insert into fda.modules (key, name, parent_id, table_name, sort_order) values ('history', 'Historial', null, 'analysis_checklist_results', 20) on conflict (key) do update set name=excluded.name, parent_id=excluded.parent_id, table_name=excluded.table_name, sort_order=excluded.sort_order;
insert into fda.modules (key, name, parent_id, table_name, sort_order) values ('cases', 'Casos', null, 'cases', 30) on conflict (key) do update set name=excluded.name, parent_id=excluded.parent_id, table_name=excluded.table_name, sort_order=excluded.sort_order;
insert into fda.modules (key, name, parent_id, table_name, sort_order) values ('prompts', 'Prompts', null, 'global_settings', 40) on conflict (key) do update set name=excluded.name, parent_id=excluded.parent_id, table_name=excluded.table_name, sort_order=excluded.sort_order;
insert into fda.modules (key, name, parent_id, table_name, sort_order) values ('admin/users', 'Usuarios', null, 'users', 90) on conflict (key) do update set name=excluded.name, parent_id=excluded.parent_id, table_name=excluded.table_name, sort_order=excluded.sort_order;
insert into fda.modules (key, name, parent_id, table_name, sort_order) values ('admin/roles', 'Perfiles', null, 'roles', 95) on conflict (key) do update set name=excluded.name, parent_id=excluded.parent_id, table_name=excluded.table_name, sort_order=excluded.sort_order;
insert into fda.modules (key, name, parent_id, table_name, sort_order) values ('cases.checklist', 'Checklist', (select id from fda.modules where key = 'cases'), 'case_checklist', 10) on conflict (key) do update set name=excluded.name, parent_id=excluded.parent_id, table_name=excluded.table_name, sort_order=excluded.sort_order;
insert into fda.modules (key, name, parent_id, table_name, sort_order) values ('history.analysis-files', 'Archivos del análisis', (select id from fda.modules where key = 'history'), 'analysis_files', 600) on conflict (key) do update set name=excluded.name, parent_id=excluded.parent_id, table_name=excluded.table_name, sort_order=excluded.sort_order;
insert into fda.modules (key, name, parent_id, table_name, sort_order) values ('prompts.prompt-templates', 'Plantillas', (select id from fda.modules where key = 'prompts'), 'prompt_templates', 600) on conflict (key) do update set name=excluded.name, parent_id=excluded.parent_id, table_name=excluded.table_name, sort_order=excluded.sort_order;

insert into fda.roles (key, name, description, is_system) values ('admin', 'Administrador', 'Acceso total, incluida la gestion de usuarios y perfiles.', true) on conflict (key) do nothing;
insert into fda.roles (key, name, description, is_system) values ('lector', 'Lector', 'Solo consulta.', false) on conflict (key) do nothing;
insert into fda.roles (key, name, description, is_system) values ('operador', 'Operador', 'Trabaja con los datos de la aplicacion; no administra cuentas.', true) on conflict (key) do nothing;

-- Los permisos de los perfiles de sistema. Un perfil creado desde la
-- pantalla no se toca aqui: sus permisos los decide quien lo creo.
insert into fda.role_permissions (role_id, module_id, can_view, can_create, can_edit, can_delete, can_download) select r.id, m.id, true, true, true, true, true from fda.roles r cross join fda.modules m where r.key = 'admin' on conflict (role_id, module_id) do nothing;
insert into fda.role_permissions (role_id, module_id, can_view, can_create, can_edit, can_delete, can_download) select r.id, m.id, true, true, true, true, true from fda.roles r cross join fda.modules m where r.key = 'operador' and m.key not like 'admin/%' on conflict (role_id, module_id) do nothing;
