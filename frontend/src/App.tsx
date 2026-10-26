import { useCallback, useEffect, useState } from "react";
import { Navigate, Route, Routes } from "react-router-dom";
import { Layout } from "./components/Layout";
import { Spinner } from "./components/ui";
import { api } from "./lib/api";
import { SystemProvider } from "./lib/system";
import { ToastProvider } from "./lib/toast";
import { UploadProvider } from "./lib/uploads";
import { AlbumPage, AlbumsPage } from "./pages/AlbumsPage";
import { CloudPage } from "./pages/CloudPage";
import { DuplicatesPage } from "./pages/DuplicatesPage";
import { HomePage } from "./pages/HomePage";
import { LoginPage } from "./pages/LoginPage";
import { PeoplePage, PersonPage } from "./pages/PeoplePage";
import { PhotosPage } from "./pages/PhotosPage";
import { ReceiptsPage } from "./pages/ReceiptsPage";
import { UploadPage } from "./pages/UploadPage";

interface Session { password_required: boolean; logged_in: boolean }

export default function App() {
  const [session, setSession] = useState<Session | null>(null);
  const [error, setError] = useState("");

  const check = useCallback(() => {
    api<Session>("/session").then(setSession).catch((e: Error) => setError(e.message));
  }, []);

  useEffect(() => {
    check();
    window.addEventListener("imagevault:logged-out", check);
    return () => window.removeEventListener("imagevault:logged-out", check);
  }, [check]);

  if (error) return <div className="grid min-h-screen place-items-center p-6 text-center text-muted">{error}</div>;
  if (!session) return <Spinner />;
  if (!session.logged_in) return <LoginPage onLoggedIn={check} />;

  return (
    <ToastProvider>
      <SystemProvider>
        <UploadProvider>
          <Layout showLogout={session.password_required}>
            <Routes>
              <Route index element={<HomePage />} />
              <Route path="photos" element={<PhotosPage />} />
              <Route path="albums" element={<AlbumsPage />} />
              <Route path="receipts" element={<ReceiptsPage />} />
              <Route path="albums/:id" element={<AlbumPage />} />
              <Route path="upload" element={<UploadPage />} />
              <Route path="duplicates" element={<DuplicatesPage />} />
              <Route path="people" element={<PeoplePage />} />
              <Route path="people/:id" element={<PersonPage />} />
              <Route path="cloud" element={<CloudPage />} />
              <Route path="*" element={<Navigate to="/" replace />} />
            </Routes>
          </Layout>
        </UploadProvider>
      </SystemProvider>
    </ToastProvider>
  );
}
