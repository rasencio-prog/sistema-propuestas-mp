import { useEffect, useState } from "react";
import { apiClient } from "../lib/apiClient";

type RadarRun = {
  id: string;
  radar_date: string;
  trigger: string;
  status: string;
  requests_used: number;
  listed_count: number;
  new_count: number;
  updated_count: number;
  detailed_count: number;
  errors: Record<string, unknown>[];
  started_at: string;
  finished_at: string | null;
};

const STATUS_LABEL: Record<string, string> = {
  running: "En curso",
  succeeded: "Completada",
  partial: "Parcial",
  failed: "Fallida",
};

export default function LotesYEjecuciones() {
  const [runs, setRuns] = useState<RadarRun[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [triggering, setTriggering] = useState(false);

  function loadRuns() {
    return apiClient
      .get<RadarRun[]>("/api/radar/runs")
      .then(setRuns)
      .catch((err) => setError(err instanceof Error ? err.message : "Error al cargar."));
  }

  useEffect(() => {
    loadRuns().finally(() => setLoading(false));
  }, []);

  async function handleEjecutarAhora() {
    setError(null);
    setTriggering(true);
    try {
      await apiClient.post("/api/radar/run");
      await loadRuns();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Error al encolar la corrida.");
    } finally {
      setTriggering(false);
    }
  }

  return (
    <main style={{ maxWidth: 900, margin: "2rem auto", fontFamily: "sans-serif" }}>
      <h1>Lotes y ejecuciones</h1>
      <button type="button" onClick={handleEjecutarAhora} disabled={triggering}>
        {triggering ? "Encolando..." : "Ejecutar ahora"}
      </button>
      {error && <p style={{ color: "crimson" }}>{error}</p>}
      {loading ? (
        <p>Cargando corridas...</p>
      ) : (
        <table style={{ width: "100%", marginTop: 16, borderCollapse: "collapse" }}>
          <thead>
            <tr>
              <th style={{ textAlign: "left" }}>Fecha radar</th>
              <th style={{ textAlign: "left" }}>Origen</th>
              <th style={{ textAlign: "left" }}>Estado</th>
              <th style={{ textAlign: "right" }}>Listadas</th>
              <th style={{ textAlign: "right" }}>Nuevas</th>
              <th style={{ textAlign: "right" }}>Actualizadas</th>
              <th style={{ textAlign: "right" }}>Detalladas</th>
              <th style={{ textAlign: "right" }}>Cuota usada</th>
              <th style={{ textAlign: "right" }}>Errores</th>
            </tr>
          </thead>
          <tbody>
            {runs.map((run) => (
              <tr key={run.id} style={{ borderTop: "1px solid #ddd" }}>
                <td>{run.radar_date}</td>
                <td>{run.trigger === "manual" ? "Manual" : "Programada"}</td>
                <td>{STATUS_LABEL[run.status] ?? run.status}</td>
                <td style={{ textAlign: "right" }}>{run.listed_count}</td>
                <td style={{ textAlign: "right" }}>{run.new_count}</td>
                <td style={{ textAlign: "right" }}>{run.updated_count}</td>
                <td style={{ textAlign: "right" }}>{run.detailed_count}</td>
                <td style={{ textAlign: "right" }}>{run.requests_used}</td>
                <td style={{ textAlign: "right" }}>{run.errors.length}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </main>
  );
}
