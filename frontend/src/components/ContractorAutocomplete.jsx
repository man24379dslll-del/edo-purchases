import { useEffect, useRef, useState } from "react";
import { api } from "../api";

/**
 * Текстовое поле с подсказками существующих контрагентов (поиск по названию/ИНН).
 * onChange({ name, inn }) вызывается и при свободном вводе, и при выборе из списка.
 */
export default function ContractorAutocomplete({ value, inn, onChange }) {
  const [query, setQuery] = useState(value || "");
  const [results, setResults] = useState([]);
  const [open, setOpen] = useState(false);
  const boxRef = useRef(null);
  const debounceRef = useRef(null);

  useEffect(() => setQuery(value || ""), [value]);

  useEffect(() => {
    function onClickOutside(e) {
      if (boxRef.current && !boxRef.current.contains(e.target)) setOpen(false);
    }
    document.addEventListener("mousedown", onClickOutside);
    return () => document.removeEventListener("mousedown", onClickOutside);
  }, []);

  function handleInput(v) {
    setQuery(v);
    onChange({ name: v, inn });
    clearTimeout(debounceRef.current);
    if (v.trim().length < 2) { setResults([]); return; }
    debounceRef.current = setTimeout(async () => {
      try {
        const rows = await api.contractors(v.trim());
        setResults(rows);
        setOpen(true);
      } catch (_) {}
    }, 250);
  }

  function select(c) {
    setQuery(c.name);
    onChange({ name: c.name, inn: c.inn || "" });
    setOpen(false);
  }

  return (
    <div ref={boxRef} style={{ position: "relative" }}>
      <input
        value={query}
        onChange={(e) => handleInput(e.target.value)}
        onFocus={() => results.length && setOpen(true)}
        placeholder="Начните вводить название или ИНН..."
        autoComplete="off"
      />
      {open && results.length > 0 && (
        <div style={{
          position: "absolute", top: "calc(100% + 4px)", left: 0, right: 0, zIndex: 20,
          background: "var(--surface)", border: "1px solid var(--border-s)", borderRadius: 8,
          boxShadow: "var(--shadow-md)", maxHeight: 220, overflowY: "auto",
        }}>
          {results.map((c) => (
            <div
              key={c.id}
              onClick={() => select(c)}
              style={{ padding: "8px 12px", cursor: "pointer", fontSize: 13, borderBottom: "1px solid var(--border)" }}
              onMouseDown={(e) => e.preventDefault()}
            >
              <div style={{ fontWeight: 600 }}>{c.name}</div>
              {c.inn && <div style={{ fontSize: 11, color: "var(--text-3)" }}>ИНН {c.inn}</div>}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
