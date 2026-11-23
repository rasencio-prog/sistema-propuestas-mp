import { useEffect, useState } from "react";
import { apiClient } from "../lib/apiClient";

type ServiceLine = {
  id: string;
  name: string;
  description: string | null;
  positive_keywords: string[];
  exclusion_keywords: string[];
  category_codes: string[];
  is_active: boolean;
};

export default function Configuracion() {
  const [lines, setLines] = useState<ServiceLine[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [savingId, setSavingId] = useState<string | null>(null);

  useEffect(() => {
    apiClient
      .get<ServiceLine[]>("/api/config/service-lines")
      .then(setLines)
      .catch((err) => setError(err instanceof Error ? err.message : "Error al cargar."))
      .finally(() => setLoading(false));
  }, []);

  async function saveKeywords(line: ServiceLine, rawKeywords: string) {
    const positive_keywords = rawKeywords
      .split(",")
      .map((word) => word.trim())
      .filter(Boolean);
    setSavingId(line.id);
    try {
      const updated = await apiClient.patch<ServiceLine>(`/api/config/service-lines/${line.id}`, {
        positive_keywords,
      });
      setLines((prev) => prev.map((l) => (l.id === updated.id ? updated : l)));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Error al guardar.");
    } finally {
      setSavingId(null);
    }
  }

  async function toggleActive(line: ServiceLine) {
    setSavingId(line.id);
    try {
      const updated = await apiClient.patch<ServiceLine>(`/api/config/service-lines/${line.id}`, {
        is_active: !line.is_active,
      });
      setLines((prev) => prev.map((l) => (l.id === updated.id ? updated : l)));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Error al guardar.");
    } finally {
      setSavingId(null);
    }
  }

  if (loading) return <p>Cargando lineas de servicio...</p>;

  return (
    <main style={{ maxWidth: 800, margin: "2rem auto", fontFamily: "sans-serif" }}>
      <h1>Configuracion · Lineas de servicio</h1>
      {error && <p style={{ color: "crimson" }}>{error}</p>}
      {lines.map((line) => (
        <section key={line.id} style={{ border: "1px solid #ccc", padding: 16, marginBottom: 12 }}>
          <h2>
            {line.name} {!line.is_active && <small>(inactiva)</small>}
          </h2>
          <p>{line.description}</p>
          <label>
            Palabras clave positivas (separadas por coma)
            <textarea
              defaultValue={line.positive_keywords.join(", ")}
              onBlur={(e) => saveKeywords(line, e.target.value)}
              style={{ display: "block", width: "100%", minHeight: 60 }}
            />
          </label>
          <button
            type="button"
            onClick={() => toggleActive(line)}
            disabled={savingId === line.id}
          >
            {line.is_active ? "Desactivar" : "Activar"}
          </button>
        </section>
      ))}
    </main>
  );
}
