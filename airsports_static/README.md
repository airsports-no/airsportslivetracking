# Air Sports Live Tracking - Static Info Site

This is the static information and documentation site for Air Sports Live Tracking (ASLT), built with **Astro 6** and **Tailwind CSS 4**.

## 🚀 Quick Start

1.  **Enter the directory:** `cd airsports_static`
2.  **Install dependencies:** `npm install`
3.  **Start development server:** `npm run dev`
    *   The site will be available at `http://localhost:4321`
4.  **Build for production:** `npm run build`
    *   Output will be in the `dist/` folder.

## 📁 Project Structure

*   `src/pages/`: Contains all site pages.
    *   `docs/`: Markdown files for user guides.
    *   `index.astro`: The homepage.
    *   `tutorials.astro`: Video tutorial gallery.
    *   `faq.astro`: Frequently Asked Questions.
*   `src/assets/img/`: **Source images.** Always put new images here for optimization.
*   `src/layouts/`:
    *   `Layout.astro`: Main wrapper with header/footer.
    *   `DocsLayout.astro`: Sidebar layout for documentation.
*   `public/`: Static assets that should NOT be processed (favicons, robots.txt).

## 📝 Maintenance & Expansion

### Adding Documentation
1.  Create a new `.md` file in `src/pages/docs/`.
2.  Use the following frontmatter:
    ```markdown
    ---
    layout: ../../layouts/DocsLayout.astro
    title: "Your Guide Title"
    ---
    ```
3.  Add the new page to the `navItems` array in `src/layouts/DocsLayout.astro` to make it appear in the sidebar.

### Adding Video Tutorials
1.  Upload the video to YouTube.
2.  Open `src/pages/tutorials.astro`.
3.  Add a new object to the `videos` array:
    ```javascript
    { title: "Your Tutorial Title", id: "YOUTUBE_VIDEO_ID" }
    ```

### Image Handling (Performance)
**Never use standard `<img>` tags for local assets.** Always use the Astro `<Image />` component for automatic WebP conversion and resizing:

```astro
---
import { Image } from 'astro:assets';
import myImage from '../assets/img/my-image.png';
---
<Image src={myImage} alt="Description" width={800} height={450} />
```

### Updating Styles
This project uses **Tailwind CSS 4**. Styles are primarily configured in `src/styles/global.css` using the new CSS-first configuration approach.

## 🧪 Testing & Validation

*   **Type Checking:** Run `npm run astro check` to validate TypeScript and component props.
*   **Build Test:** Always run `npm run build` before deploying to ensure there are no broken imports or routes.
*   **Audit:** Use `npx astro audit` (if available) or Lighthouse to check for accessibility and performance regressions.
*   **Versioning:** Increment the "Build Version" in `src/layouts/Layout.astro` when making significant production updates to help track cache busting.

## ☁️ Deployment

### Automated Deployment (Recommended)
This project is configured with **Google Cloud Build** for automated deployment. Pushes to the `main` branch (specifically changes within the `airsports_static/` directory) will trigger a build and deploy to Firebase Hosting automatically.
*   **Config:** `cloudbuild-static.yaml`
*   **Project ID:** `airsports-613ce`

### Manual Deployment
If you need to deploy manually:
1.  Build the site: `npm run build`
2.  Deploy: `firebase deploy --only hosting` (requires Firebase CLI and permissions)

The site is configured via `firebase.json` to serve from the `dist/` directory with `cleanUrls` enabled.
