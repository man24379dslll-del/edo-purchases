import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { AuthProvider, useAuth } from "./context/AuthContext";
import { ToastProvider } from "./components/Toast";
import Layout from "./components/Layout";
import Login from "./pages/Login";
import Dashboard from "./pages/Dashboard";
import Approvals from "./pages/Approvals";
import Delegations from "./pages/Delegations";
import Contracts from "./pages/Contracts";
import ContractDetail from "./pages/ContractDetail";
import Purchases from "./pages/Purchases";
import PurchaseDetail from "./pages/PurchaseDetail";
import AmendmentCreate from "./pages/AmendmentCreate";
import Osv from "./pages/Osv";
import Admin from "./pages/Admin";

function RequireAuth({ children }) {
  const { user, loading } = useAuth();
  if (loading) return <div className="loading">Загрузка...</div>;
  if (!user) return <Navigate to="/login" replace />;
  return children;
}

function RequireRole({ roles, children }) {
  const { user } = useAuth();
  if (!roles.includes(user.role) && user.role !== "Админ") return <Navigate to="/" replace />;
  return children;
}

function AppRoutes() {
  const { user, loading } = useAuth();
  if (loading) return <div className="loading">Загрузка...</div>;

  return (
    <Routes>
      <Route path="/login" element={user ? <Navigate to="/" replace /> : <Login />} />
      <Route element={<RequireAuth><Layout /></RequireAuth>}>
        <Route path="/" element={<Dashboard />} />
        <Route path="/approvals" element={<Approvals />} />
        <Route path="/delegations" element={<Delegations />} />
        <Route path="/contracts" element={<Contracts />} />
        <Route path="/contracts/:id" element={<ContractDetail />} />
        <Route path="/contracts/:id/amendment" element={<AmendmentCreate />} />
        <Route path="/purchases" element={<Purchases />} />
        <Route path="/purchases/:id" element={<PurchaseDetail />} />
        <Route path="/osv" element={
          <RequireRole roles={["Фин. директор"]}><Osv /></RequireRole>
        } />
        <Route path="/admin" element={
          <RequireRole roles={["Директор"]}><Admin /></RequireRole>
        } />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <ToastProvider>
        <AuthProvider>
          <AppRoutes />
        </AuthProvider>
      </ToastProvider>
    </BrowserRouter>
  );
}
