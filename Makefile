.PHONY: verify web ingest
verify: web ingest
web:
	cd g3-astro && npm run verify
ingest:
	cd g3-ingest && python3 -m unittest discover -s tests -v
