# Single-name stem preview

This isolated design review renders one watercolor June rose with the name **Dennis** following a naturally curved stem. It is a focused prototype for reviewing stem shape and lettering before changing the full proof composer.

The renderer measures the name in the bundled Allura script font. It keeps the lettering size steady, grows the stem to the measured word length, and gives the curve a small deterministic bend so the preview stays stable on reload.

From the repository root, serve the project files locally:

    py -m http.server 5173

Then open `http://127.0.0.1:5173/design-review/`.

This is a design prototype. It does not yet replace the main application's composer or print renderer.

