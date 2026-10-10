import React, { useState, useEffect, useRef, useCallback } from 'react';
import { api, ApiClientError } from '../api/client';
import {
  DocumentItem,
  DocumentShare,
  GranteeType,
  SharingTargetUser,
} from '../api/types';
import { SegmentedControl, Button } from './ui';
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

function getInitials(name: string): string {
  const parts = name.trim().split(/\s+/);
  if (parts.length >= 2) {
    return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
  }
  return name.slice(0, 2).toUpperCase();
}

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
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-md p-4 animate-scale-in"
      role="dialog"
      aria-modal="true"
      aria-labelledby="share-dialog-title"
      data-testid="share-dialog"
    >
      <div
        ref={dialogRef}
        className="flex flex-col w-full max-w-lg max-h-[90vh] bg-surface rounded-dialog border border-border shadow-xl overflow-hidden"
      >
        {/* Header */}
        <div className="flex items-center justify-between border-b border-border px-6 py-4">
          <div>
            <h2 id="share-dialog-title" className="font-heading text-base font-bold text-text">
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
            className="rounded-btn p-1.5 text-text-muted hover:bg-surface-2 hover:text-text transition-colors"
          >
            <X size={18} aria-hidden="true" />
          </button>
        </div>

        {/* Informative Banner */}
        <div className="bg-primary-soft/60 border-b border-border-subtle px-6 py-3 text-xs text-primary-text flex items-start gap-2.5">
          <ShieldAlert size={16} className="text-primary shrink-0 mt-0.5" aria-hidden="true" />
          <span className="leading-relaxed">
            Only you and platform administrators can see this document until you share it.
          </span>
        </div>

        {/* Body */}
        <div className="flex-1 overflow-y-auto p-6 space-y-5">
          {shareError && (
            <div
              className="flex items-center gap-2 rounded-btn bg-rose-500/10 p-3 text-xs text-danger border border-danger/30"
              role="alert"
              data-testid="share-error-message"
            >
              <AlertCircle size={15} className="shrink-0" />
              <span>{shareError}</span>
            </div>
          )}

          {statusMessage && (
            <div
              className="flex items-center gap-2 rounded-btn bg-emerald-500/10 p-2.5 text-xs text-emerald-700 dark:text-emerald-300 border border-emerald-500/30"
              role="status"
              aria-live="polite"
              data-testid="share-status-message"
            >
              <CheckCircle2 size={15} className="shrink-0" />
              <span>{statusMessage}</span>
            </div>
          )}

          {/* Add Access Section */}
          <div className="space-y-3.5">
            <div className="flex items-center justify-between">
              <label className="block text-xs font-semibold uppercase tracking-wider text-text-muted">
                Grant Access
              </label>
            </div>

            {/* Tab selection: People, Roles, Departments */}
            <SegmentedControl
              value={activeTab}
              onChange={(val) => setActiveTab(val as 'people' | 'roles' | 'departments')}
              options={[
                {
                  value: 'people',
                  label: 'People',
                  icon: <User size={13} />,
                  testId: 'tab-people',
                },
                {
                  value: 'roles',
                  label: 'Roles',
                  icon: <Users size={13} />,
                  testId: 'tab-roles',
                },
                {
                  value: 'departments',
                  label: 'Departments',
                  icon: <Building2 size={13} />,
                  testId: 'tab-departments',
                },
              ]}
              className="w-full justify-between"
            />

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
                    className="w-full rounded-btn border border-border bg-surface-2 px-3.5 py-2 text-xs text-text placeholder-text-muted focus:border-primary focus:outline-hidden transition-colors"
                    data-testid="share-people-search"
                    aria-label="Search people"
                  />
                  {isSearching && (
                    <div className="absolute right-3.5 top-2.5 text-text-muted">
                      <Loader2 size={14} className="animate-spin text-accent" />
                    </div>
                  )}
                </div>

                {/* Autocomplete Results */}
                {searchQuery.length >= 2 && targetUsers.length > 0 && !selectedUser && (
                  <ul
                    className="max-h-40 overflow-y-auto rounded-card border border-border bg-surface p-1 shadow-md divide-y divide-border-subtle"
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
                          className="w-full flex items-center justify-between px-3 py-2 text-left text-xs hover:bg-surface-2 rounded-btn transition-colors"
                          role="option"
                          aria-selected={false}
                        >
                          <div className="flex items-center gap-2.5 truncate">
                            <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-accent text-[10px] font-bold text-accent-contrast">
                              {getInitials(u.name)}
                            </span>
                            <span className="font-medium text-text">{u.name}</span>
                          </div>
                          <span className="text-[10px] text-text-muted bg-surface-2 px-1.5 py-0.5 rounded border border-border">
                            {u.department || 'General'}
                          </span>
                        </button>
                      </li>
                    ))}
                  </ul>
                )}

                {searchQuery.length >= 2 && !isSearching && targetUsers.length === 0 && !selectedUser && (
                  <p className="text-[11px] text-text-muted py-1">No matching users found.</p>
                )}

                {selectedUser && (
                  <div className="flex items-center justify-between p-2.5 rounded-btn bg-primary-soft/40 border border-primary/20 text-xs">
                    <div className="flex items-center gap-2 truncate">
                      <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-primary text-[10px] font-bold text-white">
                        {getInitials(selectedUser.name)}
                      </span>
                      <span className="font-semibold text-text">
                        {selectedUser.name}
                      </span>
                      <span className="text-text-muted">
                        ({selectedUser.department || 'General'})
                      </span>
                    </div>
                    <button
                      type="button"
                      onClick={() => {
                        setSelectedUser(null);
                        setSearchQuery('');
                      }}
                      className="text-text-muted hover:text-text p-1"
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
                  className="w-full rounded-btn border border-border bg-surface-2 px-3 py-2 text-xs text-text focus:border-primary focus:outline-hidden"
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
                  className="w-full rounded-btn border border-border bg-surface-2 px-3 py-2 text-xs text-text focus:border-primary focus:outline-hidden"
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
                    className="rounded-xs border-border text-primary focus:ring-primary"
                    data-testid="share-sensitive-checkbox"
                  />
                  <span>Also share sensitive columns</span>
                </label>
                <p className="text-[10px] text-text-muted ml-5">
                  Allows grantee to view columns designated as sensitive during upload.
                </p>
              </div>
            )}

            <Button
              variant="primary"
              size="md"
              onClick={handleAddShare}
              disabled={
                isSubmitting ||
                (activeTab === 'people' && !selectedUser) ||
                (activeTab === 'roles' && !selectedRole) ||
                (activeTab === 'departments' && !selectedDept)
              }
              loading={isSubmitting}
              className="w-full"
              data-testid="add-share-button"
            >
              Add Access
            </Button>
          </div>

          {/* Current Access List */}
          <div className="space-y-3 pt-3 border-t border-border">
            <h3 className="text-xs font-semibold uppercase tracking-wider text-text-muted">
              Current Access ({shares.length + 1})
            </h3>

            {isLoadingShares ? (
              <div className="py-4 text-center text-xs text-text-muted flex items-center justify-center gap-2">
                <Loader2 size={14} className="animate-spin text-accent" />
                <span>Loading shares...</span>
              </div>
            ) : (
              <ul className="space-y-2" data-testid="current-shares-list">
                {/* Document Owner Row (Always visible, non-removable) */}
                <li className="flex items-center justify-between p-2.5 rounded-btn bg-surface-2 border border-border-subtle text-xs">
                  <div className="flex items-center gap-2.5 min-w-0">
                    <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-accent text-[11px] font-bold text-accent-contrast">
                      {getInitials(document.owner.name)}
                    </span>
                    <div className="truncate">
                      <span className="font-semibold text-text">{document.owner.name}</span>
                      <span className="ml-1.5 text-[10px] text-text-muted font-medium">(Owner)</span>
                    </div>
                  </div>
                  <span className="text-[10px] font-semibold text-text-muted bg-surface px-2 py-0.5 rounded-badge border border-border">
                    Owner
                  </span>
                </li>

                {/* Shares */}
                {shares.map((s) => {
                  let label = s.grantee_value;
                  let icon = (
                    <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-surface-2 text-text-muted border border-border text-[11px] font-bold">
                      {getInitials(s.grantee_value)}
                    </span>
                  );
                  if (s.grantee_type === 'role') {
                    label = `Role: ${s.grantee_value}`;
                    icon = (
                      <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-indigo-500/10 text-indigo-600 dark:text-indigo-400">
                        <Users size={14} />
                      </span>
                    );
                  } else if (s.grantee_type === 'department') {
                    label = `Department: ${s.grantee_value}`;
                    icon = (
                      <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-cyan-500/10 text-cyan-600 dark:text-cyan-400">
                        <Building2 size={14} />
                      </span>
                    );
                  }

                  return (
                    <li
                      key={s.id}
                      className="flex items-center justify-between p-2.5 rounded-btn bg-surface-2 border border-border-subtle text-xs"
                    >
                      <div className="flex items-center gap-2.5 min-w-0">
                        {icon}
                        <div className="truncate">
                          <span className="font-medium text-text">{label}</span>
                          {s.include_sensitive && (
                            <span className="ml-1.5 rounded-badge bg-amber-500/10 text-amber-700 dark:text-amber-400 px-1.5 py-0.5 text-[9px] font-semibold border border-amber-500/20">
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
                        className="rounded-btn p-1.5 text-text-muted hover:text-danger hover:bg-rose-500/10 transition-colors"
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
        <div className="border-t border-border px-6 py-3.5 bg-surface-2/60 flex justify-end">
          <Button variant="secondary" size="sm" onClick={onClose}>
            Done
          </Button>
        </div>
      </div>
    </div>
  );
};
