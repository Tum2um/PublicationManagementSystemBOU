# Frontend

The active browser client is a dependency-free single-page application built
with HTML, CSS, and vanilla JavaScript.

- `index.html` provides the application mount point.
- `app.js` contains API access, session state, role navigation, views, forms,
  and event handlers.
- `styles.css` contains the shared design system and responsive layouts.
- `assets/` contains static visual assets.

The frontend never decides whether an operation is authorized. Its role checks
only control navigation and presentation; Django enforces every permission.
Authentication uses an HTTP-only cookie, so JavaScript must make API requests
with `credentials: "include"` and must never store a session token.

Run the frontend and backend together from the repository root:

```bash
python3 setup_local.py
python3 run_all.py
```

See the project-level [README](../README.md) for installation, configuration,
workflow, security, testing, API, and deployment documentation.
