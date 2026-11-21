# Super Stems design-review stack

## Current application stack

- **Web app:** Flask 3 with Jinja templates
- **Interactive proof:** browser-side JavaScript renders the composition as SVG
- **Artwork:** watercolor paper texture, birth-month flower images, and bundled script fonts
- **Accounts and saved proofs:** SQLite in local development
- **Payments:** one-time Stripe Checkout, enabled with test credentials
- **Print output:** ReportLab and SVGLib generate a PDF after payment is confirmed

## Current lettering behavior

The preview places the name as SVG text, rotates the whole word vertically, and sizes it with a character-count heuristic. The server repeats a similar calculation for the saved proof and PDF. The name is placed at a fixed position relative to the flower image, so it does not follow a measured stem path or the actual width of the shaped script lettering. Browser and print output also use separate rendering paths.

## Design-review focus

Review the flower-to-name connection and stem length before expanding the product flow. The next lettering iteration should measure the shaped name, fit it to a gentle stem path anchored to the flower, and keep the proof and print output visually consistent.

## Local setup

See [the application README](final/README.md) for Windows setup and configuration. The complete customer flow and repository overview are in [README.md](README.md).

