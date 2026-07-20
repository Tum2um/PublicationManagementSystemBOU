# BOU PMS Frontend

This is the active browser frontend for the Publication Management System.
It is dependency-free HTML, CSS, and JavaScript and communicates with the
Django API in `backend/`.

## Run

From the project root:

```bash
python3 setup_local.py
python3 run_all.py
```

Then open:

```text
http://127.0.0.1:3000
```

## Local Login

The frontend has no public registration page. Accounts are created by the System Admin.

For local development, the Django backend seeds this account:

```text
Email: admin@bou.or.ug
Password: Admin123!
```
