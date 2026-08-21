import { useEffect, useRef, useState } from "react";
import { api } from "../api";

/**
 * Выбор существующего договора — для формы добавления доп. соглашения/приложения.
 * При клике сразу показывает список последних договоров (без необходимости печатать),
 * при вводе текста — фильтрует по номеру/предмету/контрагенту.
 */
export default function ContractAutocomplete({ value, onSelect }) {
  const [query, setQuery] = useState(value?.subject ? `${value.id} · ${value.subject}` : "");
  const [results, setResults] = useState([]);
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const boxRef = useRef(null);
  const debounceRef = useRef(null);

  useEffect(() => {
    function onClickOutside(e) {
      if (boxRef.current && !boxRef.current.contains(e.target)) setOpen(false);
    }
    document.addEventListener("mousedown", onClickOutside);
    return () => document.removeEventListener("mousedown", onClickOutside);
  }, []);

  async function search(q) {
    setLoading(true);
    try {
      const rows = await api.contracts(q ? { q } : {});
      setResults(rows.slice(0, 20));
      setOpen(true);
    } catch (_) {
    } finally {
      setLoading(false);
    }
  }

  function handleInput(v) {
    setQuery(v);
    onSelect(null);
    clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => search(v.trim()), 250);
  }

  function handleFocus() {
    // Клик по пустому полю сразу показывает список последних договоров —
    // не нужно ничего печатать, чтобы увидеть, из чего выбирать.
    if (!query.trim()) search("");
    else if (results.length) setOpen(true);
  }

  function select(c) {
    setQuery(`${c.id} · ${c.subject}`);
    onSelect(c);
    setOpen(false);
  }

  return (
    <div ref={boxRef} style={{ position: "relative" }}>
      <input
        value={query}
        onChange={(e) => handleInput(e.target.value)}
        onFocus={handleFocus}
        placeholder="Нажмите, чтобы выбрать договор, или начните вводить..."
        autoComplete="off"
      />
      {open && (
        <div style={{
          position: "absolute", top: "calc(100% + 4px)", left: 0, right: 0, zIndex: 20,
          background: "var(--surface)", border: "1px solid var(--border-s)", borderRadius: 8,
          boxShadow: "var(--shadow-md)", maxHeight: 260, overflowY: "auto",
        }}>
          {loading && <div style={{ padding: "10px 12px", fontSize: 12, color: "var(--text-3)" }}>Загрузка...</div>}
          {!loading && results.length === 0 && (
            <div style={{ padding: "10px 12px", fontSize: 12, color: "var(--text-3)" }}>Ничего не найдено</div>
          )}
          {!loading && results.map((c) => (
            <div
              key={c.id}
              onClick={() => select(c)}
              style={{ padding: "8px 12px", cursor: "pointer", fontSize: 13, borderBottom: "1px solid var(--border)" }}
              onMouseDown={(e) => e.preventDefault()}
            >
              <div style={{ fontWeight: 600 }}>{c.id} · {c.contractor_name}</div>
              <div style={{ fontSize: 11, color: "var(--text-3)" }}>{c.subject}</div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
