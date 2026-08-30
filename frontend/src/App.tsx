import { LoaderCircle } from "lucide-react";
import { lazy, Suspense } from "react";
import { Navigate, Outlet, Route, Routes } from "react-router-dom";
import { AppLayout } from "./components/AppLayout";
import { useAuth } from "./providers/AuthProvider";

const AuthPage = lazy(() => import("./pages/AuthPage").then((module) => ({ default: module.AuthPage })));
const DashboardPage = lazy(() => import("./pages/DashboardPage").then((module) => ({ default: module.DashboardPage })));
const DuplicatesPage = lazy(() => import("./pages/DuplicatesPage").then((module) => ({ default: module.DuplicatesPage })));
const GalleryPage = lazy(() => import("./pages/GalleryPage").then((module) => ({ default: module.GalleryPage })));
const ImageDetailPage = lazy(() => import("./pages/ImageDetailPage").then((module) => ({ default: module.ImageDetailPage })));
const SettingsPage = lazy(() => import("./pages/SettingsPage").then((module) => ({ default: module.SettingsPage })));
const SystemPage = lazy(() => import("./pages/SystemPage").then((module) => ({ default: module.SystemPage })));
const UploadPage = lazy(() => import("./pages/UploadPage").then((module) => ({ default: module.UploadPage })));

function RouteLoading() {
  return <div className="grid min-h-[50vh] place-items-center"><LoaderCircle className="h-6 w-6 animate-spin text-acid" /></div>;
}

function ProtectedLayout() {
  const { user, loading } = useAuth();
  if (loading) return <div className="grid min-h-screen place-items-center bg-canvas"><div className="text-center"><LoaderCircle className="mx-auto h-6 w-6 animate-spin text-acid" /><p className="mt-3 font-mono text-[10px] uppercase tracking-widest text-muted">Opening private vault</p></div></div>;
  if (!user) return <Navigate to="/login" replace />;
  return <AppLayout><Outlet /></AppLayout>;
}

export default function App() {
  return <Suspense fallback={<RouteLoading />}><Routes>
    <Route path="/login" element={<AuthPage />} />
    <Route path="/register" element={<AuthPage />} />
    <Route element={<ProtectedLayout />}>
      <Route index element={<DashboardPage />} />
      <Route path="gallery" element={<GalleryPage />} />
      <Route path="upload" element={<UploadPage />} />
      <Route path="duplicates" element={<DuplicatesPage />} />
      <Route path="images/:id" element={<ImageDetailPage />} />
      <Route path="system" element={<SystemPage />} />
      <Route path="settings" element={<SettingsPage />} />
    </Route>
    <Route path="*" element={<Navigate to="/" replace />} />
  </Routes></Suspense>;
}
