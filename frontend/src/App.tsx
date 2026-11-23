import type { ReactNode } from "react";
import { Navigate, Route, Routes } from "react-router-dom";
import { useSession } from "./lib/useSession";
import Login from "./pages/Login";
import Configuracion from "./pages/Configuracion";

function RequireSession({ children }: { children: ReactNode }) {
  const { session, loading } = useSession();
  if (loading) return <p>Cargando...</p>;
  if (!session) return <Navigate to="/login" replace />;
  return <>{children}</>;
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
      <Route path="*" element={<Navigate to="/configuracion" replace />} />
    </Routes>
  );
}
