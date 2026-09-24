let root: HTMLElement | null = null;

/**
 * A dedicated container for createPortal(), isolated from document.body's other direct
 * children. React tracks sibling DOM positions among a portal's own children when
 * reconciling; portaling straight into document.body means any other script that also
 * mutates document.body's direct children (a browser extension, another widget) can shift
 * those positions out from under React, causing spurious insertBefore/removeChild
 * "not a child of this node" NotFoundErrors (seen repeatedly in production - Sentry
 * JAVASCRIPT-REACT-8/-C/-J/-N/-Q/-R/-S/-T and others).
 */
export function getPortalRoot(): HTMLElement {
    if (!root || !root.isConnected) {
        root = document.getElementById('app-portal-root');
        if (!root) {
            root = document.createElement('div');
            root.id = 'app-portal-root';
            document.body.appendChild(root);
        }
    }
    return root;
}
