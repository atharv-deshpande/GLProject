# Initial EKIP departments and users

Run from the backend directory after applying migrations:

```powershell
alembic upgrade head
```

Set initial passwords in the current PowerShell session. Use the provided onboarding passwords locally if these are your intended initial passwords; they are not stored in source control.

```powershell
$env:USER_MUKESH_JHA_PASSWORD = Read-Host "Password for Mukesh"
$env:USER_CHETAN_SINHA_PASSWORD = Read-Host "Password for Chetan"
$env:USER_RAHUL_SHINDE_PASSWORD = Read-Host "Password for Rahul"
$env:USER_MUKTA_DOSHI_PASSWORD = Read-Host "Password for Mukta"
$env:USER_RAMESH_SETH_PASSWORD = Read-Host "Password for Ramesh (Admin)"
$env:USER_RUPALI_RAO_PASSWORD = Read-Host "Password for Rupali"
$env:USER_MAYANK_IYER_PASSWORD = Read-Host "Password for Mayank"
python scripts/seed_initial_organization.py
```

Passwords are hashed using Argon2 before persistence. Do not commit plaintext passwords or put them in shared shell history. Change onboarding passwords after first login.

## Departments
- Ethics and Compliance — ETHICS_COMPLIANCE
- Human resource — HUMAN_RESOURCE
- Finance and auditing — FINANCE_AUDITING
- Facility and safety — FACILITY_SAFETY
- Legal and risk — LEGAL_RISK
- Information technology and security — IT_SECURITY
- Marketing, Investor relations and Communications — MARKETING_IR_COMMUNICATIONS
- AI usage — AI_USAGE

## Accounts and role mapping
- Mukesh.jha@abcerp.com — USER
- Chetan.sinha@abcerp.com — DEPARTMENT_MANAGER
- Rahul.shinde@abcerp.com — USER
- Mukta.doshi@abcerp.com — USER
- Ramesh.seth@abcerp.com — ADMIN
- Rupali.rao@abcerp.com — DEPARTMENT_MANAGER
- Mayank.iyer@abcerp.com — USER

Chetan and Rupali are assigned to Human resource because their supplied role is HR. Employee accounts are created without department memberships; assign them to their real departments through the admin API. No employee department was inferred.

The seeder is safe to rerun: it does not overwrite existing users' roles or passwords, and only adds missing departments, users and memberships.
