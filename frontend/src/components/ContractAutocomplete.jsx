import { useEffect, useRef, useState } from "react";
import { api } from "../api";

/**
 * Поиск существующего договора по номеру/предмету/контрагенту — для формы
 * добавления доп. соглашения/приложения к уже созданному договору.
 */
export default function ContractAutocomplete({ value, onSelect }) {
  const [query, setQuery] = useState(value?.subject ? `${value.id} · ${value.subject}` : "");
  const [results, setResults] = useState([]);
  const [open, setOpen] = useState(false);
  const boxRef = useRef(null);
  const debounceRef = useRef(null);

  useEffect(() => {
    function onClickOutside(e) {
      if (boxRef.current && !boxRef.current.contains(e.target)) setOpen(false);
    }
    document.addEventListener("mousedown", onClickOutside);
    return () => document.removeEventListener("mousedown", onClickOutside);
  }, []);

  function handleInput(v) {
    setQuery(v);
    onSelect(null);
    clearTimeout(debounceRef.current);
    if (v.trim().length < 2) { setResults([]); return; }
    debounceRef.current = setTimeout(async () => {
      try {
        const rows = await api.contracts({ q: v.trim() });
        setResults(rows.slice(0, 15));
        setOpen(true);
      } catch (_) {}
    }, 250);
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
        onFocus={() => results.length && setOpen(true)}
        placeholder="Начните вводить номер, контрагента или предмет договора..."
        autoComplete="off"
      />
      {open && results.length > 0 && (
        <div style={{
          position: "absolute", top: "calc(100% + 4px)", left: 0, right: 0, zIndex: 20,
          background: "var(--surface)", border: "1px solid var(--border-s)", borderRadius: 8,
          boxShadow: "var(--shadow-md)", maxHeight: 260, overflowY: "auto",
        }}>
          {results.map((c) => (
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
