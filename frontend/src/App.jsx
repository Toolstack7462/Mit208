import { Navigate, Route, Routes } from "react-router-dom";
import { useAuth } from "./context/AuthContext";
import Login from "./pages/Login";
import Dashboard from "./pages/Dashboard";
import Inbox from "./pages/Inbox";
import StaffPortal from "./pages/StaffPortal";
import ReleaseRequests from "./pages/ReleaseRequests";
import AuditLogs from "./pages/AuditLogs";

function Protected({ children, roles }) {
  const { user } = useAuth();
  if (!user) return <Navigate to="/login" replace />;
  if (roles && !roles.includes(user.role)) return <Navigate to="/dashboard" replace />;
  return children;
}

export default function App() {
  const { user } = useAuth();
  return (
    <Routes>
      <Route path="/login" element={user ? <Navigate to="/dashboard" replace /> : <Login />} />
      <Route path="/dashboard" element={<Protected><Dashboard /></Protected>} />
      <Route
        path="/inbox"
        element={<Protected roles={["analyst", "admin"]}><Inbox /></Protected>}
      />
      <Route
        path="/audit"
        element={<Protected roles={["analyst", "admin"]}><AuditLogs /></Protected>}
      />
      <Route
        path="/staff"
        element={<Protected roles={["staff", "admin"]}><StaffPortal /></Protected>}
      />
      <Route path="/release-requests" element={<Protected><ReleaseRequests /></Protected>} />
      <Route path="*" element={<Navigate to={user ? "/dashboard" : "/login"} replace />} />
    </Routes>
  );
}
