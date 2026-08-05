export default function FilePreview({ url }) {
  if (!url) return <div className="empty-state">Файл не прикреплён</div>;
  const isPdf = /\.pdf(\?|$)/i.test(url);
  const isImage = /\.(png|jpe?g|gif|webp)(\?|$)/i.test(url);

  return (
    <div>
      {isPdf && (
        <iframe
          src={url}
          title="Просмотр файла"
          style={{ width: "100%", height: 480, border: "1px solid var(--border)", borderRadius: 8 }}
        />
      )}
      {isImage && (
        <img src={url} alt="Файл" style={{ maxWidth: "100%", borderRadius: 8, border: "1px solid var(--border)" }} />
      )}
      {!isPdf && !isImage && (
        <div className="empty-state">Предпросмотр недоступен для этого типа файла</div>
      )}
      <div style={{ marginTop: 10 }}>
        <a href={url} target="_blank" rel="noreferrer" className="btn btn-ghost btn-xs">Открыть в новой вкладке</a>
      </div>
    </div>
  );
}
