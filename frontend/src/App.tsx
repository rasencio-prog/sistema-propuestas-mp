import type { ReactNode } from "react";
import { Navigate, NavLink, Route, Routes } from "react-router-dom";
import { useSession } from "./lib/useSession";
import Login from "./pages/Login";
import Configuracion from "./pages/Configuracion";
import LotesYEjecuciones from "./pages/LotesYEjecuciones";

function RequireSession({ children }: { children: ReactNode }) {
  const { session, loading } = useSession();
  if (loading) return <p>Cargando...</p>;
  if (!session) return <Navigate to="/login" replace />;
  return (
    <>
      <nav style={{ display: "flex", gap: 16, padding: "1rem 2rem", borderBottom: "1px solid #ddd" }}>
        <NavLink to="/configuracion">Configuracion</NavLink>
        <NavLink to="/lotes-y-ejecuciones">Lotes y ejecuciones</NavLink>
      </nav>
      {children}
    </>
  );
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route
        path="/configuracion"
        element={
          <RequireSession>
            <Configuracion />
          </RequireSession>
        }
      />
      <Route
        path="/lotes-y-ejecuciones"
        element={
          <RequireSession>
            <LotesYEjecuciones />
          </RequireSession>
        }
      />
      <Route path="*" element={<Navigate to="/configuracion" replace />} />
    </Routes>
  );
}
