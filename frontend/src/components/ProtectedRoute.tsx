import type { ReactNode } from "react";
import { Navigate, useLocation } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import type { Role } from "../api/types";
import { Loading } from "./States";

/** Convenience only: it hides pages the user can't use. The BACKEND is what actually
 *  blocks access, so changing this code in the browser gains an attacker nothing. */
export function ProtectedRoute({ role, children }: { role?: Role; children: ReactNode }) {
  const { user, loading } = useAuth();
  const location = useLocation();
  if (loading) return <Loading label="Checking your session" />;
  if (!user) return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  if (role && user.role !== role) return <Navigate to={user.role === "staff" ? "/staff" : "/"} replace />;
  return <>{children}</>;
}
