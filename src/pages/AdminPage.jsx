/* ============================================= */
/* PÁGINA DE ADMINISTRACIÓN DE USUARIOS          */
/* CRUD completo: crear, editar, desactivar y    */
/* eliminar usuarios del sistema                 */
/* ============================================= */
import { useState, useEffect } from 'react';
import { useApp } from '../context/AppContext';
import ConfirmModal from '../components/ConfirmModal';

/* Roles disponibles para los usuarios */
const ROLES = [
  { value: 'admin', label: 'Administrador' },
  { value: 'operador', label: 'Operador' },
  { value: 'supervisor', label: 'Supervisor' },
  { value: 'viewer', label: 'Solo lectura' },
];

/* Estado inicial del formulario de usuario */
const EMPTY_FORM = {
  username: '',
  password: '',
  role: 'operador',
  full_name: '',
  email: '',
  department: '',
  position: '',
};

export default function AdminPage() {
  /* Obtener funciones del contexto */
  const { getUsers, createUser, updateUser, deleteUser, showToast, user: currentUser } = useApp();
  /* Lista de usuarios */
  const [users, setUsers] = useState([]);
  /* Estado de carga */
  const [loading, setLoading] = useState(true);
  /* Modal de creación/edición */
  const [modalOpen, setModalOpen] = useState(false);
  /* Usuario en edición (null = crear nuevo) */
  const [editingUser, setEditingUser] = useState(null);
  /* Estado del formulario */
  const [form, setForm] = useState({ ...EMPTY_FORM });
  /* Estado de envío */
  const [saving, setSaving] = useState(false);
  /* Estado del modal de confirmación de eliminación */
  const [confirmModal, setConfirmModal] = useState({ open: false, user: null });

  /* Cargar la lista de usuarios al montar */
  useEffect(() => {
    loadUsers();
  }, []);

  /* Función para cargar usuarios desde el backend */
  const loadUsers = async () => {
    setLoading(true);
    const data = await getUsers();
    setUsers(data);
    setLoading(false);
  };

  /* Abrir modal para crear un nuevo usuario */
  const openCreate = () => {
    setEditingUser(null);
    setForm({ ...EMPTY_FORM });
    setModalOpen(true);
  };

  /* Abrir modal para editar un usuario existente */
  const openEdit = (u) => {
    setEditingUser(u);
    setForm({
      username: u.username,
      password: '',
      role: u.role,
      full_name: u.full_name || '',
      email: u.email || '',
      department: u.department || '',
      position: u.position || '',
    });
    setModalOpen(true);
  };

  /* Guardar usuario (crear o actualizar) */
  const handleSave = async () => {
    /* Validar campos obligatorios */
    if (!form.username.trim()) {
      showToast('El nombre de usuario es obligatorio', 'warning');
      return;
    }
    if (!editingUser && !form.password) {
      showToast('La contraseña es obligatoria para nuevos usuarios', 'warning');
      return;
    }
    setSaving(true);
    if (editingUser) {
      /* Preparar datos para actualización */
      const updateData = { ...form };
      /* Si no se cambió la contraseña, no enviarla */
      if (!updateData.password) {
        delete updateData.password;
      }
      const result = await updateUser(editingUser.id, updateData);
      if (result.success) {
        showToast('Usuario actualizado correctamente', 'success');
        setModalOpen(false);
        await loadUsers();
      } else {
        showToast(result.error || 'Error al actualizar usuario', 'error');
      }
    } else {
      /* Crear nuevo usuario */
      const result = await createUser(form);
      if (result.success) {
        showToast('Usuario creado correctamente', 'success');
        setModalOpen(false);
        await loadUsers();
      } else {
        showToast(result.error || 'Error al crear usuario', 'error');
      }
    }
    setSaving(false);
  };

  /* Alternar estado activo/inactivo de un usuario */
  const handleToggleActive = async (u) => {
    const newState = !u.is_active;
    const result = await updateUser(u.id, { is_active: newState });
    if (result.success) {
      showToast(newState ? 'Usuario activado' : 'Usuario desactivado', 'success');
      await loadUsers();
    } else {
      showToast(result.error || 'Error al cambiar estado', 'error');
    }
  };

  /* Abrir modal de confirmación para eliminar un usuario */
  const handleDelete = (u) => {
    if (u.id === currentUser.id) {
      showToast('No puedes eliminar tu propia cuenta', 'warning');
      return;
    }
    setConfirmModal({ open: true, user: u });
  };

  /* Ejecutar eliminación tras confirmar */
  const handleConfirmDelete = async () => {
    const u = confirmModal.user;
    setConfirmModal({ open: false, user: null });
    const result = await deleteUser(u.id);
    if (result.success) {
      showToast('Usuario eliminado', 'info');
      await loadUsers();
    } else {
      showToast(result.error || 'Error al eliminar usuario', 'error');
    }
  };

  /* Actualizar un campo del formulario */
  const updateField = (field, value) => {
    setForm(prev => ({ ...prev, [field]: value }));
  };

  return (
    <div>
      {/* Encabezado con título y botón de crear */}
      <div className="page-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
        <div>
          <h2>Administración de Usuarios</h2>
          <p>Gestiona los usuarios del sistema</p>
        </div>
        {/* Botón para crear nuevo usuario */}
        <button className="btn btn-primary" onClick={openCreate}>
          + Nuevo Usuario
        </button>
      </div>

      {/* Estado de carga */}
      {loading ? (
        <div style={{ textAlign: 'center', padding: '48px' }}>
          <div className="spinner" style={{ margin: '0 auto 16px' }} />
          <p style={{ color: 'var(--color-text-secondary)' }}>Cargando usuarios...</p>
        </div>
      ) : users.length === 0 ? (
        /* Estado vacío */
        <div className="empty-state">
          <div className="empty-state-icon">👥</div>
          <h3>Sin usuarios registrados</h3>
          <p>Crea el primer usuario para comenzar.</p>
        </div>
      ) : (
        /* Tabla de usuarios */
        <div className="card" style={{ overflow: 'hidden' }}>
          <div className="history-table-wrapper">
            <table className="history-table">
              <thead>
                <tr>
                  <th>Usuario</th>
                  <th>Nombre completo</th>
                  <th>Email</th>
                  <th>Departamento</th>
                  <th>Cargo</th>
                  <th>Rol</th>
                  <th>Estado</th>
                  <th>Acciones</th>
                </tr>
              </thead>
              <tbody>
                {users.map((u) => (
                  <tr key={u.id} style={{ cursor: 'default' }}>
                    {/* Usuario */}
                    <td>
                      <span style={{ fontWeight: 600 }}>{u.username}</span>
                      {u.id === currentUser.id && (
                        <span style={{ fontSize: '11px', color: 'var(--color-primary)', marginLeft: '6px' }}>(tú)</span>
                      )}
                    </td>
                    {/* Nombre completo */}
                    <td>{u.full_name || '—'}</td>
                    {/* Email */}
                    <td>
                      <span style={{ fontSize: '13px', color: 'var(--color-text-secondary)' }}>
                        {u.email || '—'}
                      </span>
                    </td>
                    {/* Departamento */}
                    <td>{u.department || '—'}</td>
                    {/* Cargo */}
                    <td>{u.position || '—'}</td>
                    {/* Rol */}
                    <td>
                      <span className={`pill ${u.role === 'admin' ? 'pill-info' : 'pill-success'}`}>
                        {u.role}
                      </span>
                    </td>
                    {/* Estado */}
                    <td>
                      <span className={`pill ${u.is_active ? 'pill-success' : 'pill-error'}`}>
                        {u.is_active ? 'Activo' : 'Inactivo'}
                      </span>
                    </td>
                    {/* Acciones */}
                    <td>
                      <div style={{ display: 'flex', gap: '4px' }}>
                        {/* Botón editar */}
                        <button className="btn btn-ghost btn-sm" onClick={() => openEdit(u)}>
                          Editar
                        </button>
                        {/* Botón activar/desactivar */}
                        <button
                          className="btn btn-ghost btn-sm"
                          style={{ color: u.is_active ? 'var(--color-warning)' : 'var(--color-success)' }}
                          onClick={() => handleToggleActive(u)}
                          disabled={u.id === currentUser.id}
                        >
                          {u.is_active ? 'Desactivar' : 'Activar'}
                        </button>
                        {/* Botón eliminar */}
                        <button
                          className="btn btn-ghost btn-sm"
                          style={{ color: 'var(--color-error)' }}
                          onClick={() => handleDelete(u)}
                          disabled={u.id === currentUser.id}
                        >
                          Eliminar
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Modal de confirmación de eliminación */}
      <ConfirmModal
        isOpen={confirmModal.open}
        title="Eliminar usuario"
        message={confirmModal.user ? `¿Eliminar al usuario "${confirmModal.user.username}"? Esta acción no se puede deshacer.` : ''}
        confirmLabel="Eliminar"
        onConfirm={handleConfirmDelete}
        onCancel={() => setConfirmModal({ open: false, user: null })}
      />

      {/* Modal de creación/edición de usuario */}
      {modalOpen && (
        <div className="modal-overlay" onClick={() => setModalOpen(false)}>
          {/* Contenido del modal */}
          <div className="modal-content" onClick={(e) => e.stopPropagation()}>
            {/* Header del modal */}
            <div className="modal-header">
              <h3>{editingUser ? 'Editar Usuario' : 'Nuevo Usuario'}</h3>
              <button className="modal-close" onClick={() => setModalOpen(false)}>✕</button>
            </div>
            {/* Cuerpo del modal con el formulario */}
            <div className="modal-body">
              {/* Fila: Username y Rol */}
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px' }}>
                <div className="form-group">
                  <label className="form-label">Usuario *</label>
                  <input
                    type="text"
                    className="form-input"
                    value={form.username}
                    onChange={(e) => updateField('username', e.target.value)}
                    placeholder="Nombre de usuario"
                    disabled={saving}
                  />
                </div>
                <div className="form-group">
                  <label className="form-label">Rol</label>
                  <select
                    className="form-input"
                    value={form.role}
                    onChange={(e) => updateField('role', e.target.value)}
                    disabled={saving}
                  >
                    {ROLES.map(r => (
                      <option key={r.value} value={r.value}>{r.label}</option>
                    ))}
                  </select>
                </div>
              </div>
              {/* Campo: Contraseña */}
              <div className="form-group">
                <label className="form-label">
                  {editingUser ? 'Nueva Contraseña (dejar vacío para mantener)' : 'Contraseña *'}
                </label>
                <input
                  type="password"
                  className="form-input"
                  value={form.password}
                  onChange={(e) => updateField('password', e.target.value)}
                  placeholder={editingUser ? 'Sin cambios' : 'Contraseña'}
                  disabled={saving}
                />
              </div>
              {/* Campo: Nombre completo */}
              <div className="form-group">
                <label className="form-label">Nombre Completo</label>
                <input
                  type="text"
                  className="form-input"
                  value={form.full_name}
                  onChange={(e) => updateField('full_name', e.target.value)}
                  placeholder="Nombre y apellidos"
                  disabled={saving}
                />
              </div>
              {/* Campo: Email */}
              <div className="form-group">
                <label className="form-label">Email</label>
                <input
                  type="email"
                  className="form-input"
                  value={form.email}
                  onChange={(e) => updateField('email', e.target.value)}
                  placeholder="correo@ejemplo.com"
                  disabled={saving}
                />
              </div>
              {/* Fila: Departamento y Cargo */}
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px' }}>
                <div className="form-group">
                  <label className="form-label">Departamento</label>
                  <input
                    type="text"
                    className="form-input"
                    value={form.department}
                    onChange={(e) => updateField('department', e.target.value)}
                    placeholder="Ej: QHSE, Operaciones"
                    disabled={saving}
                  />
                </div>
                <div className="form-group">
                  <label className="form-label">Cargo</label>
                  <input
                    type="text"
                    className="form-input"
                    value={form.position}
                    onChange={(e) => updateField('position', e.target.value)}
                    placeholder="Ej: Supervisor, Analista"
                    disabled={saving}
                  />
                </div>
              </div>
            </div>
            {/* Footer del modal con botones de acción */}
            <div className="modal-footer">
              <button className="btn btn-secondary" onClick={() => setModalOpen(false)} disabled={saving}>
                Cancelar
              </button>
              <button className="btn btn-primary" onClick={handleSave} disabled={saving}>
                {saving ? 'Guardando...' : editingUser ? 'Guardar Cambios' : 'Crear Usuario'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
