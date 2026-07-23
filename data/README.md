# Challenge data manifests

This folder holds the **URL manifest** for downloading MCAP clips.

- `manifest.example.json` — schema example (placeholder URLs)
- `manifest.json` — live manifest with presigned R2 URLs (generated per candidate
  batch; not always committed)

Download:

```bash
python download_data.py data/manifest.json --out recordings/
```

The email / zip package you receive may contain only the manifest + README
(no MCAP bytes), same as our partner share flow. URLs typically expire in 7 days.
