import React from "react";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import "@/App.css";
import { Toaster } from "@/components/ui/sonner";
import { AuthProvider, useAuth } from "@/context/AuthContext";
import { ProjectProvider } from "@/context/ProjectContext";
import Layout from "@/components/Layout";
import Login from "@/pages/Login";
import Dashboard from "@/pages/Dashboard";
import MultiTemplateTracker from "@/pages/MultiTemplateTracker";
import LocationDetail from "@/pages/LocationDetail";
import YourList from "@/pages/YourList";
import Milestones from "@/pages/Milestones";
import ProjectSetup from "@/pages/ProjectSetup";
import Documents from "@/pages/Documents";
import Report from "@/pages/Report";
import UserManagement from "@/pages/UserManagement";
import { Loader2 } from "lucide-react";

function Protected({ children }) {
  const { user } = useAuth();
  if (user === null)
    return (
      <div className="h-screen w-screen flex items-center justify-center">
        <Loader2 className="animate-spin text-emerald-600" />
      </div>
    );
  if (!user) return <Navigate to="/login" replace />;
  return children;
}

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Toaster position="top-right" richColors />
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route
            element={
              <Protected>
                <ProjectProvider>
                  <Layout />
                </ProjectProvider>
              </Protected>
            }
          >
            <Route path="/dashboard" element={<Dashboard />} />
            <Route path="/your-list" element={<YourList />} />
            <Route path="/tracker" element={<MultiTemplateTracker />} />
            <Route path="/documents" element={<Documents />} />
            <Route path="/milestones" element={<Milestones />} />
            <Route path="/report" element={<Report />} />
            <Route path="/users" element={<UserManagement />} />
            <Route path="/setup" element={<ProjectSetup />} />
            <Route path="/location/:locationId" element={<LocationDetail />} />
          </Route>
          <Route path="*" element={<Navigate to="/dashboard" replace />} />
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  );
}
