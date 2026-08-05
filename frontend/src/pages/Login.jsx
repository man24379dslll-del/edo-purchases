import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";

export default function Login() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(e) {
    e.preventDefault();
    setError("");
    setBusy(true);
    try {
      await login(email, password);
      navigate("/");
    } catch (err) {
      setError(err.message || "Не удалось войти");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="login-shell">
      <form className="login-card" onSubmit={submit}>
        <div className="login-logo">
          <div className="sb-logo-icon">📋</div>
          <div>
            <div style={{ fontWeight: 700, fontSize: 15 }}>ЭДО Закупок</div>
            <div style={{ fontSize: 11, color: "var(--text-3)" }}>Вход в систему</div>
          </div>
        </div>
        {error && <div className="login-error">{error}</div>}
        <div className="field">
          <label>Email</label>
          <input type="email" required value={email} onChange={(e) => setEmail(e.target.value)} placeholder="you@company.com" />
        </div>
        <div className="field">
          <label>Пароль</label>
          <input type="password" required value={password} onChange={(e) => setPassword(e.target.value)} placeholder="••••••••" />
        </div>
        <button className="btn btn-primary" type="submit" style={{ width: "100%" }} disabled={busy}>
          {busy ? "Входим..." : "Войти"}
        </button>
      </form>
    </div>
  );
}
