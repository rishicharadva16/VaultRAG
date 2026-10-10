import React, { useState, useEffect, useRef, useCallback } from 'react';
import { api, ApiClientError } from '../api/client';
import { AdminUser, CreateAdminUserPayload, PatchAdminUserPayload } from '../api/types';
import { useAuth } from '../auth/AuthContext';
import { NotFoundPage } from './NotFoundPage';
import { DepartmentBadge } from '../components/DepartmentBadge';
import { Skeleton } from '../components/Skeleton';
import { ErrorBanner } from '../components/ErrorBanner';
import {
  Users,
  UserPlus,
  Search,
  MoreVertical,
  Edit2,
  Key,
  UserX,
  UserCheck,
  CheckCircle2,
  XCircle,
  Eye,
  EyeOff,
  AlertCircle,
  Loader2,
  X,
  RotateCcw,
} from 'lucide-react';

const STANDARD_DEPARTMENTS = ['Engineering', 'Finance', 'HR', 'Sales'];

export const UserManagementPage: React.FC = () => {
  const { user: currentUser } = useAuth();
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [isForbidden, setIsForbidden] = useState<boolean>(false);

  // Filters & Search
  const [searchQuery, setSearchQuery] = useState('');
  const [departmentFilter, setDepartmentFilter] = useState('ALL');
  const [statusFilter, setStatusFilter] = useState('ALL');

  // Toasts
  const [toast, setToast] = useState<{ id: number; message: string; type: 'success' | 'error' } | null>(null);
  const toastTimeoutRef = useRef<number | null>(null);

  const showToast = useCallback((message: string, type: 'success' | 'error' = 'success') => {
    if (toastTimeoutRef.current) {
      window.clearTimeout(toastTimeoutRef.current);
    }
    setToast({ id: Date.now(), message, type });
    toastTimeoutRef.current = window.setTimeout(() => {
      setToast(null);
    }, 4000);
  }, []);

  // Modals state
  const [isAddOpen, setIsAddOpen] = useState(false);
  const [editingUser, setEditingUser] = useState<AdminUser | null>(null);
  const [deactivatingUser, setDeactivatingUser] = useState<AdminUser | null>(null);
  const [resetPasswordUser, setResetPasswordUser] = useState<AdminUser | null>(null);

  // Active row action menu ID
  const [actionMenuOpenId, setActionMenuOpenId] = useState<string | null>(null);

  // Add User Form State
  const [addName, setAddName] = useState('');
  const [addEmail, setAddEmail] = useState('');
  const [addDept, setAddDept] = useState('');
  const [addEmpId, setAddEmpId] = useState('');
  const [addPassword, setAddPassword] = useState('');
  const [addShowPassword, setAddShowPassword] = useState(false);
  const [addError, setAddError] = useState<string | null>(null);
  const [isAdding, setIsAdding] = useState(false);

  // Edit User Form State
  const [editName, setEditName] = useState('');
  const [editDept, setEditDept] = useState('');
  const [editIsActive, setEditIsActive] = useState(true);
  const [editPassword, setEditPassword] = useState('');
  const [editShowPassword, setEditShowPassword] = useState(false);
  const [editError, setEditError] = useState<string | null>(null);
  const [isEditing, setIsEditing] = useState(false);

  // Reset Password Modal State
  const [resetPassword, setResetPassword] = useState('');
  const [resetShowPassword, setResetShowPassword] = useState(false);
  const [resetError, setResetError] = useState<string | null>(null);
  const [isResetting, setIsResetting] = useState(false);

  // Load users
  const loadUsers = useCallback(async () => {
    setIsLoading(true);
    setErrorMessage(null);
    try {
      const data = await api.getAdminUsers();
      setUsers(data);
    } catch (err: unknown) {
      if (err instanceof ApiClientError) {
        if (err.status === 403) {
          setIsForbidden(true);
          return;
        }
        setErrorMessage(err.message);
      } else {
        setErrorMessage('Failed to load users. Is the backend running?');
      }
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    loadUsers();
  }, [loadUsers]);

  // Close open action menu on outside click
  useEffect(() => {
    const handleOutsideClick = (e: MouseEvent) => {
      const target = e.target as HTMLElement;
      if (!target.closest('[data-action-menu]')) {
        setActionMenuOpenId(null);
      }
    };
    document.addEventListener('click', handleOutsideClick);
    return () => {
      document.removeEventListener('click', handleOutsideClick);
    };
  }, []);

  // Close modals on Escape key
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        if (isAddOpen && !isAdding) closeAddModal();
        if (editingUser && !isEditing) closeEditModal();
        if (deactivatingUser) setDeactivatingUser(null);
        if (resetPasswordUser && !isResetting) closeResetModal();
        setActionMenuOpenId(null);
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => {
      window.removeEventListener('keydown', handleKeyDown);
    };
  }, [isAddOpen, isAdding, editingUser, isEditing, deactivatingUser, resetPasswordUser, isResetting]);

  // If 403, render neutral NotFoundPage (standing rule)
  if (isForbidden) {
    return <NotFoundPage />;
  }

  // Departments list for dropdown
  const allDepartments = Array.from(
    new Set([
      ...STANDARD_DEPARTMENTS,
      ...users.map((u) => u.department).filter((d): d is string => Boolean(d)),
    ])
  ).sort();

  // Filtered users
  const filteredUsers = users.filter((u) => {
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase().trim();
      const matchName = u.name.toLowerCase().includes(q);
      const matchEmail = u.email.toLowerCase().includes(q);
      const matchEmp = u.employee_id ? u.employee_id.toLowerCase().includes(q) : false;
      if (!matchName && !matchEmail && !matchEmp) return false;
    }
    if (departmentFilter !== 'ALL') {
      if (departmentFilter === 'NONE') {
        if (u.department !== null && u.department !== '') return false;
      } else if (u.department !== departmentFilter) {
        return false;
      }
    }
    if (statusFilter === 'ACTIVE' && !u.is_active) return false;
    if (statusFilter === 'INACTIVE' && u.is_active) return false;
    return true;
  });

  const getInitials = (name: string, email: string) => {
    if (name.trim()) {
      const parts = name.trim().split(/\s+/);
      if (parts.length >= 2) {
        return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
      }
      return parts[0].slice(0, 2).toUpperCase();
    }
    return email.charAt(0).toUpperCase();
  };

  // Add User Handlers
  const openAddModal = () => {
    setAddName('');
    setAddEmail('');
    setAddDept('');
    setAddEmpId('');
    setAddPassword('');
    setAddShowPassword(false);
    setAddError(null);
    setIsAddOpen(true);
  };

  const closeAddModal = () => {
    setIsAddOpen(false);
    setAddPassword('');
    setAddError(null);
  };

  const handleAddSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setAddError(null);

    const trimmedName = addName.trim();
    const trimmedEmail = addEmail.trim();

    if (!trimmedName) {
      setAddError('Full name is required.');
      return;
    }
    if (!trimmedEmail) {
      setAddError('Email address is required.');
      return;
    }
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(trimmedEmail)) {
      setAddError('Please enter a valid email address.');
      return;
    }
    if (!addPassword) {
      setAddError('Password is required.');
      return;
    }
    if (addPassword.length < 8) {
      setAddError('Password must be at least 8 characters long.');
      return;
    }

    setIsAdding(true);
    try {
      const payload: CreateAdminUserPayload = {
        name: trimmedName,
        email: trimmedEmail,
        password: addPassword,
        department: addDept || null,
        employee_id: addEmpId.trim() || null,
      };
      const created = await api.createAdminUser(payload);
      showToast(`User ${created.name} created successfully.`);
      closeAddModal();
      await loadUsers();
    } catch (err: unknown) {
      if (err instanceof ApiClientError) {
        if (err.status === 403) {
          setIsForbidden(true);
          return;
        }
        if (err.status === 422) {
          setAddError(err.message || 'Duplicate email or invalid data.');
          return;
        }
        setAddError(err.message);
      } else {
        setAddError('Failed to create user. Please try again.');
      }
    } finally {
      setIsAdding(false);
    }
  };

  // Edit User Handlers
  const openEditModal = (u: AdminUser) => {
    setActionMenuOpenId(null);
    setEditingUser(u);
    setEditName(u.name);
    setEditDept(u.department || '');
    setEditIsActive(u.is_active);
    setEditPassword('');
    setEditShowPassword(false);
    setEditError(null);
  };

  const closeEditModal = () => {
    setEditingUser(null);
    setEditPassword('');
    setEditError(null);
  };

  const handleEditSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!editingUser) return;
    setEditError(null);

    const trimmedName = editName.trim();
    if (!trimmedName) {
      setEditError('Full name is required.');
      return;
    }

    if (editPassword && editPassword.length < 8) {
      setEditError('New password must be at least 8 characters long.');
      return;
    }

    // Check self deactivation
    const isSelf = editingUser.id === currentUser?.id;
    if (isSelf && !editIsActive) {
      setEditError('Admin cannot deactivate themselves.');
      return;
    }

    // If changing from active to inactive, ask for confirmation
    if (editingUser.is_active && !editIsActive) {
      setDeactivatingUser(editingUser);
      return;
    }

    setIsEditing(true);
    try {
      const payload: PatchAdminUserPayload = {
        name: trimmedName,
        department: editDept || null,
        is_active: editIsActive,
      };
      if (editPassword) {
        payload.password = editPassword;
      }
      const updated = await api.patchAdminUser(editingUser.id, payload);
      showToast(`User ${updated.name} updated successfully.`);
      closeEditModal();
      await loadUsers();
    } catch (err: unknown) {
      if (err instanceof ApiClientError) {
        if (err.status === 403) {
          setIsForbidden(true);
          return;
        }
        setEditError(err.message);
      } else {
        setEditError('Failed to update user. Please try again.');
      }
    } finally {
      setIsEditing(false);
    }
  };

  // Toggle Active Handler (from action menu)
  const handleToggleActive = (u: AdminUser) => {
    setActionMenuOpenId(null);
    const isSelf = u.id === currentUser?.id;
    if (isSelf && u.is_active) {
      showToast('Admin cannot deactivate themselves.', 'error');
      return;
    }

    if (u.is_active) {
      // Prompt for confirmation
      setDeactivatingUser(u);
    } else {
      // Directly activate
      confirmActivateUser(u);
    }
  };

  const confirmActivateUser = async (u: AdminUser) => {
    try {
      await api.patchAdminUser(u.id, { is_active: true });
      showToast(`User ${u.name} has been activated.`);
      await loadUsers();
    } catch (err: unknown) {
      if (err instanceof ApiClientError) {
        showToast(err.message, 'error');
      } else {
        showToast('Failed to activate user.', 'error');
      }
    }
  };

  const confirmDeactivateUser = async () => {
    if (!deactivatingUser) return;
    try {
      await api.patchAdminUser(deactivatingUser.id, { is_active: false });
      showToast(`User ${deactivatingUser.name} has been deactivated.`);
      setDeactivatingUser(null);
      if (editingUser && editingUser.id === deactivatingUser.id) {
        closeEditModal();
      }
      await loadUsers();
    } catch (err: unknown) {
      if (err instanceof ApiClientError) {
        showToast(err.message, 'error');
      } else {
        showToast('Failed to deactivate user.', 'error');
      }
    }
  };

  // Reset Password Handlers
  const openResetModal = (u: AdminUser) => {
    setActionMenuOpenId(null);
    setResetPasswordUser(u);
    setResetPassword('');
    setResetShowPassword(false);
    setResetError(null);
  };

  const closeResetModal = () => {
    setResetPasswordUser(null);
    setResetPassword('');
    setResetError(null);
  };

  const handleResetSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!resetPasswordUser) return;
    setResetError(null);

    if (!resetPassword) {
      setResetError('New password is required.');
      return;
    }
    if (resetPassword.length < 8) {
      setResetError('Password must be at least 8 characters long.');
      return;
    }

    setIsResetting(true);
    try {
      await api.patchAdminUser(resetPasswordUser.id, { password: resetPassword });
      showToast(`Password for ${resetPasswordUser.name} has been reset.`);
      closeResetModal();
    } catch (err: unknown) {
      if (err instanceof ApiClientError) {
        if (err.status === 403) {
          setIsForbidden(true);
          return;
        }
        setResetError(err.message);
      } else {
        setResetError('Failed to reset password. Please try again.');
      }
    } finally {
      setIsResetting(false);
    }
  };

  return (
    <div className="flex-1 overflow-y-auto bg-background p-4 md:p-6 text-text">
      {/* Toast Notification */}
      {toast && (
        <div
          role="status"
          aria-live="polite"
          className={`fixed bottom-5 right-5 z-50 flex items-center gap-3 rounded-card border px-4 py-3 text-sm shadow-raised animate-in slide-in-from-bottom duration-200 ${
            toast.type === 'success'
              ? 'border-emerald-300 bg-emerald-50 text-emerald-900 dark:border-emerald-900/60 dark:bg-emerald-950/80 dark:text-emerald-200'
              : 'border-red-300 bg-red-50 text-red-900 dark:border-red-900/60 dark:bg-red-950/80 dark:text-red-200'
          }`}
        >
          {toast.type === 'success' ? (
            <CheckCircle2 size={18} className="text-emerald-600 dark:text-emerald-400 shrink-0" aria-hidden="true" />
          ) : (
            <AlertCircle size={18} className="text-danger shrink-0" aria-hidden="true" />
          )}
          <span className="font-medium">{toast.message}</span>
          <button
            type="button"
            onClick={() => setToast(null)}
            aria-label="Dismiss notification"
            className="ml-2 text-text-muted hover:text-text rounded p-0.5"
          >
            <X size={15} aria-hidden="true" />
          </button>
        </div>
      )}

      <div className="max-w-7xl mx-auto space-y-6">
        {/* Header Section */}
        <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between border-b border-border-subtle pb-5">
          <div>
            <div className="flex items-center gap-2.5">
              <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-accent text-accent-contrast shadow-xs">
                <Users size={20} aria-hidden="true" />
              </div>
              <h1 className="text-xl md:text-2xl font-bold tracking-tight text-text">User Management</h1>
            </div>
            <p className="mt-1 text-xs md:text-sm text-text-muted">
              {isLoading ? 'Loading users...' : `${users.length} total ${users.length === 1 ? 'user' : 'users'} registered`}
            </p>
          </div>

          <button
            type="button"
            onClick={openAddModal}
            className="inline-flex items-center justify-center gap-2 rounded-btn bg-accent px-4 py-2 text-sm font-semibold text-accent-contrast shadow-xs hover:bg-accent-hover transition-colors min-h-[40px] focus-visible:ring-2 focus-visible:ring-accent"
            data-testid="add-user-button"
            aria-label="Add new user"
          >
            <UserPlus size={16} aria-hidden="true" />
            <span>Add user</span>
          </button>
        </div>

        {/* Search & Filters Bar */}
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between bg-surface p-3.5 rounded-card border border-border shadow-xs">
          {/* Search Box */}
          <div className="relative flex-1 max-w-md">
            <div className="pointer-events-none absolute inset-y-0 left-0 flex items-center pl-3 text-text-muted">
              <Search size={16} aria-hidden="true" />
            </div>
            <input
              type="text"
              id="user-search-input"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search by name, email, or employee ID..."
              aria-label="Search users by name, email, or employee ID"
              className="w-full rounded-input border border-border bg-background py-2 pl-9 pr-8 text-sm text-text placeholder:text-text-muted focus:border-accent focus:outline-none focus-visible:ring-2 focus-visible:ring-accent min-h-[40px] md:min-h-0"
            />
            {searchQuery && (
              <button
                type="button"
                onClick={() => setSearchQuery('')}
                aria-label="Clear search query"
                className="absolute inset-y-0 right-0 flex items-center pr-2.5 text-text-muted hover:text-text"
              >
                <X size={15} aria-hidden="true" />
              </button>
            )}
          </div>

          {/* Filters: Department & Status */}
          <div className="flex flex-wrap items-center gap-2.5">
            <div className="flex items-center gap-1.5">
              <label htmlFor="dept-filter-select" className="text-xs font-medium text-text-muted sr-only sm:not-sr-only">
                Dept:
              </label>
              <select
                id="dept-filter-select"
                value={departmentFilter}
                onChange={(e) => setDepartmentFilter(e.target.value)}
                aria-label="Filter by department"
                className="rounded-input border border-border bg-background py-2 px-3 text-xs md:text-sm text-text focus:border-accent focus:outline-none focus-visible:ring-2 focus-visible:ring-accent min-h-[40px] md:min-h-0"
              >
                <option value="ALL">All Departments</option>
                {allDepartments.map((d) => (
                  <option key={d} value={d}>
                    {d}
                  </option>
                ))}
                <option value="NONE">Unassigned / None</option>
              </select>
            </div>

            <div className="flex items-center gap-1.5">
              <label htmlFor="status-filter-select" className="text-xs font-medium text-text-muted sr-only sm:not-sr-only">
                Status:
              </label>
              <select
                id="status-filter-select"
                value={statusFilter}
                onChange={(e) => setStatusFilter(e.target.value)}
                aria-label="Filter by account status"
                className="rounded-input border border-border bg-background py-2 px-3 text-xs md:text-sm text-text focus:border-accent focus:outline-none focus-visible:ring-2 focus-visible:ring-accent min-h-[40px] md:min-h-0"
              >
                <option value="ALL">All Status</option>
                <option value="ACTIVE">Active</option>
                <option value="INACTIVE">Inactive</option>
              </select>
            </div>

            {(searchQuery || departmentFilter !== 'ALL' || statusFilter !== 'ALL') && (
              <button
                type="button"
                onClick={() => {
                  setSearchQuery('');
                  setDepartmentFilter('ALL');
                  setStatusFilter('ALL');
                }}
                className="inline-flex items-center gap-1 text-xs text-text-muted hover:text-text px-2 py-1.5 rounded-btn hover:bg-surface-raised min-h-[40px] md:min-h-0"
                aria-label="Reset all search and filter settings"
              >
                <RotateCcw size={13} aria-hidden="true" />
                <span>Reset</span>
              </button>
            )}
          </div>
        </div>

        {/* Error Banner */}
        {errorMessage && (
          <ErrorBanner
            message={errorMessage}
            onRetry={loadUsers}
            onDismiss={() => setErrorMessage(null)}
          />
        )}

        {/* Loading Skeletons */}
        {isLoading && (
          <div className="space-y-3" aria-live="polite" aria-busy="true">
            <Skeleton className="h-16 w-full" />
            <Skeleton className="h-16 w-full" />
            <Skeleton className="h-16 w-full" />
            <Skeleton className="h-16 w-full" />
          </div>
        )}

        {/* Empty State */}
        {!isLoading && filteredUsers.length === 0 && (
          <div
            className="rounded-card border border-border bg-surface p-12 text-center"
            data-testid="empty-users-state"
          >
            <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-surface-raised border border-border text-text-muted mb-3">
              <Users size={24} aria-hidden="true" />
            </div>
            <h2 className="text-base font-semibold text-text">No users match your filters</h2>
            <p className="mt-1 text-xs md:text-sm text-text-muted max-w-sm mx-auto">
              Try adjusting your search terms or clearing department and status filters.
            </p>
            {(searchQuery || departmentFilter !== 'ALL' || statusFilter !== 'ALL') && (
              <button
                type="button"
                onClick={() => {
                  setSearchQuery('');
                  setDepartmentFilter('ALL');
                  setStatusFilter('ALL');
                }}
                className="mt-4 inline-flex items-center gap-1.5 rounded-btn bg-surface-raised border border-border px-3.5 py-2 text-xs font-semibold text-text hover:bg-border transition-colors min-h-[40px]"
              >
                <RotateCcw size={14} aria-hidden="true" />
                <span>Clear filters</span>
              </button>
            )}
          </div>
        )}

        {/* Users Content: Desktop Table & Mobile Cards */}
        {!isLoading && filteredUsers.length > 0 && (
          <>
            {/* Desktop Table View (>= md) */}
            <div className="hidden md:block overflow-hidden rounded-card border border-border bg-surface shadow-xs">
              <div className="max-h-[680px] overflow-y-auto">
                <table className="w-full text-left text-sm border-collapse">
                  <thead className="sticky top-0 z-10 border-b border-border bg-surface-raised text-text-muted font-semibold uppercase tracking-wider text-xs">
                    <tr>
                      <th scope="col" className="py-3 px-4">User</th>
                      <th scope="col" className="py-3 px-3">Department</th>
                      <th scope="col" className="py-3 px-3">Employee ID</th>
                      <th scope="col" className="py-3 px-3">Status</th>
                      <th scope="col" className="py-3 px-4 text-right">Actions</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border">
                    {filteredUsers.map((u) => {
                      const isSelf = u.id === currentUser?.id;
                      const menuOpen = actionMenuOpenId === u.id;

                      return (
                        <tr
                          key={u.id}
                          className="hover:bg-surface-raised/50 transition-colors"
                          data-testid={`user-row-${u.id}`}
                        >
                          {/* Name + Email + Avatar */}
                          <td className="py-3.5 px-4">
                            <div className="flex items-center gap-3">
                              <div
                                className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-surface-raised border border-border font-semibold text-text text-xs"
                                aria-hidden="true"
                              >
                                {getInitials(u.name, u.email)}
                              </div>
                              <div className="min-w-0">
                                <div className="font-semibold text-text truncate flex items-center gap-1.5">
                                  <span>{u.name}</span>
                                  {u.is_admin && (
                                    <span className="text-[10px] font-bold text-accent uppercase tracking-wider px-1.5 py-0.2 rounded bg-accent/10">
                                      Admin
                                    </span>
                                  )}
                                  {isSelf && (
                                    <span className="text-[10px] text-text-muted italic">
                                      (You)
                                    </span>
                                  )}
                                </div>
                                <div className="text-xs text-text-muted truncate">{u.email}</div>
                              </div>
                            </div>
                          </td>

                          {/* Department */}
                          <td className="py-3.5 px-3 whitespace-nowrap">
                            <DepartmentBadge department={u.department} isAdmin={u.is_admin} size="sm" />
                          </td>

                          {/* Employee ID */}
                          <td className="py-3.5 px-3 text-text-muted font-mono text-xs whitespace-nowrap">
                            {u.employee_id || '—'}
                          </td>

                          {/* Status Pill (Never shown by color alone) */}
                          <td className="py-3.5 px-3 whitespace-nowrap">
                            {u.is_active ? (
                              <span
                                className="inline-flex items-center gap-1 rounded-badge bg-emerald-500/10 px-2.5 py-0.5 text-xs font-semibold text-emerald-700 dark:text-emerald-400 border border-emerald-500/20"
                                data-testid={`user-status-${u.id}`}
                              >
                                <CheckCircle2 size={13} aria-hidden="true" />
                                <span>Active</span>
                              </span>
                            ) : (
                              <span
                                className="inline-flex items-center gap-1 rounded-badge bg-slate-500/10 px-2.5 py-0.5 text-xs font-semibold text-slate-600 dark:text-slate-400 border border-slate-500/20"
                                data-testid={`user-status-${u.id}`}
                              >
                                <XCircle size={13} aria-hidden="true" />
                                <span>Inactive</span>
                              </span>
                            )}
                          </td>

                          {/* Actions Menu */}
                          <td className="py-3.5 px-4 text-right whitespace-nowrap">
                            <div className="relative inline-block text-left" data-action-menu>
                              <button
                                type="button"
                                onClick={(e) => {
                                  e.stopPropagation();
                                  setActionMenuOpenId(menuOpen ? null : u.id);
                                }}
                                aria-label={`Actions for user ${u.name}`}
                                aria-expanded={menuOpen}
                                aria-haspopup="true"
                                className="inline-flex items-center justify-center h-8 w-8 rounded-btn text-text-muted hover:bg-surface-raised hover:text-text transition-colors focus-visible:ring-2 focus-visible:ring-accent"
                                data-testid={`user-actions-btn-${u.id}`}
                              >
                                <MoreVertical size={16} aria-hidden="true" />
                              </button>

                              {menuOpen && (
                                <div
                                  role="menu"
                                  aria-orientation="vertical"
                                  className="absolute right-0 top-full mt-1 w-44 rounded-card border border-border bg-surface p-1 shadow-raised z-30 animate-in fade-in zoom-in-95 duration-100"
                                >
                                  <button
                                    type="button"
                                    role="menuitem"
                                    onClick={() => openEditModal(u)}
                                    className="flex w-full items-center gap-2 rounded-btn px-2.5 py-1.5 text-xs font-medium text-text hover:bg-surface-raised text-left transition-colors"
                                    data-testid={`action-edit-${u.id}`}
                                  >
                                    <Edit2 size={14} className="text-text-muted" aria-hidden="true" />
                                    <span>Edit</span>
                                  </button>

                                  <button
                                    type="button"
                                    role="menuitem"
                                    disabled={isSelf && u.is_active}
                                    title={isSelf && u.is_active ? 'Admin cannot deactivate themselves' : undefined}
                                    onClick={() => handleToggleActive(u)}
                                    className={`flex w-full items-center gap-2 rounded-btn px-2.5 py-1.5 text-xs font-medium text-left transition-colors ${
                                      isSelf && u.is_active
                                        ? 'opacity-40 cursor-not-allowed text-text-muted'
                                        : u.is_active
                                        ? 'text-danger hover:bg-red-50 dark:hover:bg-red-950/40'
                                        : 'text-emerald-700 dark:text-emerald-400 hover:bg-emerald-50 dark:hover:bg-emerald-950/40'
                                    }`}
                                    data-testid={`action-toggle-active-${u.id}`}
                                  >
                                    {u.is_active ? (
                                      <>
                                        <UserX size={14} aria-hidden="true" />
                                        <span>Deactivate</span>
                                      </>
                                    ) : (
                                      <>
                                        <UserCheck size={14} aria-hidden="true" />
                                        <span>Activate</span>
                                      </>
                                    )}
                                  </button>

                                  <button
                                    type="button"
                                    role="menuitem"
                                    onClick={() => openResetModal(u)}
                                    className="flex w-full items-center gap-2 rounded-btn px-2.5 py-1.5 text-xs font-medium text-text hover:bg-surface-raised text-left transition-colors"
                                    data-testid={`action-reset-pw-${u.id}`}
                                  >
                                    <Key size={14} className="text-text-muted" aria-hidden="true" />
                                    <span>Reset password</span>
                                  </button>
                                </div>
                              )}
                            </div>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </div>

            {/* Mobile Cards View (< md) - No horizontal scroll at 360px */}
            <div className="grid grid-cols-1 gap-3 md:hidden">
              {filteredUsers.map((u) => {
                const isSelf = u.id === currentUser?.id;
                const menuOpen = actionMenuOpenId === u.id;

                return (
                  <div
                    key={u.id}
                    className="rounded-card border border-border bg-surface p-4 shadow-xs space-y-3 min-w-0"
                    data-testid={`user-card-${u.id}`}
                  >
                    {/* Top Row: Avatar + Name/Email + Action Menu */}
                    <div className="flex items-start justify-between gap-2 min-w-0">
                      <div className="flex items-center gap-2.5 min-w-0">
                        <div
                          className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-surface-raised border border-border font-semibold text-text text-xs"
                          aria-hidden="true"
                        >
                          {getInitials(u.name, u.email)}
                        </div>
                        <div className="min-w-0">
                          <h2 className="font-semibold text-sm text-text truncate flex items-center gap-1.5">
                            <span className="truncate">{u.name}</span>
                            {u.is_admin && (
                              <span className="text-[10px] font-bold text-accent uppercase tracking-wider px-1 rounded bg-accent/10 shrink-0">
                                Admin
                              </span>
                            )}
                            {isSelf && (
                              <span className="text-[10px] text-text-muted italic shrink-0">
                                (You)
                              </span>
                            )}
                          </h2>
                          <p className="text-xs text-text-muted truncate">{u.email}</p>
                        </div>
                      </div>

                      {/* Action dropdown for mobile */}
                      <div className="relative shrink-0" data-action-menu>
                        <button
                          type="button"
                          onClick={(e) => {
                            e.stopPropagation();
                            setActionMenuOpenId(menuOpen ? null : u.id);
                          }}
                          aria-label={`Actions for user ${u.name}`}
                          aria-expanded={menuOpen}
                          className="flex h-10 w-10 items-center justify-center rounded-btn text-text-muted hover:bg-surface-raised hover:text-text transition-colors"
                        >
                          <MoreVertical size={18} aria-hidden="true" />
                        </button>

                        {menuOpen && (
                          <div
                            role="menu"
                            aria-orientation="vertical"
                            className="absolute right-0 top-full mt-1 w-44 rounded-card border border-border bg-surface p-1 shadow-raised z-30 animate-in fade-in zoom-in-95 duration-100"
                          >
                            <button
                              type="button"
                              role="menuitem"
                              onClick={() => openEditModal(u)}
                              className="flex w-full items-center gap-2 rounded-btn px-3 py-2 text-xs font-medium text-text hover:bg-surface-raised min-h-[40px]"
                            >
                              <Edit2 size={14} className="text-text-muted" aria-hidden="true" />
                              <span>Edit</span>
                            </button>

                            <button
                              type="button"
                              role="menuitem"
                              disabled={isSelf && u.is_active}
                              title={isSelf && u.is_active ? 'Admin cannot deactivate themselves' : undefined}
                              onClick={() => handleToggleActive(u)}
                              className={`flex w-full items-center gap-2 rounded-btn px-3 py-2 text-xs font-medium min-h-[40px] ${
                                isSelf && u.is_active
                                  ? 'opacity-40 cursor-not-allowed text-text-muted'
                                  : u.is_active
                                  ? 'text-danger hover:bg-red-50 dark:hover:bg-red-950/40'
                                  : 'text-emerald-700 dark:text-emerald-400 hover:bg-emerald-50 dark:hover:bg-emerald-950/40'
                              }`}
                            >
                              {u.is_active ? (
                                <>
                                  <UserX size={14} aria-hidden="true" />
                                  <span>Deactivate</span>
                                </>
                              ) : (
                                <>
                                  <UserCheck size={14} aria-hidden="true" />
                                  <span>Activate</span>
                                </>
                              )}
                            </button>

                            <button
                              type="button"
                              role="menuitem"
                              onClick={() => openResetModal(u)}
                              className="flex w-full items-center gap-2 rounded-btn px-3 py-2 text-xs font-medium text-text hover:bg-surface-raised min-h-[40px]"
                            >
                              <Key size={14} className="text-text-muted" aria-hidden="true" />
                              <span>Reset password</span>
                            </button>
                          </div>
                        )}
                      </div>
                    </div>

                    {/* Middle Info: Department & Emp ID */}
                    <div className="flex flex-wrap items-center justify-between gap-2 border-t border-border-subtle pt-2.5 text-xs text-text-muted">
                      <div>
                        <DepartmentBadge department={u.department} isAdmin={u.is_admin} size="sm" />
                      </div>
                      <div className="font-mono text-[11px]">
                        ID: {u.employee_id || '—'}
                      </div>
                    </div>

                    {/* Bottom Status Pill */}
                    <div className="flex items-center justify-between border-t border-border-subtle pt-2 text-xs">
                      <span className="text-text-muted">Account Status:</span>
                      {u.is_active ? (
                        <span className="inline-flex items-center gap-1 rounded-badge bg-emerald-500/10 px-2 py-0.5 text-xs font-semibold text-emerald-700 dark:text-emerald-400 border border-emerald-500/20">
                          <CheckCircle2 size={12} aria-hidden="true" />
                          <span>Active</span>
                        </span>
                      ) : (
                        <span className="inline-flex items-center gap-1 rounded-badge bg-slate-500/10 px-2 py-0.5 text-xs font-semibold text-slate-600 dark:text-slate-400 border border-slate-500/20">
                          <XCircle size={12} aria-hidden="true" />
                          <span>Inactive</span>
                        </span>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          </>
        )}
      </div>

      {/* ── ADD USER DIALOG (Full-screen sheet on mobile) ── */}
      {isAddOpen && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center p-0 md:p-4 bg-background md:bg-black/50 md:backdrop-blur-xs overflow-y-auto"
          role="dialog"
          aria-modal="true"
          aria-labelledby="add-user-title"
        >
          <div className="relative flex h-full md:h-auto w-full md:max-w-md flex-col rounded-none md:rounded-card border-0 md:border md:border-border bg-surface p-6 shadow-panel">
            <div className="flex items-center justify-between border-b border-border-subtle pb-4 mb-4">
              <div className="flex items-center gap-2">
                <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-accent text-accent-contrast">
                  <UserPlus size={18} aria-hidden="true" />
                </div>
                <h2 id="add-user-title" className="text-base font-bold text-text">
                  Add New User
                </h2>
              </div>
              <button
                type="button"
                onClick={closeAddModal}
                disabled={isAdding}
                aria-label="Close dialog"
                className="rounded-btn p-1.5 text-text-muted hover:bg-surface-raised hover:text-text transition-colors min-h-[40px] min-w-[40px] flex items-center justify-center"
              >
                <X size={18} aria-hidden="true" />
              </button>
            </div>

            {addError && (
              <div
                role="alert"
                className="mb-4 flex items-start gap-2 rounded-card border border-red-300 bg-red-50 p-3 text-xs text-red-900 dark:border-red-900/60 dark:bg-red-950/40 dark:text-red-200"
              >
                <AlertCircle size={15} className="text-danger shrink-0 mt-0.5" aria-hidden="true" />
                <div className="leading-relaxed">{addError}</div>
              </div>
            )}

            <form onSubmit={handleAddSubmit} className="space-y-4 flex-1 flex flex-col justify-between" noValidate>
              <div className="space-y-4">
                {/* Name */}
                <div>
                  <label htmlFor="add-name" className="block text-xs font-semibold text-text mb-1">
                    Full name <span className="text-danger">*</span>
                  </label>
                  <input
                    id="add-name"
                    type="text"
                    required
                    value={addName}
                    onChange={(e) => setAddName(e.target.value)}
                    placeholder="e.g. Rahul Sharma"
                    className="w-full rounded-input border border-border bg-background py-2 px-3 text-sm text-text focus:border-accent focus:outline-none focus-visible:ring-2 focus-visible:ring-accent min-h-[40px]"
                  />
                </div>

                {/* Email */}
                <div>
                  <label htmlFor="add-email" className="block text-xs font-semibold text-text mb-1">
                    Corporate email <span className="text-danger">*</span>
                  </label>
                  <input
                    id="add-email"
                    type="email"
                    required
                    value={addEmail}
                    onChange={(e) => setAddEmail(e.target.value)}
                    placeholder="name@northwind.example"
                    className="w-full rounded-input border border-border bg-background py-2 px-3 text-sm text-text focus:border-accent focus:outline-none focus-visible:ring-2 focus-visible:ring-accent min-h-[40px]"
                  />
                </div>

                {/* Department Dropdown */}
                <div>
                  <label htmlFor="add-department" className="block text-xs font-semibold text-text mb-1">
                    Department
                  </label>
                  <select
                    id="add-department"
                    value={addDept}
                    onChange={(e) => setAddDept(e.target.value)}
                    className="w-full rounded-input border border-border bg-background py-2 px-3 text-sm text-text focus:border-accent focus:outline-none focus-visible:ring-2 focus-visible:ring-accent min-h-[40px]"
                  >
                    <option value="">None / Unassigned</option>
                    {allDepartments.map((d) => (
                      <option key={d} value={d}>
                        {d}
                      </option>
                    ))}
                  </select>
                </div>

                {/* Optional Employee ID */}
                <div>
                  <label htmlFor="add-empid" className="block text-xs font-semibold text-text mb-1">
                    Employee ID <span className="text-text-muted font-normal">(optional)</span>
                  </label>
                  <input
                    id="add-empid"
                    type="text"
                    value={addEmpId}
                    onChange={(e) => setAddEmpId(e.target.value)}
                    placeholder="e.g. EMP009"
                    className="w-full rounded-input border border-border bg-background py-2 px-3 text-sm text-text focus:border-accent focus:outline-none focus-visible:ring-2 focus-visible:ring-accent min-h-[40px]"
                  />
                </div>

                {/* Initial Password */}
                <div>
                  <label htmlFor="add-password" className="block text-xs font-semibold text-text mb-1">
                    Initial password <span className="text-danger">*</span>{' '}
                    <span className="text-text-muted font-normal">(min. 8 characters)</span>
                  </label>
                  <div className="relative">
                    <input
                      id="add-password"
                      type={addShowPassword ? 'text' : 'password'}
                      required
                      value={addPassword}
                      onChange={(e) => setAddPassword(e.target.value)}
                      placeholder="••••••••••••"
                      className="w-full rounded-input border border-border bg-background py-2 pl-3 pr-10 text-sm text-text focus:border-accent focus:outline-none focus-visible:ring-2 focus-visible:ring-accent min-h-[40px]"
                      autoComplete="new-password"
                    />
                    <button
                      type="button"
                      onClick={() => setAddShowPassword(!addShowPassword)}
                      aria-label={addShowPassword ? 'Hide password' : 'Show password'}
                      className="absolute inset-y-0 right-0 flex items-center pr-3 text-text-muted hover:text-text"
                    >
                      {addShowPassword ? <EyeOff size={16} aria-hidden="true" /> : <Eye size={16} aria-hidden="true" />}
                    </button>
                  </div>
                </div>
              </div>

              {/* Action buttons */}
              <div className="flex items-center justify-end gap-3 pt-6 border-t border-border-subtle mt-6">
                <button
                  type="button"
                  onClick={closeAddModal}
                  disabled={isAdding}
                  className="rounded-btn border border-border bg-surface-raised px-4 py-2 text-sm font-semibold text-text hover:bg-border transition-colors min-h-[40px]"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={isAdding}
                  className="inline-flex items-center justify-center gap-2 rounded-btn bg-accent px-4 py-2 text-sm font-semibold text-accent-contrast shadow-xs hover:bg-accent-hover disabled:opacity-50 transition-colors min-h-[40px] focus-visible:ring-2 focus-visible:ring-accent"
                  data-testid="submit-add-user"
                >
                  {isAdding ? (
                    <>
                      <Loader2 size={16} className="animate-spin" aria-hidden="true" />
                      <span>Creating...</span>
                    </>
                  ) : (
                    <span>Create User</span>
                  )}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* ── EDIT USER DIALOG (Full-screen sheet on mobile) ── */}
      {editingUser && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center p-0 md:p-4 bg-background md:bg-black/50 md:backdrop-blur-xs overflow-y-auto"
          role="dialog"
          aria-modal="true"
          aria-labelledby="edit-user-title"
        >
          <div className="relative flex h-full md:h-auto w-full md:max-w-md flex-col rounded-none md:rounded-card border-0 md:border md:border-border bg-surface p-6 shadow-panel">
            <div className="flex items-center justify-between border-b border-border-subtle pb-4 mb-4">
              <div className="flex items-center gap-2">
                <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-accent text-accent-contrast">
                  <Edit2 size={18} aria-hidden="true" />
                </div>
                <h2 id="edit-user-title" className="text-base font-bold text-text">
                  Edit User
                </h2>
              </div>
              <button
                type="button"
                onClick={closeEditModal}
                disabled={isEditing}
                aria-label="Close dialog"
                className="rounded-btn p-1.5 text-text-muted hover:bg-surface-raised hover:text-text transition-colors min-h-[40px] min-w-[40px] flex items-center justify-center"
              >
                <X size={18} aria-hidden="true" />
              </button>
            </div>

            {editError && (
              <div
                role="alert"
                className="mb-4 flex items-start gap-2 rounded-card border border-red-300 bg-red-50 p-3 text-xs text-red-900 dark:border-red-900/60 dark:bg-red-950/40 dark:text-red-200"
              >
                <AlertCircle size={15} className="text-danger shrink-0 mt-0.5" aria-hidden="true" />
                <div className="leading-relaxed">{editError}</div>
              </div>
            )}

            <form onSubmit={handleEditSubmit} className="space-y-4 flex-1 flex flex-col justify-between" noValidate>
              <div className="space-y-4">
                {/* Email (Readonly reference) */}
                <div>
                  <label className="block text-xs font-semibold text-text-muted mb-1">Email</label>
                  <div className="rounded-input border border-border-subtle bg-surface-raised py-2 px-3 text-sm text-text-muted">
                    {editingUser.email}
                  </div>
                </div>

                {/* Name */}
                <div>
                  <label htmlFor="edit-name" className="block text-xs font-semibold text-text mb-1">
                    Full name <span className="text-danger">*</span>
                  </label>
                  <input
                    id="edit-name"
                    type="text"
                    required
                    value={editName}
                    onChange={(e) => setEditName(e.target.value)}
                    className="w-full rounded-input border border-border bg-background py-2 px-3 text-sm text-text focus:border-accent focus:outline-none focus-visible:ring-2 focus-visible:ring-accent min-h-[40px]"
                  />
                </div>

                {/* Department Dropdown */}
                <div>
                  <label htmlFor="edit-department" className="block text-xs font-semibold text-text mb-1">
                    Department
                  </label>
                  <select
                    id="edit-department"
                    value={editDept}
                    onChange={(e) => setEditDept(e.target.value)}
                    className="w-full rounded-input border border-border bg-background py-2 px-3 text-sm text-text focus:border-accent focus:outline-none focus-visible:ring-2 focus-visible:ring-accent min-h-[40px]"
                  >
                    <option value="">None / Unassigned</option>
                    {allDepartments.map((d) => (
                      <option key={d} value={d}>
                        {d}
                      </option>
                    ))}
                  </select>
                </div>

                {/* Active Toggle */}
                <div>
                  <div className="flex items-center justify-between rounded-card border border-border p-3 bg-background">
                    <div>
                      <div className="text-sm font-semibold text-text">Account Active</div>
                      <div className="text-xs text-text-muted">
                        {editIsActive ? 'User can log in and query documents' : 'User access is blocked'}
                      </div>
                    </div>

                    <label
                      className={`relative inline-flex items-center cursor-pointer ${
                        editingUser.id === currentUser?.id ? 'opacity-40 cursor-not-allowed' : ''
                      }`}
                      title={
                        editingUser.id === currentUser?.id
                          ? 'Admin cannot deactivate themselves'
                          : undefined
                      }
                    >
                      <input
                        type="checkbox"
                        checked={editIsActive}
                        disabled={editingUser.id === currentUser?.id}
                        onChange={(e) => setEditIsActive(e.target.checked)}
                        className="sr-only peer"
                        aria-label="Account active toggle"
                      />
                      <div className="w-11 h-6 bg-border peer-focus:outline-none peer-focus:ring-2 peer-focus:ring-accent rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:width-5 after:transition-all peer-checked:bg-accent"></div>
                    </label>
                  </div>
                </div>

                {/* Optional New Password */}
                <div>
                  <label htmlFor="edit-password" className="block text-xs font-semibold text-text mb-1">
                    New password <span className="text-text-muted font-normal">(optional, min. 8 characters)</span>
                  </label>
                  <div className="relative">
                    <input
                      id="edit-password"
                      type={editShowPassword ? 'text' : 'password'}
                      value={editPassword}
                      onChange={(e) => setEditPassword(e.target.value)}
                      placeholder="Leave blank to keep existing password"
                      className="w-full rounded-input border border-border bg-background py-2 pl-3 pr-10 text-sm text-text focus:border-accent focus:outline-none focus-visible:ring-2 focus-visible:ring-accent min-h-[40px]"
                      autoComplete="new-password"
                    />
                    <button
                      type="button"
                      onClick={() => setEditShowPassword(!editShowPassword)}
                      aria-label={editShowPassword ? 'Hide password' : 'Show password'}
                      className="absolute inset-y-0 right-0 flex items-center pr-3 text-text-muted hover:text-text"
                    >
                      {editShowPassword ? <EyeOff size={16} aria-hidden="true" /> : <Eye size={16} aria-hidden="true" />}
                    </button>
                  </div>
                </div>
              </div>

              {/* Action buttons */}
              <div className="flex items-center justify-end gap-3 pt-6 border-t border-border-subtle mt-6">
                <button
                  type="button"
                  onClick={closeEditModal}
                  disabled={isEditing}
                  className="rounded-btn border border-border bg-surface-raised px-4 py-2 text-sm font-semibold text-text hover:bg-border transition-colors min-h-[40px]"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={isEditing}
                  className="inline-flex items-center justify-center gap-2 rounded-btn bg-accent px-4 py-2 text-sm font-semibold text-accent-contrast shadow-xs hover:bg-accent-hover disabled:opacity-50 transition-colors min-h-[40px] focus-visible:ring-2 focus-visible:ring-accent"
                  data-testid="submit-edit-user"
                >
                  {isEditing ? (
                    <>
                      <Loader2 size={16} className="animate-spin" aria-hidden="true" />
                      <span>Saving...</span>
                    </>
                  ) : (
                    <span>Save Changes</span>
                  )}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* ── DEACTIVATION CONFIRMATION DIALOG ── */}
      {deactivatingUser && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-xs"
          role="dialog"
          aria-modal="true"
          aria-labelledby="deactivate-confirm-title"
        >
          <div className="relative w-full max-w-sm rounded-card border border-border bg-surface p-6 shadow-panel space-y-4 animate-in fade-in zoom-in-95 duration-150">
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-full bg-red-100 dark:bg-red-950/60 text-danger shrink-0">
                <UserX size={20} aria-hidden="true" />
              </div>
              <div>
                <h2 id="deactivate-confirm-title" className="text-base font-bold text-text">
                  Deactivate User
                </h2>
                <p className="text-xs text-text-muted">Are you sure you want to deactivate?</p>
              </div>
            </div>

            <p className="text-xs md:text-sm text-text leading-relaxed">
              Deactivating <strong className="font-semibold text-text">{deactivatingUser.name}</strong> ({deactivatingUser.email}) will immediately revoke their access to VaultRAG. They will not be able to sign in until reactivated.
            </p>

            <div className="flex items-center justify-end gap-2.5 pt-3 border-t border-border-subtle">
              <button
                type="button"
                onClick={() => setDeactivatingUser(null)}
                className="rounded-btn border border-border bg-surface-raised px-3.5 py-2 text-xs font-semibold text-text hover:bg-border transition-colors min-h-[40px]"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={confirmDeactivateUser}
                className="inline-flex items-center justify-center gap-1.5 rounded-btn bg-danger px-3.5 py-2 text-xs font-semibold text-white shadow-xs hover:bg-red-700 transition-colors min-h-[40px] focus-visible:ring-2 focus-visible:ring-danger"
                data-testid="confirm-deactivate-user"
              >
                <UserX size={14} aria-hidden="true" />
                <span>Deactivate user</span>
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ── RESET PASSWORD MODAL ── */}
      {resetPasswordUser && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center p-0 md:p-4 bg-background md:bg-black/50 md:backdrop-blur-xs overflow-y-auto"
          role="dialog"
          aria-modal="true"
          aria-labelledby="reset-password-title"
        >
          <div className="relative flex h-full md:h-auto w-full md:max-w-md flex-col rounded-none md:rounded-card border-0 md:border md:border-border bg-surface p-6 shadow-panel">
            <div className="flex items-center justify-between border-b border-border-subtle pb-4 mb-4">
              <div className="flex items-center gap-2">
                <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-accent text-accent-contrast">
                  <Key size={18} aria-hidden="true" />
                </div>
                <h2 id="reset-password-title" className="text-base font-bold text-text">
                  Reset Password
                </h2>
              </div>
              <button
                type="button"
                onClick={closeResetModal}
                disabled={isResetting}
                aria-label="Close dialog"
                className="rounded-btn p-1.5 text-text-muted hover:bg-surface-raised hover:text-text transition-colors min-h-[40px] min-w-[40px] flex items-center justify-center"
              >
                <X size={18} aria-hidden="true" />
              </button>
            </div>

            <p className="text-xs text-text-muted mb-4">
              Set a new corporate password for <strong className="text-text font-semibold">{resetPasswordUser.name}</strong> ({resetPasswordUser.email}).
            </p>

            {resetError && (
              <div
                role="alert"
                className="mb-4 flex items-start gap-2 rounded-card border border-red-300 bg-red-50 p-3 text-xs text-red-900 dark:border-red-900/60 dark:bg-red-950/40 dark:text-red-200"
              >
                <AlertCircle size={15} className="text-danger shrink-0 mt-0.5" aria-hidden="true" />
                <div className="leading-relaxed">{resetError}</div>
              </div>
            )}

            <form onSubmit={handleResetSubmit} className="space-y-4 flex-1 flex flex-col justify-between" noValidate>
              <div>
                <label htmlFor="reset-new-password" className="block text-xs font-semibold text-text mb-1">
                  New password <span className="text-danger">*</span>{' '}
                  <span className="text-text-muted font-normal">(min. 8 characters)</span>
                </label>
                <div className="relative">
                  <input
                    id="reset-new-password"
                    type={resetShowPassword ? 'text' : 'password'}
                    required
                    value={resetPassword}
                    onChange={(e) => setResetPassword(e.target.value)}
                    placeholder="••••••••••••"
                    className="w-full rounded-input border border-border bg-background py-2 pl-3 pr-10 text-sm text-text focus:border-accent focus:outline-none focus-visible:ring-2 focus-visible:ring-accent min-h-[40px]"
                    autoComplete="new-password"
                  />
                  <button
                    type="button"
                    onClick={() => setResetShowPassword(!resetShowPassword)}
                    aria-label={resetShowPassword ? 'Hide password' : 'Show password'}
                    className="absolute inset-y-0 right-0 flex items-center pr-3 text-text-muted hover:text-text"
                  >
                    {resetShowPassword ? <EyeOff size={16} aria-hidden="true" /> : <Eye size={16} aria-hidden="true" />}
                  </button>
                </div>
              </div>

              <div className="flex items-center justify-end gap-3 pt-6 border-t border-border-subtle mt-6">
                <button
                  type="button"
                  onClick={closeResetModal}
                  disabled={isResetting}
                  className="rounded-btn border border-border bg-surface-raised px-4 py-2 text-sm font-semibold text-text hover:bg-border transition-colors min-h-[40px]"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={isResetting}
                  className="inline-flex items-center justify-center gap-2 rounded-btn bg-accent px-4 py-2 text-sm font-semibold text-accent-contrast shadow-xs hover:bg-accent-hover disabled:opacity-50 transition-colors min-h-[40px] focus-visible:ring-2 focus-visible:ring-accent"
                  data-testid="submit-reset-password"
                >
                  {isResetting ? (
                    <>
                      <Loader2 size={16} className="animate-spin" aria-hidden="true" />
                      <span>Resetting...</span>
                    </>
                  ) : (
                    <span>Update Password</span>
                  )}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
