import { Role } from '../api/types';

export function formatRoleLabel(role: Role): string {
  switch (role) {
    case 'admin':
      return 'Administrator';
    case 'hr_admin':
      return 'HR Admin';
    case 'finance_admin':
      return 'Finance Admin';
    case 'manager':
      return 'Manager';
    case 'employee':
      return 'Employee';
    default:
      return role;
  }
}

export function formatLatency(latencyMs: number): string {
  if (latencyMs < 1000) {
    return `${Math.round(latencyMs)} ms`;
  }
  return `${(latencyMs / 1000).toFixed(2)} s`;
}

export function formatSourceLabel(file: string, page?: number | null, rowId?: string | null): string {
  if (page !== null && page !== undefined) {
    return `${file} • p. ${page}`;
  }
  if (rowId) {
    return `${file} • row ${rowId}`;
  }
  return file;
}
