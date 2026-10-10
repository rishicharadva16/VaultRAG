import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider } from './auth/AuthContext';
import { ChatProvider } from './chat/ChatContext';
import { ProtectedRoute } from './auth/ProtectedRoute';
import { AdminRouteGuard } from './auth/AdminRouteGuard';
import { AppShell } from './components/AppShell';
import { LoginPage } from './pages/LoginPage';
import { ChatPage } from './pages/ChatPage';
import { SearchPage } from './pages/SearchPage';
import { DocumentsPage } from './pages/DocumentsPage';
import { AdminDashboardPage } from './pages/AdminDashboardPage';
import { UserManagementPage } from './pages/UserManagementPage';
import { NotFoundPage } from './pages/NotFoundPage';

export const App: React.FC = () => {
  return (
    <AuthProvider>
      <ChatProvider>
        <BrowserRouter>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route
            path="/chat"
            element={
              <ProtectedRoute>
                <AppShell>
                  <ChatPage />
                </AppShell>
              </ProtectedRoute>
            }
          />
          <Route
            path="/search"
            element={
              <ProtectedRoute>
                <AppShell>
                  <SearchPage />
                </AppShell>
              </ProtectedRoute>
            }
          />
          <Route
            path="/documents"
            element={
              <ProtectedRoute>
                <AppShell>
                  <DocumentsPage />
                </AppShell>
              </ProtectedRoute>
            }
          />
          <Route
            path="/admin"
            element={
              <ProtectedRoute>
                <AdminRouteGuard>
                  <AppShell>
                    <AdminDashboardPage />
                  </AppShell>
                </AdminRouteGuard>
              </ProtectedRoute>
            }
          />
          <Route
            path="/admin/users"
            element={
              <ProtectedRoute>
                <AdminRouteGuard>
                  <AppShell>
                    <UserManagementPage />
                  </AppShell>
                </AdminRouteGuard>
              </ProtectedRoute>
            }
          />
          <Route path="/" element={<Navigate to="/chat" replace />} />
          <Route
            path="*"
            element={
              <ProtectedRoute>
                <AppShell>
                  <NotFoundPage />
                </AppShell>
              </ProtectedRoute>
            }
          />
        </Routes>
      </BrowserRouter>
    </ChatProvider>
  </AuthProvider>
  );
};

export default App;
