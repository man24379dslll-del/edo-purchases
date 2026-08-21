import { useState } from "react";
import { api } from "../api";
import { useToast } from "./Toast";

const ACCEPT = ".pdf,.doc,.docx,.xls,.xlsx,.ppt,.pptx,.jpg,.jpeg,.png,.gif,.webp,.txt,.csv,.zip";

/**
 * Загрузка файла на сервер (хранится физически, не просто ссылка).
 * value — текущий URL (или пусто), onChange(url) вызывается после успешной загрузки/очистки.
 */
export default function FileUpload({ value, onChange }) {
  const toast = useToast();
  const [busy, setBusy] = useState(false);
  const [name, setName] = useState("");

  async function handleFile(e) {
    const file = e.target.files[0];
    e.target.value = "";
    if (!file) return;
    if (file.size > 20 * 1024 * 1024) {
      toast("Файл больше 20 МБ — уменьшите размер и попробуйте снова", true);
      return;
    }
    setBusy(true);
    try {
      const res = await api.uploadFile(file);
      setName(res.originalName);
      onChange(res.url);
      toast("✓ Файл загружен");
    } catch (err) {
      toast(err.message, true);
    } finally {
      setBusy(false);
    }
  }

  if (value) {
    return (
      <div style={{ display: "flex", alignItems: "center", gap: 10, fontSize: 13 }}>
        <span>📎 {name || "Файл прикреплён"}</span>
        <a href={value} target="_blank" rel="noreferrer" className="btn btn-ghost btn-xs">Открыть</a>
        <button type="button" className="btn btn-ghost btn-xs" onClick={() => { onChange(""); setName(""); }}>
          Заменить
        </button>
      </div>
    );
  }

  return (
    <label className="btn btn-ghost btn-xs" style={{ display: "inline-block", cursor: busy ? "default" : "pointer" }}>
      {busy ? "Загрузка..." : "📎 Прикрепить файл"}
      <input type="file" accept={ACCEPT} onChange={handleFile} disabled={busy} style={{ display: "none" }} />
    </label>
  );
}
