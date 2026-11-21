# Super Stems

Build the feature set for the NameSprouts app.

A main feature of this app is the handwritten look of letters up the stem that spell a person's name. This repository is the design-review workspace for code that lets lettering follow stems and feel hand drawn.

## Focused preview

The [single-name preview](design-review/) shows a June rose with **Dennis** following a gently curved stem. It measures the name in the bundled Allura script font and lets the stem grow to fit the lettering.

From the repository root, run:

    py -m http.server 5173

Then open http://127.0.0.1:5173/design-review/.

## Current application stack

The full NameSprouts prototype uses Flask 3 and Jinja, a browser-side JavaScript SVG proof preview, SQLite for local accounts and saved proofs, Stripe Checkout for one-time payment, and ReportLab/SVGLib for paid PDF output. See [STACK.md](STACK.md) for the current renderer and design-review notes. The application lives in [final/](final/).
