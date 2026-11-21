# super-stems

Build the feature set for the NameSprouts app.

A main feature of this app is the handwritten look of letters up the stem that spell a person's name. This repository is the design-review workspace for the code structure that lets lettering follow stems and feel hand drawn.

## Current stack

The prototype uses Flask 3 and Jinja templates, a browser-side JavaScript SVG proof preview, SQLite for local accounts and saved proofs, Stripe Checkout for one-time payment, and ReportLab/SVGLib for paid PDF output. The browser proof and print renderer are still separate.

## Design review

The current renderer rotates script text vertically and places it at a fixed position relative to each flower image. It does not measure the actual shaped name or fit lettering to a flower-specific stem path yet. See [STACK.md](STACK.md) for the current state and next design focus.

## Run locally

The Flask app is in [final/](final/). On Windows:

    cd final
    py -m venv .venv
    .\\.venv\\Scripts\\Activate.ps1
    py -m pip install -r requirements.txt
    Copy-Item .env.example .env
    py -m flask --app app run --debug

Open http://127.0.0.1:5000. Stripe stays disabled until test credentials are configured. See [final/README.md](final/README.md) for configuration details.
