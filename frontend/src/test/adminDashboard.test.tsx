import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import { AdminDashboardPage } from '../pages/AdminDashboardPage';
import { AdminRouteGuard } from '../auth/AdminRouteGuard';
import { api } from '../api/client';
import * as AuthContextModule from '../auth/AuthContext';
import { AuditSummary, AdminQueryLog, AdminUploadItem, User } from '../api/types';

describe('Admin Dashboard and AdminRouteGuard', () => {
  const dummyAdminUser: User = {
    id: 'u-admin',
    name: 'Admin User',
    email: 'admin@northwind.example',
    roles: ['admin'],
    employee_id: 'E0001',
    department: 'IT',
    external_id: 'u_admin',
  };

  const dummyRegularUser: User = {
    id: 'u-employee',
    name: 'Regular Employee',
    email: 'employee@northwind.example',
    roles: ['employee'],
    employee_id: 'E1001',
    department: 'Sales',
    external_id: 'u_employee',
  };

  const sampleSummary: AuditSummary = {
    days: 7,
    totals: {
      asks: 42,
      searches: 18,
      refusals: 5,
      refusal_rate: 0.119,
      avg_latency_ms: 320.5,
      p95_latency_ms: 780.0,
      uploads: 12,
      active_users: 6,
    },
    per_day_series: [
      { date: '2026-10-08', asks: 20, refusals: 2, searches: 8, uploads: 5 },
      { date: '2026-10-09', asks: 22, refusals: 3, searches: 10, uploads: 7 },
    ],
    counts_by_reason_code: {
      acl_denied: 3,
      no_relevant_chunks: 2,
    },
    top_users: [
      { name: 'Asha Patel', count: 25 },
      { name: 'Vikram Singh', count: 17 },
    ],
  };

  const sampleQueries: AdminQueryLog[] = [
    {
      time: new Date().toISOString(),
      user_name: 'Asha Patel',
      event_type: 'ask',
      refused: false,
      reason_code: null,
      latency_ms: 310.2,
      chunk_count: 3,
      admin_access: false,
      question_hash: 'a1b2c3d4e5f6',
      question_length: 45,
    },
    {
      time: new Date().toISOString(),
      user_name: 'Neha Sharma',
      event_type: 'ask',
      refused: true,
      reason_code: 'acl_denied',
      latency_ms: 85.0,
      chunk_count: 0,
      admin_access: false,
      question_hash: 'f9e8d7c6b5a4',
      question_length: 32,
    },
  ];

  const sampleUploads: AdminUploadItem[] = [
    {
      id: 'doc-1',
      filename: 'contract.pdf',
      kind: 'pdf',
      status: 'ready',
      size_bytes: 50000,
      owner: { id: 'u-1', name: 'Asha Patel' },
      shared_with_count: 2,
      deleted: false,
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    },
  ];

  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it('1. AdminRouteGuard renders neutral NotFoundPage for non-admin users', () => {
    vi.spyOn(AuthContextModule, 'useAuth').mockReturnValue({
      user: dummyRegularUser,
      isLoading: false,
      error: null,
      login: vi.fn(),
      logout: vi.fn(),
      switchDemoUser: vi.fn(),
      clearError: vi.fn(),
      setError: vi.fn(),
    });

    render(
      <MemoryRouter initialEntries={['/admin']}>
        <Routes>
          <Route
            path="/admin"
            element={
              <AdminRouteGuard>
                <div>Secret Admin Dashboard</div>
              </AdminRouteGuard>
            }
          />
        </Routes>
      </MemoryRouter>
    );

    // Standing rule: non-admins see the same neutral not-found page
    expect(screen.queryByText('Secret Admin Dashboard')).toBeNull();
    expect(screen.getByText('Page not found')).toBeInTheDocument();
    expect(screen.getByText('The page you are looking for does not exist or has been moved.')).toBeInTheDocument();
  });

  it('2. AdminRouteGuard renders dashboard for users with admin role', async () => {
    vi.spyOn(AuthContextModule, 'useAuth').mockReturnValue({
      user: dummyAdminUser,
      isLoading: false,
      error: null,
      login: vi.fn(),
      logout: vi.fn(),
      switchDemoUser: vi.fn(),
      clearError: vi.fn(),
      setError: vi.fn(),
    });

    vi.spyOn(api, 'getAdminAuditSummary').mockResolvedValue(sampleSummary);
    vi.spyOn(api, 'getAdminQueries').mockResolvedValue(sampleQueries);
    vi.spyOn(api, 'getAdminUploads').mockResolvedValue(sampleUploads);

    render(
      <MemoryRouter initialEntries={['/admin']}>
        <Routes>
          <Route
            path="/admin"
            element={
              <AdminRouteGuard>
                <AdminDashboardPage />
              </AdminRouteGuard>
            }
          />
        </Routes>
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText('Admin Dashboard')).toBeInTheDocument();
    });

    // Check KPI metrics rendered
    expect(screen.getByTestId('kpi-total-asks')).toHaveTextContent('42');
    expect(screen.getByTestId('kpi-refusal-rate')).toHaveTextContent('11.9%');
    expect(screen.getByTestId('kpi-avg-latency')).toHaveTextContent('321 ms');
    expect(screen.getByTestId('kpi-uploads')).toHaveTextContent('12');
    expect(screen.getByTestId('kpi-active-users')).toHaveTextContent('6');
  });

  it('3. Recent queries table never displays raw question text (displays hash and length only)', async () => {
    vi.spyOn(AuthContextModule, 'useAuth').mockReturnValue({
      user: dummyAdminUser,
      isLoading: false,
      error: null,
      login: vi.fn(),
      logout: vi.fn(),
      switchDemoUser: vi.fn(),
      clearError: vi.fn(),
      setError: vi.fn(),
    });

    vi.spyOn(api, 'getAdminAuditSummary').mockResolvedValue(sampleSummary);
    vi.spyOn(api, 'getAdminQueries').mockResolvedValue(sampleQueries);
    vi.spyOn(api, 'getAdminUploads').mockResolvedValue(sampleUploads);

    render(
      <MemoryRouter initialEntries={['/admin']}>
        <Routes>
          <Route
            path="/admin"
            element={
              <AdminRouteGuard>
                <AdminDashboardPage />
              </AdminRouteGuard>
            }
          />
        </Routes>
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText('Recent Queries (Audit Log)')).toBeInTheDocument();
    });

    // Hash substring should be visible
    expect(screen.getByText(/a1b2c3d4/i)).toBeInTheDocument();
    expect(screen.getByText(/45 chars/i)).toBeInTheDocument();

    // Confirm that no raw prompt text exists in HTML
    expect(document.body.innerHTML).not.toContain('What are the executive salaries?');
    expect(document.body.innerHTML).not.toContain('raw_prompt');
  });

  it('4. toggles between SVG chart and accessible table view', async () => {
    vi.spyOn(AuthContextModule, 'useAuth').mockReturnValue({
      user: dummyAdminUser,
      isLoading: false,
      error: null,
      login: vi.fn(),
      logout: vi.fn(),
      switchDemoUser: vi.fn(),
      clearError: vi.fn(),
      setError: vi.fn(),
    });

    vi.spyOn(api, 'getAdminAuditSummary').mockResolvedValue(sampleSummary);
    vi.spyOn(api, 'getAdminQueries').mockResolvedValue(sampleQueries);
    vi.spyOn(api, 'getAdminUploads').mockResolvedValue(sampleUploads);

    render(
      <MemoryRouter initialEntries={['/admin']}>
        <Routes>
          <Route
            path="/admin"
            element={
              <AdminRouteGuard>
                <AdminDashboardPage />
              </AdminRouteGuard>
            }
          />
        </Routes>
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText('Activity Overview (Per Day)')).toBeInTheDocument();
    });

    // Default: SVG chart is rendered
    expect(screen.getByRole('img', { name: /Activity timeline chart/i })).toBeInTheDocument();

    // Click toggle to table view
    const toggleBtn = screen.getByTestId('toggle-chart-table-button');
    fireEvent.click(toggleBtn);

    // Now accessible table fallback is rendered
    expect(screen.getByRole('table', { name: /Daily asks and refusals activity table/i })).toBeInTheDocument();
  });
});
