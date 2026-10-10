import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { ShareDialog } from '../components/ShareDialog';
import { api, ApiClientError } from '../api/client';
import { DocumentItem, DocumentShare, SharingTargets } from '../api/types';

describe('ShareDialog Component', () => {
  const dummyDoc: DocumentItem = {
    id: 'doc-123',
    filename: 'financial_summary.csv',
    kind: 'csv',
    status: 'ready',
    reason_code: null,
    size_bytes: 4096,
    created_at: new Date().toISOString(),
    owner: { id: 'u-1', name: 'Asha Patel' },
    shared_with_count: 1,
    can_manage: true,
  };

  const initialShares: DocumentShare[] = [
    {
      id: 'share-1',
      grantee_type: 'user',
      grantee_value: 'Neha Sharma',
      include_sensitive: false,
      created_at: new Date().toISOString(),
      granted_by: 'u-1',
    },
  ];

  const dummyTargets: SharingTargets = {
    users: [
      { id: 'u-2', name: 'Neha Sharma', department: 'Executive' },
      { id: 'u-3', name: 'Vikram Singh', department: 'Finance' },
    ],
    roles: ['analyst', 'manager', 'admin'],
    departments: ['Executive', 'Finance', 'Engineering'],
  };

  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it('1. renders statement banner and current access list without exposing ACL tokens', async () => {
    vi.spyOn(api, 'getDocumentShares').mockResolvedValue(initialShares);
    vi.spyOn(api, 'getSharingTargets').mockResolvedValue(dummyTargets);

    render(
      <ShareDialog
        document={dummyDoc}
        isOpen={true}
        onClose={vi.fn()}
      />
    );

    await waitFor(() => {
      expect(
        screen.getByText('Only you and platform administrators can see this document until you share it.')
      ).toBeInTheDocument();
      expect(screen.getByText('Neha Sharma')).toBeInTheDocument();
    });

    // Verify no ACL tokens or raw permission strings are exposed in the DOM
    expect(document.body.innerHTML).not.toContain('acl_token');
    expect(document.body.innerHTML).not.toContain('perm:');
  });

  it('2. adds access via debounced user search and shows "Shared with <name>"', async () => {
    vi.spyOn(api, 'getDocumentShares').mockResolvedValue([]);
    const targetsSpy = vi.spyOn(api, 'getSharingTargets').mockResolvedValue(dummyTargets);
    const createShareSpy = vi.spyOn(api, 'createDocumentShare').mockResolvedValue({
      id: 'share-new',
      grantee_type: 'user',
      grantee_value: 'u-3',
      include_sensitive: true,
      created_at: new Date().toISOString(),
      granted_by: 'u-1',
    });

    render(
      <ShareDialog
        document={dummyDoc}
        isOpen={true}
        onClose={vi.fn()}
      />
    );

    await waitFor(() => {
      expect(screen.getByTestId('share-people-search')).toBeInTheDocument();
    });

    const searchInput = screen.getByTestId('share-people-search');
    fireEvent.change(searchInput, { target: { value: 'Vi' } });

    // Wait 350ms for debounce
    await new Promise((r) => setTimeout(r, 350));

    expect(targetsSpy).toHaveBeenCalledWith('Vi');

    // Click on Vikram Singh from autocomplete options
    const option = await screen.findByText('Vikram Singh');
    fireEvent.click(option);

    // Check sensitive checkbox (since doc is CSV)
    const sensCheckbox = screen.getByTestId('share-sensitive-checkbox');
    fireEvent.click(sensCheckbox);

    // Click Add access
    const addBtn = screen.getByTestId('add-share-button');
    fireEvent.click(addBtn);

    await waitFor(() => {
      expect(createShareSpy).toHaveBeenCalledWith('doc-123', {
        grantee_type: 'user',
        value: 'u-3',
        include_sensitive: true,
      });
      expect(screen.getByText('Shared with Vikram Singh')).toBeInTheDocument();
    });
  });

  it('3. removes share immediately and announces "Access removed"', async () => {
    vi.spyOn(api, 'getDocumentShares').mockResolvedValue(initialShares);
    vi.spyOn(api, 'getSharingTargets').mockResolvedValue(dummyTargets);
    const deleteSpy = vi.spyOn(api, 'deleteDocumentShare').mockResolvedValue(undefined);

    render(
      <ShareDialog
        document={dummyDoc}
        isOpen={true}
        onClose={vi.fn()}
      />
    );

    await waitFor(() => {
      expect(screen.getByText('Neha Sharma')).toBeInTheDocument();
    });

    const removeBtn = screen.getByTestId('remove-share-share-1');
    fireEvent.click(removeBtn);

    await waitFor(() => {
      expect(deleteSpy).toHaveBeenCalledWith('doc-123', 'share-1');
      expect(screen.getByText('Access removed')).toBeInTheDocument();
      expect(screen.queryByText('Neha Sharma')).toBeNull();
    });
  });

  it('4. shows neutral error message when user cannot manage sharing (403/404)', async () => {
    vi.spyOn(api, 'getDocumentShares').mockRejectedValue(
      new ApiClientError(403, 'Forbidden')
    );
    vi.spyOn(api, 'getSharingTargets').mockResolvedValue(dummyTargets);

    render(
      <ShareDialog
        document={dummyDoc}
        isOpen={true}
        onClose={vi.fn()}
      />
    );

    await waitFor(() => {
      expect(
        screen.getByText("You can't manage sharing for this document.")
      ).toBeInTheDocument();
    });
  });
});
