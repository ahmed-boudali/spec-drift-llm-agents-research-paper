"""
routes.py -- shared route/affordance tables.

Where each control lives, where each sidebar item navigates, and which guard
protects each route. Derived from the specification's navigation map and
cross-checked against the Angular templates and router by extract.py.

Imported by both validator.py and the benchmark generator so that there is a
single source of truth for affordance placement.
"""

SIDEBAR = {
    "dashboard", "finance-menu", "finance-dashboard", "cash",
    "supplier-invoices", "client-invoices", "suppliers", "clients",
    "intelligence", "finance-docs", "timesheet-menu", "ts-projects",
    "ts-tasks", "my-timesheet", "ts-validation", "ts-reporting", "ts-messenger",
}

# Where each sidebar item navigates to. Clicking one changes the current route,
# so a step sequence must be validated against the route the PRECEDING steps
# have navigated to, not against the route the user started on.
SIDEBAR_TARGET = {
    "finance-dashboard": "/finance/dashboard", "cash": "/finance",
    "supplier-invoices": "/finance/invoices",
    "client-invoices": "/finance/client-invoices",
    "suppliers": "/finance/suppliers", "clients": "/finance/clients",
    "intelligence": "/finance/intelligence", "finance-docs": "/finance/documents",
    "ts-projects": "/timesheet/projects", "ts-tasks": "/timesheet/tasks",
    "my-timesheet": "/timesheet/my-timesheet",
    "ts-validation": "/timesheet/validation",
    "ts-reporting": "/timesheet/reporting", "ts-messenger": "/timesheet/messenger",
    # Menu toggles expand a submenu without navigating.
    "finance-menu": None, "timesheet-menu": None, "dashboard": "/dashboard",
}

ROUTE_OF_SELECTOR = {
    "new-invoice": "/finance/invoices", "export-excel": "/finance/invoices",
    "export-pdf": "/finance/invoices", "total-outstanding": "/finance/invoices",
    "total-paid-month": "/finance/invoices", "overdue-risk": "/finance/invoices",
    "upcoming-payments": "/finance/invoices", "edit": "/finance/invoices",
    "validate": "/finance/invoices", "record-payment": "/finance/invoices",
    "cancel": "/finance/invoices", "reset-invoices": "/finance/invoices",
    "focus-invoices": "/finance/invoices",
    "new-client-invoice": "/finance/client-invoices",
    "export-excel-ci": "/finance/client-invoices",
    "export-pdf-ci": "/finance/client-invoices",
    "view-doc-ci": "/finance/client-invoices",
    "validate-ci": "/finance/client-invoices",
    "record-payment-ci": "/finance/client-invoices",
    "cancel-ci": "/finance/client-invoices",
    "reset-invoices-ci": "/finance/client-invoices",
    "new-op": "/finance", "total-inflows": "/finance", "total-outflows": "/finance",
    "net-flow": "/finance", "draft-ops": "/finance", "view-cheque": "/finance",
    "view-avis": "/finance", "edit-op": "/finance", "validate-op": "/finance",
    "cancel-op": "/finance", "cash-settings": "/finance", "export-cash": "/finance",
    "reset-cash": "/finance",
    "create-supplier": "/finance/suppliers", "edit-supplier": "/finance/suppliers",
    "delete-supplier": "/finance/suppliers", "export-suppliers": "/finance/suppliers",
    "reset-suppliers": "/finance/suppliers",
    "create-client": "/finance/clients", "edit-client": "/finance/clients",
    "delete-client": "/finance/clients", "view-client": "/finance/clients",
    "export-clients": "/finance/clients", "reset-clients": "/finance/clients",
    "fd-period": "/finance/dashboard",
    "doc-search": "/finance/documents", "doc-view": "/finance/documents",
    "doc-download": "/finance/documents", "doc-select-all": "/finance/documents",
    "doc-bulk-download": "/finance/documents", "doc-clear-filters": "/finance/documents",
    "export-report-pdf": "/finance/intelligence",
    "new-project": "/timesheet/projects", "reset-projects": "/timesheet/projects",
    "new-task": "/timesheet/tasks", "reset-tasks": "/timesheet/tasks",
    "ts-today": "/timesheet/my-timesheet", "ts-prev-week": "/timesheet/my-timesheet",
    "ts-next-week": "/timesheet/my-timesheet", "ts-add-entry": "/timesheet/my-timesheet",
    "ts-view-mode": "/timesheet/my-timesheet", "ts-resubmit": "/timesheet/my-timesheet",
    "submit-week": "/timesheet/my-timesheet",
    "validate-all": "/timesheet/validation", "refuse-all": "/timesheet/validation",
    "validate-entry": "/timesheet/validation", "refuse-entry": "/timesheet/validation",
    "val-view-mode": "/timesheet/validation",
    "ts-export-excel": "/timesheet/reporting", "ts-export-pdf": "/timesheet/reporting",
    "ms-send": "/timesheet/messenger", "ms-details": "/timesheet/messenger",
    "ms-project": "/timesheet/messenger", "ms-mode": "/timesheet/messenger",
}

# Routes restricted by a guard, mapped to the roles that guard admits.
# Extracted from core/guards/role.guard.ts by extract.py.
GUARD_OF_ROUTE = {
    "/finance": "financeGuard", "/finance/dashboard": "financeGuard",
    "/finance/invoices": "financeGuard", "/finance/client-invoices": "financeGuard",
    "/finance/suppliers": "financeGuard", "/finance/clients": "financeGuard",
    "/finance/intelligence": "financeGuard", "/finance/documents": "financeGuard",
    "/timesheet/projects": "timesheetGuard", "/timesheet/tasks": "timesheetGuard",
    "/timesheet/my-timesheet": "timesheetGuard",
    "/timesheet/messenger": "timesheetGuard",
    "/timesheet/validation": "managerGuard", "/timesheet/reporting": "managerGuard",
}


