# Testing the Frontend & Domain Migration

This guide explains how to verify the migration of the Astro marketing site to `airsports.no` and the main application to `app.airsports.no` on your local machine.

## 1. Local DNS Setup
To simulate the production environment, you need to map the production domains to your local loopback address.

Add the following lines to your system's `hosts` file:
*   **Linux/Mac:** `/etc/hosts`
*   **Windows:** `C:\Windows\System32\drivers\etc\hosts`

```text
127.0.0.1 airsports.no
127.0.0.1 app.airsports.no
127.0.0.1 www.airsports.no
```

## 2. Build the Static Assets
You can now build both the React app and the Marketing site from the root directory using the new helper scripts:

```bash
# To build everything at once:
npm run build:all

# Or build specifically:
npm run build:marketing
npm run build:react
```

If you are using the **Dev Container**, the dependencies for the marketing site are now installed automatically when the container is created.

## 3. Start the Application
Run the Django development server inside your dev container. Because your `docker-compose.yml` maps host `8002` to container `8000`, you must bind to `8000` inside the container:

```bash
# From the /src directory INSIDE the container
python manage.py runserver 0.0.0.0:8000
```

## 4. Verification Checklist

### ✅ Marketing Site (airsports.no)
Visit `http://airsports.no:8002` in your browser.
- Test "Pretty URLs": Visit `http://airsports.no:8002/faq`.

### ✅ Main Application (app.airsports.no)
Visit `http://app.airsports.no:8002`. You should see the React application.
- Verify that the `Host` header detection correctly opted out of the marketing site for this subdomain.

### ✅ Legacy API Compatibility
Visit `http://airsports.no/api/schema/swagger-ui/`.
- This should still resolve to the Django API documentation.
- This confirms that path-based routing (`/api/`) takes precedence over the catch-all marketing route.

## 5. Architectural Reminder (Post-Test)
Once you deploy to GKE, remember the final "Performance Step" documented in `CDN_IMPLEMENTATION_PLAN.md`:
- Change `STATIC_URL` to `/static/` in production settings.
- Configure the GKE Gateway to serve `/static/*` via a **GCS Backend Bucket** for global CDN edge caching.
