import React, { useState, useEffect, useRef, useCallback } from 'react';
import { api, ApiClientError } from '../api/client';
import {
  DocumentItem,
  DocumentShare,
  GranteeType,
  SharingTargetUser,
} from '../api/types';
import {
  X,
  User,
  Users,
  Building2,
  Trash2,
  Loader2,
  CheckCircle2,
  AlertCircle,
  ShieldAlert,
} from 'lucide-react';

interface ShareDialogProps {
  document: DocumentItem;
  isOpen: boolean;
  onClose: () => void;
  onShareUpdated?: () => void;
}

export const ShareDialog: React.FC<ShareDialogProps> = ({
  document,
  isOpen,
  onClose,
  onShareUpdated,
}) => {
  const [activeTab, setActiveTab] = useState<'people' | 'roles' | 'departments'>('people');
  const [shares, setShares] = useState<DocumentShare[]>([]);
  const [isLoadingShares, setIsLoadingShares] = useState<boolean>(true);
  const [shareError, setShareError] = useState<string | null>(null);
  const [statusMessage, setStatusMessage] = useState<string | null>(null);

  // People search state
  const [searchQuery, setSearchQuery] = useState('');
  const [targetUsers, setTargetUsers] = useState<SharingTargetUser[]>([]);
  const [availableRoles, setAvailableRoles] = useState<string[]>([]);
  const [availableDepts, setAvailableDepts] = useState<string[]>([]);
  const [isSearching, setIsSearching] = useState(false);
  const [selectedUser, setSelectedUser] = useState<SharingTargetUser | null>(null);

  // Role and Dept select state
  const [selectedRole, setSelectedRole] = useState<string>('');
  const [selectedDept, setSelectedDept] = useState<string>('');

  // Sensitive columns sharing for CSV
  const isCsv = document.kind === 'csv';
  const [includeSensitive, setIncludeSensitive] = useState<boolean>(false);
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);
  const [removingShareId, setRemovingShareId] = useState<string | null>(null);

  const dialogRef = useRef<HTMLDivElement>(null);
  const searchTimeoutRef = useRef<number | null>(null);

  // Load initial targets & shares
  const loadShares = useCallback(async () => {
    setIsLoadingShares(true);
    setShareError(null);
    try {
      const data = await api.getDocumentShares(document.id);
      setShares(data);
    } catch (err: unknown) {
      if (err instanceof ApiClientError && (err.status === 403 || err.status === 404)) {
        setShareError("You can't manage sharing for this document.");
      } else {
        setShareError('Failed to load sharing settings.');
      }
    } finally {
      setIsLoadingShares(false);
    }
  }, [document.id]);

  useEffect(() => {
    if (isOpen) {
      loadShares();
      // Load default targets (roles & departments)
      api
        .getSharingTargets('')
        .then((targets) => {
          setAvailableRoles(targets.roles);
          setAvailableDepts(targets.departments);
          if (targets.roles.length > 0) setSelectedRole(targets.roles[0]);
          if (targets.departments.length > 0) setSelectedDept(targets.departments[0]);
        })
        .catch(() => {});
    } else {
      setSearchQuery('');
      setSelectedUser(null);
      setStatusMessage(null);
      setShareError(null);
      setIncludeSensitive(false);
    }
  }, [isOpen, loadShares]);

  // Handle escape key
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && isOpen) {
        onClose();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, onClose]);

  // Debounced search for People
  useEffect(() => {
    if (searchTimeoutRef.current) {
      clearTimeout(searchTimeoutRef.current);
    }
    const q = searchQuery.trim();
    if (q.length < 2) {
      setTargetUsers([]);
      setIsSearching(false);
      return;
    }

    setIsSearching(true);
    searchTimeoutRef.current = window.setTimeout(async () => {
      try {
        const res = await api.getSharingTargets(q);
        // Exclude document owner
        const filtered = res.users.filter((u) => u.id !== document.owner.id);
        setTargetUsers(filtered);
      } catch {
        setTargetUsers([]);
      } finally {
        setIsSearching(false);
      }
    }, 300);

    return () => {
      if (searchTimeoutRef.current) {
        clearTimeout(searchTimeoutRef.current);
      }
    };
  }, [searchQuery, document.owner.id]);

  const handleAddShare = async () => {
    let granteeType: GranteeType = 'user';
    let value = '';
    let displayName = '';

    if (activeTab === 'people') {
      if (!selectedUser) return;
      granteeType = 'user';
      value = selectedUser.id;
      displayName = selectedUser.name;
    } else if (activeTab === 'roles') {
      if (!selectedRole) return;
      granteeType = 'role';
      value = selectedRole;
      displayName = `Role: ${selectedRole}`;
    } else if (activeTab === 'departments') {
      if (!selectedDept) return;
      granteeType = 'department';
      value = selectedDept;
      displayName = `Department: ${selectedDept}`;
    }

    setIsSubmitting(true);
    setShareError(null);
    setStatusMessage(null);

    try {
      const newShare = await api.createDocumentShare(document.id, {
        grantee_type: granteeType,
        value,
        include_sensitive: isCsv ? includeSensitive : false,
      });
      setShares((prev) => [...prev, newShare]);
      setStatusMessage(`Shared with ${displayName}`);
      setSelectedUser(null);
      setSearchQuery('');
      if (onShareUpdated) onShareUpdated();
    } catch (err: unknown) {
      if (err instanceof ApiClientError && (err.status === 403 || err.status === 404)) {
        setShareError("You can't manage sharing for this document.");
      } else if (err instanceof ApiClientError && err.status === 409) {
        setShareError('This user or group already has access.');
      } else {
        setShareError(err instanceof Error ? err.message : 'Failed to grant share.');
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleRemoveShare = async (shareId: string) => {
    setRemovingShareId(shareId);
    setShareError(null);
    setStatusMessage(null);
    try {
      await api.deleteDocumentShare(document.id, shareId);
      setShares((prev) => prev.filter((s) => s.id !== shareId));
      setStatusMessage('Access removed');
      if (onShareUpdated) onShareUpdated();
    } catch (err: unknown) {
      if (err instanceof ApiClientError && (err.status === 403 || err.status === 404)) {
        setShareError("You can't manage sharing for this document.");
      } else {
        setShareError('Failed to remove access.');
      }
    } finally {
      setRemovingShareId(null);
    }
  };

  if (!isOpen) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-xs p-4"
      role="dialog"
      aria-modal="true"
      aria-labelledby="share-dialog-title"
      data-testid="share-dialog"
    >
      <div
        ref={dialogRef}
        className="flex flex-col w-full max-w-lg max-h-[90vh] bg-surface rounded-card border border-border shadow-raised overflow-hidden"
      >
        {/* Header */}
        <div className="flex items-center justify-between border-b border-border px-5 py-4">
          <div>
            <h2 id="share-dialog-title" className="text-base font-semibold text-text">
              Share Document
            </h2>
            <p className="text-xs text-text-muted mt-0.5 truncate max-w-sm">
              {document.filename}
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close share dialog"
            className="rounded-btn p-1.5 text-text-muted hover:bg-surface-raised hover:text-text transition-colors"
          >
            <X size={18} aria-hidden="true" />
          </button>
        </div>

        {/* Informative Banner */}
        <div className="bg-surface-raised/70 border-b border-border-subtle px-5 py-3 text-xs text-text-muted flex items-start gap-2">
          <ShieldAlert size={15} className="text-accent shrink-0 mt-0.5" aria-hidden="true" />
          <span>
            Only you and platform administrators can see this document until you share it.
          </span>
        </div>

        {/* Body */}
        <div className="flex-1 overflow-y-auto p-5 space-y-5">
          {shareError && (
            <div
              className="flex items-center gap-2 rounded-btn bg-red-50 p-3 text-xs text-danger dark:bg-red-950/40 border border-red-200 dark:border-red-900"
              role="alert"
              data-testid="share-error-message"
            >
              <AlertCircle size={15} className="shrink-0" />
              <span>{shareError}</span>
            </div>
          )}

          {statusMessage && (
            <div
              className="flex items-center gap-2 rounded-btn bg-emerald-50 p-2.5 text-xs text-emerald-800 dark:bg-emerald-950/40 dark:text-emerald-300 border border-emerald-200 dark:border-emerald-800"
              role="status"
              aria-live="polite"
              data-testid="share-status-message"
            >
              <CheckCircle2 size={15} className="shrink-0" />
              <span>{statusMessage}</span>
            </div>
          )}

          {/* Add Access Section */}
          <div className="space-y-3">
            <label className="block text-xs font-semibold uppercase tracking-wider text-text-muted">
              Grant Access
            </label>

            {/* Tab selection: People, Roles, Departments */}
            <div className="flex border-b border-border">
              <button
                type="button"
                onClick={() => setActiveTab('people')}
                className={`flex items-center gap-1.5 px-3 py-2 text-xs font-medium border-b-2 transition-colors ${
                  activeTab === 'people'
                    ? 'border-accent text-accent'
                    : 'border-transparent text-text-muted hover:text-text'
                }`}
                data-testid="tab-people"
              >
                <User size={14} aria-hidden="true" />
                <span>People</span>
              </button>
              <button
                type="button"
                onClick={() => setActiveTab('roles')}
                className={`flex items-center gap-1.5 px-3 py-2 text-xs font-medium border-b-2 transition-colors ${
                  activeTab === 'roles'
                    ? 'border-accent text-accent'
                    : 'border-transparent text-text-muted hover:text-text'
                }`}
                data-testid="tab-roles"
              >
                <Users size={14} aria-hidden="true" />
                <span>Roles</span>
              </button>
              <button
                type="button"
                onClick={() => setActiveTab('departments')}
                className={`flex items-center gap-1.5 px-3 py-2 text-xs font-medium border-b-2 transition-colors ${
                  activeTab === 'departments'
                    ? 'border-accent text-accent'
                    : 'border-transparent text-text-muted hover:text-text'
                }`}
                data-testid="tab-departments"
              >
                <Building2 size={14} aria-hidden="true" />
                <span>Departments</span>
              </button>
            </div>

            {/* Tab Content */}
            {activeTab === 'people' && (
              <div className="space-y-2">
                <div className="relative">
                  <input
                    type="text"
                    value={searchQuery}
                    onChange={(e) => {
                      setSearchQuery(e.target.value);
                      setSelectedUser(null);
                    }}
                    placeholder="Search people by name..."
                    className="w-full rounded-btn border border-border bg-background px-3 py-2 text-xs text-text placeholder-text-muted focus:border-accent focus:outline-hidden"
                    data-testid="share-people-search"
                    aria-label="Search people"
                  />
                  {isSearching && (
                    <div className="absolute right-3 top-2.5 text-text-muted">
                      <Loader2 size={14} className="animate-spin" />
                    </div>
                  )}
                </div>

                {/* Autocomplete Results */}
                {searchQuery.length >= 2 && targetUsers.length > 0 && !selectedUser && (
                  <ul
                    className="max-h-36 overflow-y-auto rounded-card border border-border bg-surface p-1 shadow-xs divide-y divide-border-subtle"
                    role="listbox"
                    aria-label="Matching users"
                    data-testid="people-results-list"
                  >
                    {targetUsers.map((u) => (
                      <li key={u.id}>
                        <button
                          type="button"
                          onClick={() => {
                            setSelectedUser(u);
                            setSearchQuery(u.name);
                          }}
                          className="w-full flex items-center justify-between px-2.5 py-1.5 text-left text-xs hover:bg-surface-raised rounded-btn transition-colors"
                          role="option"
                          aria-selected={false}
                        >
                          <span className="font-medium text-text">{u.name}</span>
                          <span className="text-[10px] text-text-muted">{u.department || 'General'}</span>
                        </button>
                      </li>
                    ))}
                  </ul>
                )}

                {searchQuery.length >= 2 && !isSearching && targetUsers.length === 0 && !selectedUser && (
                  <p className="text-[11px] text-text-muted py-1">No matching users found.</p>
                )}

                {selectedUser && (
                  <div className="flex items-center justify-between p-2 rounded-btn bg-accent/10 border border-accent/20 text-xs">
                    <span className="font-medium text-text">
                      Selected: {selectedUser.name} ({selectedUser.department || 'General'})
                    </span>
                    <button
                      type="button"
                      onClick={() => {
                        setSelectedUser(null);
                        setSearchQuery('');
                      }}
                      className="text-text-muted hover:text-text"
                    >
                      <X size={13} />
                    </button>
                  </div>
                )}
              </div>
            )}

            {activeTab === 'roles' && (
              <div className="space-y-1">
                <label htmlFor="select-role" className="text-xs text-text-muted">
                  Choose role to grant access:
                </label>
                <select
                  id="select-role"
                  value={selectedRole}
                  onChange={(e) => setSelectedRole(e.target.value)}
                  className="w-full rounded-btn border border-border bg-background px-3 py-2 text-xs text-text focus:border-accent focus:outline-hidden"
                  data-testid="share-role-select"
                >
                  {(availableRoles.length > 0
                    ? availableRoles
                    : ['employee', 'manager', 'hr_admin', 'finance_admin']
                  ).map((r) => (
                    <option key={r} value={r}>
                      {r.replace('_', ' ').toUpperCase()}
                    </option>
                  ))}
                </select>
              </div>
            )}

            {activeTab === 'departments' && (
              <div className="space-y-1">
                <label htmlFor="select-dept" className="text-xs text-text-muted">
                  Choose department to grant access:
                </label>
                <select
                  id="select-dept"
                  value={selectedDept}
                  onChange={(e) => setSelectedDept(e.target.value)}
                  className="w-full rounded-btn border border-border bg-background px-3 py-2 text-xs text-text focus:border-accent focus:outline-hidden"
                  data-testid="share-dept-select"
                >
                  {(availableDepts.length > 0
                    ? availableDepts
                    : ['Engineering', 'Sales', 'HR', 'Finance']
                  ).map((d) => (
                    <option key={d} value={d}>
                      {d}
                    </option>
                  ))}
                </select>
              </div>
            )}

            {/* CSV Sensitive Columns Checkbox */}
            {isCsv && (
              <div className="pt-1">
                <label className="flex items-center gap-2 text-xs text-text cursor-pointer select-none">
                  <input
                    type="checkbox"
                    checked={includeSensitive}
                    onChange={(e) => setIncludeSensitive(e.target.checked)}
                    className="rounded-xs border-border text-accent focus:ring-accent"
                    data-testid="share-sensitive-checkbox"
                  />
                  <span>Also share sensitive columns</span>
                </label>
                <p className="text-[10px] text-text-muted ml-5">
                  Allows grantee to view columns designated as sensitive during upload.
                </p>
              </div>
            )}

            <button
              type="button"
              onClick={handleAddShare}
              disabled={
                isSubmitting ||
                (activeTab === 'people' && !selectedUser) ||
                (activeTab === 'roles' && !selectedRole) ||
                (activeTab === 'departments' && !selectedDept)
              }
              className="w-full rounded-btn bg-accent py-2 px-3 text-xs font-medium text-accent-contrast hover:bg-accent-hover disabled:opacity-50 transition-colors flex items-center justify-center gap-1.5 shadow-xs"
              data-testid="add-share-button"
            >
              {isSubmitting ? (
                <>
                  <Loader2 size={14} className="animate-spin" />
                  <span>Granting...</span>
                </>
              ) : (
                <span>Add Access</span>
              )}
            </button>
          </div>

          {/* Current Access List */}
          <div className="space-y-3 pt-3 border-t border-border">
            <h3 className="text-xs font-semibold uppercase tracking-wider text-text-muted">
              Current Access ({shares.length + 1})
            </h3>

            {isLoadingShares ? (
              <div className="py-4 text-center text-xs text-text-muted flex items-center justify-center gap-2">
                <Loader2 size={14} className="animate-spin" />
                <span>Loading shares...</span>
              </div>
            ) : (
              <ul className="space-y-2" data-testid="current-shares-list">
                {/* Document Owner Row (Always visible, non-removable) */}
                <li className="flex items-center justify-between p-2.5 rounded-btn bg-surface-raised border border-border-subtle text-xs">
                  <div className="flex items-center gap-2 min-w-0">
                    <User size={15} className="text-accent shrink-0" />
                    <div className="truncate">
                      <span className="font-medium text-text">{document.owner.name}</span>
                      <span className="ml-1.5 text-[10px] text-text-muted">(Owner)</span>
                    </div>
                  </div>
                  <span className="text-[11px] font-medium text-text-muted">Owner</span>
                </li>

                {/* Shares */}
                {shares.map((s) => {
                  let label = s.grantee_value;
                  let icon = <User size={15} className="text-text-muted shrink-0" />;
                  if (s.grantee_type === 'role') {
                    label = `Role: ${s.grantee_value}`;
                    icon = <Users size={15} className="text-text-muted shrink-0" />;
                  } else if (s.grantee_type === 'department') {
                    label = `Department: ${s.grantee_value}`;
                    icon = <Building2 size={15} className="text-text-muted shrink-0" />;
                  }

                  return (
                    <li
                      key={s.id}
                      className="flex items-center justify-between p-2.5 rounded-btn bg-surface-raised border border-border-subtle text-xs"
                    >
                      <div className="flex items-center gap-2 min-w-0">
                        {icon}
                        <div className="truncate">
                          <span className="font-medium text-text">{label}</span>
                          {s.include_sensitive && (
                            <span className="ml-1.5 rounded-xs bg-amber-500/10 text-amber-700 dark:text-amber-400 px-1 py-0.5 text-[9px] font-medium">
                              Sensitive included
                            </span>
                          )}
                        </div>
                      </div>

                      <button
                        type="button"
                        onClick={() => handleRemoveShare(s.id)}
                        disabled={removingShareId === s.id}
                        aria-label={`Remove access for ${label}`}
                        className="rounded-btn p-1 text-text-muted hover:text-danger hover:bg-red-50 dark:hover:bg-red-950/40 transition-colors"
                        data-testid={`remove-share-${s.id}`}
                      >
                        {removingShareId === s.id ? (
                          <Loader2 size={14} className="animate-spin text-danger" />
                        ) : (
                          <Trash2 size={14} />
                        )}
                      </button>
                    </li>
                  );
                })}
              </ul>
            )}
          </div>
        </div>

        {/* Footer */}
        <div className="border-t border-border px-5 py-3 bg-surface-raised/40 flex justify-end">
          <button
            type="button"
            onClick={onClose}
            className="rounded-btn border border-border bg-surface px-4 py-1.5 text-xs font-medium text-text hover:bg-border transition-colors"
          >
            Done
          </button>
        </div>
      </div>
    </div>
  );
};
