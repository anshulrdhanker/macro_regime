# Deploy

This app is ready to deploy as a public Python web service.

## Render

1. Push this repo to GitHub.
2. In Render, create a new `Blueprint` or `Web Service` from the repo.
3. If using the blueprint flow, Render will detect [render.yaml](/Users/anshuldhanker/Downloads/macro_barometer_db/render.yaml).
4. Set these environment variables in Render:
   - `FRED_API_KEY`
   - `OPENAI_API_KEY`
5. Deploy.

Start command:

```bash
gunicorn app:server --workers 1 --threads 4 --timeout 180
```

## Railway / Other Procfile Hosts

This repo also includes [Procfile](/Users/anshuldhanker/Downloads/macro_barometer_db/Procfile), so hosts that support Procfiles can run:

```bash
gunicorn app:server --workers 1 --threads 4 --timeout 180
```

## Notes

- The app binds to `0.0.0.0` and reads `PORT` automatically in production.
- Data refresh uses the existing cache/freshness logic from the app.
- If `OPENAI_API_KEY` is missing or the OpenAI request fails, the dashboard falls back to deterministic copy.
