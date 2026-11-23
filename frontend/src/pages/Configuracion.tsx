import { useEffect, useState, type FormEvent } from "react";
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

type Credential = {
  id: string;
  provider: string;
  holder_name: string | null;
  ticket_masked: string;
  daily_limit: number;
  valid_until: string | null;
  is_active: boolean;
  updated_at: string;
};

function CredencialMercadoPublico() {
  const [credential, setCredential] = useState<Credential | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [ticket, setTicket] = useState("");
  const [holderName, setHolderName] = useState("");
  const [dailyLimit, setDailyLimit] = useState(8000);

  function load() {
    return apiClient
      .get<Credential | null>("/api/config/mp-credential")
      .then((current) => {
        setCredential(current);
        if (current) {
          setHolderName(current.holder_name ?? "");
          setDailyLimit(current.daily_limit);
        }
      })
      .catch((err) => setError(err instanceof Error ? err.message : "Error al cargar."));
  }

  useEffect(() => {
    load().finally(() => setLoading(false));
  }, []);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setSaving(true);
    try {
      const updated = await apiClient.post<Credential>("/api/config/mp-credential", {
        ticket,
        holder_name: holderName || null,
        daily_limit: dailyLimit,
      });
      setCredential(updated);
      setTicket("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Error al guardar el ticket.");
    } finally {
      setSaving(false);
    }
  }

  if (loading) return <p>Cargando credencial de Mercado Publico...</p>;

  return (
    <section style={{ border: "1px solid #ccc", padding: 16, marginBottom: 24 }}>
      <h2>Credencial de Mercado Publico</h2>
      {error && <p style={{ color: "crimson" }}>{error}</p>}
      {credential ? (
        <p>
          Ticket actual: <code>{credential.ticket_masked}</code>
          {credential.holder_name && <> · titular: {credential.holder_name}</>}
          {" · "}limite diario: {credential.daily_limit}
        </p>
      ) : (
        <p>No hay ningun ticket configurado todavia (el radar no puede correr sin uno).</p>
      )}
      <form onSubmit={handleSubmit}>
        <label>
          Nuevo ticket (reemplaza el actual)
          <input
            type="password"
            value={ticket}
            onChange={(e) => setTicket(e.target.value)}
            required
            style={{ display: "block", width: "100%" }}
          />
        </label>
        <label>
          Titular
          <input
            type="text"
            value={holderName}
            onChange={(e) => setHolderName(e.target.value)}
            style={{ display: "block", width: "100%" }}
          />
        </label>
        <label>
          Limite diario de solicitudes
          <input
            type="number"
            min={1}
            max={10000}
            value={dailyLimit}
            onChange={(e) => setDailyLimit(Number(e.target.value))}
            style={{ display: "block", width: 160 }}
          />
        </label>
        <button type="submit" disabled={saving} style={{ marginTop: 8 }}>
          {saving ? "Guardando..." : "Guardar ticket"}
        </button>
      </form>
    </section>
  );
}

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
      <h1>Configuracion</h1>
      <CredencialMercadoPublico />
      <h2>Lineas de servicio</h2>
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
