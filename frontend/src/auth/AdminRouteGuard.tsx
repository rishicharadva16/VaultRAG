import React from 'react';
import { useAuth } from './AuthContext';
import { NotFoundPage } from '../pages/NotFoundPage';

interface AdminRouteGuardProps {
  children: React.ReactNode;
}

export const AdminRouteGuard: React.FC<AdminRouteGuardProps> = ({ children }) => {
  const { user, isLoading } = useAuth();

  if (isLoading) {
    return (
      <div className="flex h-full w-full items-center justify-center p-8 text-sm text-text-muted">
        Loading...
      </div>
    );
  }

  const isAdmin = Boolean(user?.roles && user.roles.includes('admin'));

  if (!isAdmin) {
    // Exact neutral not-found page for non-admins (standing rule)
    return <NotFoundPage />;
  }

  return <>{children}</>;
};
