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
Django needs the built Astro files to serve them. Run the build command in the marketing directory:

```bash
cd airsports_static
npm install
npm run build
```
This creates the `dist/` folder which Django is now configured to look for if the production `/marketing_dist` path is missing.

## 3. Start the Application
Run the Django development server. To use the domains without a port number, you must bind to port `80` (requires root/admin):

```bash
# From the /src directory
sudo python manage.py runserver 80
```

*If you prefer not to use sudo, run on port 8000 and append :8000 to the URLs below.*

## 4. Verification Checklist

### ✅ Marketing Site (airsports.no)
Visit `http://airsports.no`. You should see the Astro-based marketing site. 
- Test "Pretty URLs": Visit `http://airsports.no/faq` or `http://airsports.no/support`. Django should resolve these to the corresponding HTML files in the dist folder.

### ✅ Main Application (app.airsports.no)
Visit `http://app.airsports.no`. You should see the React application (loading screen/dashboard).
- Verify that the `Host` header detection correctly opted out of the marketing site for this subdomain.

### ✅ Legacy API Compatibility
Visit `http://airsports.no/api/schema/swagger-ui/`.
- This should still resolve to the Django API documentation.
- This confirms that path-based routing (`/api/`) takes precedence over the catch-all marketing route.

## 5. Architectural Reminder (Post-Test)
Once you deploy to GKE, remember the final "Performance Step" documented in `CDN_IMPLEMENTATION_PLAN.md`:
- Change `STATIC_URL` to `/static/` in production settings.
- Configure the GKE Gateway to serve `/static/*` via a **GCS Backend Bucket** for global CDN edge caching.
