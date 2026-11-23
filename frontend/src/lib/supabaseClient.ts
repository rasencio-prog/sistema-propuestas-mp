// Cliente de Supabase, usado solo para el login (obtener el JWT de Supabase Auth).
// El resto de la app llama siempre a la API propia (ver apiClient.ts). ADR-0013.
import { createClient } from "@supabase/supabase-js";

const supabaseUrl = import.meta.env.VITE_SUPABASE_URL as string | undefined;
const supabaseAnonKey = import.meta.env.VITE_SUPABASE_ANON_KEY as string | undefined;

if (!supabaseUrl || !supabaseAnonKey) {
  throw new Error(
    "Faltan VITE_SUPABASE_URL o VITE_SUPABASE_ANON_KEY. Copia frontend/.env.local (ver README).",
  );
}

export const supabase = createClient(supabaseUrl, supabaseAnonKey);
