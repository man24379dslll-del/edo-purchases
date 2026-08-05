import { useEffect, useState } from "react";
import { api } from "../api";
import { useToast } from "../components/Toast";

const ALL_ROLES = ['Админ', 'Инициатор', 'Закупщик', 'Маркетинг', 'Юрист',
  'Фин. директор', 'Директор', 'Бухгалтер', 'Склад'];

export default function Admin() {
  const toast = useToast();
  const [users, setUsers] = useState([]);
  const [entities, setEntities] = useState([]);
  const [newUser, setNewUser] = useState({ email: "", fio: "", role: "Инициатор" });
  const [newEntity, setNewEntity] = useState({ name: "", inn: "", address: "" });
  const [roleEdits, setRoleEdits] = useState({});

  function load() {
    api.adminUsers().then(setUsers).catch(() => setUsers([]));
    api.adminLegalEntities().then(setEntities).catch(() => setEntities([]));
  }
  useEffect(load, []);

  async function addUser() {
    if (!newUser.email || !newUser.fio) { toast("Заполните email и ФИО", true); return; }
    try {
      const res = await api.addUser(newUser);
      toast(res.temp_password ? `✓ Добавлен. Временный пароль: ${res.temp_password}` : "✓ Пользователь добавлен");
      setNewUser({ email: "", fio: "", role: "Инициатор" });
      load();
    } catch (e) { toast(e.message, true); }
  }

  async function saveRole(u) {
    const newRole = roleEdits[u.email] || u.role;
    if (newRole === u.role) { toast("Роль не изменилась"); return; }
    if (!confirm(`Изменить роль ${u.email} с «${u.role}» на «${newRole}»?`)) return;
    try {
      await api.updateUserRole(u.email, newRole, u.role);
      toast("✓ Роль изменена");
      load();
    } catch (e) { toast(e.message, true); }
  }

  async function removeUser(u) {
    if (!confirm(`Удалить пользователя ${u.email}?`)) return;
    try { await api.removeUser(u.email, u.role); toast("✓ Пользователь удалён"); load(); }
    catch (e) { toast(e.message, true); }
  }

  async function addEntity() {
    if (!newEntity.name) { toast("Укажите название юрлица", true); return; }
    try {
      await api.addLegalEntity(newEntity);
      toast("✓ Юрлицо добавлено");
      setNewEntity({ name: "", inn: "", address: "" });
      load();
    } catch (e) { toast(e.message, true); }
  }

  async function removeEntity(id) {
    if (!confirm(`Удалить юрлицо ${id}?`)) return;
    try { await api.removeLegalEntity(id); toast("✓ Юрлицо удалено"); load(); }
    catch (e) { toast(e.message, true); }
  }

  return (
    <div>
      <div className="card">
        <div className="card-header"><div className="card-title">Пользователи</div></div>
        <div className="card-body">
          <div className="grid-2" style={{ gridTemplateColumns: "1fr 1fr 1fr auto", alignItems: "end", gap: 10 }}>
            <div className="field" style={{ margin: 0 }}>
              <label>Email</label>
              <input value={newUser.email} onChange={(e) => setNewUser({ ...newUser, email: e.target.value })} />
            </div>
            <div className="field" style={{ margin: 0 }}>
              <label>ФИО</label>
              <input value={newUser.fio} onChange={(e) => setNewUser({ ...newUser, fio: e.target.value })} />
            </div>
            <div className="field" style={{ margin: 0 }}>
              <label>Роль</label>
              <select value={newUser.role} onChange={(e) => setNewUser({ ...newUser, role: e.target.value })}>
                {ALL_ROLES.map((r) => <option key={r} value={r}>{r}</option>)}
              </select>
            </div>
            <button className="btn btn-primary" onClick={addUser}>+ Добавить</button>
          </div>
        </div>
        <table>
          <thead><tr><th>Email</th><th>ФИО</th><th>Роль</th><th>Изменить роль</th><th></th></tr></thead>
          <tbody>
            {users.map((u) => (
              <tr key={u.email} style={{ cursor: "default" }}>
                <td>{u.email}</td>
                <td>{u.fio}</td>
                <td><span className="badge b-p">{u.role}</span></td>
                <td style={{ whiteSpace: "nowrap" }}>
                  <select style={{ width: 140, marginRight: 6 }} value={roleEdits[u.email] || u.role}
                    onChange={(e) => setRoleEdits({ ...roleEdits, [u.email]: e.target.value })}>
                    {ALL_ROLES.map((r) => <option key={r} value={r}>{r}</option>)}
                  </select>
                  <button className="btn btn-primary btn-xs" onClick={() => saveRole(u)}>Сохранить</button>
                </td>
                <td><button className="btn btn-danger btn-xs" onClick={() => removeUser(u)}>Удалить</button></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="card">
        <div className="card-header"><div className="card-title">Юрлица</div></div>
        <div className="card-body">
          <div className="grid-2" style={{ gridTemplateColumns: "1fr 1fr 1fr auto", alignItems: "end", gap: 10 }}>
            <div className="field" style={{ margin: 0 }}>
              <label>Название</label>
              <input value={newEntity.name} onChange={(e) => setNewEntity({ ...newEntity, name: e.target.value })} />
            </div>
            <div className="field" style={{ margin: 0 }}>
              <label>ИНН</label>
              <input value={newEntity.inn} onChange={(e) => setNewEntity({ ...newEntity, inn: e.target.value })} />
            </div>
            <div className="field" style={{ margin: 0 }}>
              <label>Адрес</label>
              <input value={newEntity.address} onChange={(e) => setNewEntity({ ...newEntity, address: e.target.value })} />
            </div>
            <button className="btn btn-primary" onClick={addEntity}>+ Добавить</button>
          </div>
        </div>
        <table>
          <thead><tr><th>Id</th><th>Название</th><th>ИНН</th><th>Адрес</th><th></th></tr></thead>
          <tbody>
            {entities.map((le) => (
              <tr key={le.id} style={{ cursor: "default" }}>
                <td>{le.id}</td><td>{le.name}</td><td>{le.inn || "—"}</td><td>{le.address || "—"}</td>
                <td><button className="btn btn-danger btn-xs" onClick={() => removeEntity(le.id)}>Удалить</button></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
