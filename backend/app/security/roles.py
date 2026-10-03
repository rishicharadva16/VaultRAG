"""
Central role definitions for VaultRAG.

Roles:
- employee: Regular staff. Own data only plus all-staff policies.
- manager: Line manager. Own data + direct reports' expenses; contracts.
- hr_admin: HR. All employee master data, salaries, board minutes, ID proofs.
- finance_admin: Finance. Salaries, all expenses, contracts, invoices, board minutes, finance memos.
- admin: Platform administration only (user management, audit).
  Does NOT appear in any document ACL and cannot read documents through RAG.
"""

ROLES = {"employee", "manager", "hr_admin", "finance_admin", "admin"}
