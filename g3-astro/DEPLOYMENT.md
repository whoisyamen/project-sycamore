# Cloudflare Pages deployment

## Scope

Publish the existing Astro static website through Cloudflare Pages' native GitHub
integration. The production branch is `prod`; `main` remains the development
branch. No Astro runtime adapter, Pages Functions, database upload, or ingestion
service migration is required.

The Python service continues to run locally. Cloudflare builds NEVER fetch news,
read local credentials, or run live ingestion. The Pages feed is a published
snapshot, not a connection to the local service. Browser polling cannot make an
unpublished snapshot fresh.

## Project settings

Authorize Cloudflare's GitHub app for `whoisyamen/project-sycamore` before creating
the project. Do not create a Direct Upload project if native Git integration is
wanted; that project type cannot simply be switched to Git integration later.

| Setting | Value |
| --- | --- |
| Project name | `project-sycamore` (subject to availability) |
| Repository | `whoisyamen/project-sycamore` |
| Production branch | `prod` |
| Root directory | `g3-astro` |
| Build command | `bash scripts/build-pages.sh` |
| Build output directory | `dist` |
| Build image | v3 |
| `NODE_VERSION` | `22.23.3` |
| `PYTHON_VERSION` | `3.13.3` |
| `SKIP_DEPENDENCY_INSTALL` | `true` |
| `PUBLIC_DEMO_MODE` | `false` |

Apply environment variables to production and preview builds. Repository version
files also pin Node and Python. Retain `shared/` and `g3-ingest/` in the checkout:
the web build reads shared schemas, and the build gate runs Python tests.

The build command installs locked dependencies, audits them, runs formatting,
Astro diagnostics, the production build, web tests and ingestion tests, then
removes local bookkeeping files from the artifact. High-severity dependency
findings or test failures prevent deployment. Security/cache headers come from
`public/_headers`.

## Release and data refresh

1. Review the website changes and a valid snapshot, including every referenced
   article image, in Git. Never add credentials, ingestion logs, databases,
   `_private/`, or generated Cesium assets.
2. Publish the reviewed commit to `prod`. Cloudflare automatically builds and
   deploys that branch after GitHub integration is configured.
3. Verify `/`, `/intelligence`, `/reporting`, `/data/snapshot.json`, static event
   links, image paths, browser console, Cesium workers and WebGL appearance.
4. Check freshness and error labels against the published snapshot timestamps.
   Check CSP and `Cache-Control: no-store` on data responses.
5. Ensure `/data/.ingest.lock` and `/data/media/.og-attempts.json` are not exposed.
   Pages may return a fallback HTML response for absent paths; verify the body,
   not only the status code.

Production currently changes only when `prod` is updated. No automatic snapshot
commits or timer changes are installed by this migration. Keep data publication
as an explicitly reviewed operation initially; frequent refreshes should use a
separate object-storage/publication design rather than exhausting build quotas.
Static event pages change on rebuild; dashboard event query links use the
published snapshot.

## Operations and limits

- Pages' Free plan allows 500 builds/month, 20,000 files/site and 25 MiB/file.
- Git builds need no Cloudflare deployment token stored in GitHub. The temporary
  API token used to configure the project should be revoked after setup.
- Use Cloudflare's deployment rollback for a bad release, then revert the
  corresponding `prod` commit so the next build does not reintroduce it.
- A custom domain, zone WAF/TLS settings, legal-page review, external uptime
  monitoring, and automatic data publication remain separate release tasks.
- Verify the repository security policy before a public product launch; a
  successful Pages build does not attest zone settings or legal compliance.

References: [GitHub integration](https://developers.cloudflare.com/pages/configuration/git-integration/github-integration/),
[build image](https://developers.cloudflare.com/pages/configuration/build-image/),
[Pages limits](https://developers.cloudflare.com/pages/platform/limits/).
