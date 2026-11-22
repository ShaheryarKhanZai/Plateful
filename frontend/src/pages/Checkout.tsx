# Plateful frontend CI/CD: setup guide

Workflow: `.github/workflows/frontend-ci-cd.yml` (frontend only; Vite + React + TypeScript, output in `frontend/dist`).

| Event | Jobs run |
|---|---|
| Pull request to `main` | `test` + `security` (parallel) -> `build`. **No deploy.** |
| Push to `main` | `test` + `security` -> `build` -> `deploy` (ZIP + site to S3) |

The workflow only triggers when `frontend/**` or the workflow file changes. Replace `eu-west-1`, `ACCOUNT_ID`, `OWNER/REPO` and `YOUR-BUCKET` below with your own values.

---

## 1. S3 bucket with static website hosting

1. **Create bucket** `YOUR-BUCKET` in your chosen region.
2. **Permissions > Block public access**: turn off **"Block public access to buckets and objects granted through new public bucket or access point policies"** and **"...any public bucket or access point policies"** (needed for a public website).
3. **Properties > Static website hosting > Enable**
   - Index document: `index.html`
   - Error document: `index.html` (the app uses `BrowserRouter`, so deep links like `/orders/5` must fall back to the SPA. S3 serves them with HTTP 404 but the page still renders.)
4. **Permissions > Bucket policy** (public read):

```json
{
  "Version": "2012-10-17",
  "Statement": [{
    "Sid": "PublicReadForWebsite",
    "Effect": "Allow",
    "Principal": "*",
    "Action": "s3:GetObject",
    "Resource": "arn:aws:s3:::YOUR-BUCKET/*"
  }]
}
```

> The build ZIPs go to the `artifacts/frontend/` prefix in the **same** bucket, so they are publicly readable too. They only contain the already-public site files, but if that bothers you, use a separate private bucket for ZIPs.

The deploy never deletes `artifacts/`. Website URL: *Properties > Static website hosting*. It is **HTTP only** (use CloudFront for HTTPS, not covered here).

## 2. IAM OIDC provider

IAM > Identity providers > Add provider:
- Type: **OpenID Connect**
- Provider URL: `https://token.actions.githubusercontent.com`
- Audience: `sts.amazonaws.com`

(Skip if your account already has this provider.)

## 3. IAM role for GitHub

IAM > Roles > Create role > Custom trust policy. Name it e.g. `plateful-frontend-deploy`.

**Trust policy**: only the `main` branch of your repo can assume it, so PRs cannot:

```json
{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Principal": {
      "Federated": "arn:aws:iam::ACCOUNT_ID:oidc-provider/token.actions.githubusercontent.com"
    },
    "Action": "sts:AssumeRoleWithWebIdentity",
    "Condition": {
      "StringEquals": {
        "token.actions.githubusercontent.com:aud": "sts.amazonaws.com",
        "token.actions.githubusercontent.com:sub": "repo:OWNER/REPO:ref:refs/heads/main"
      }
    }
  }]
}
```

**Permissions policy** (least privilege, this one bucket only):

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "ListBucket",
      "Effect": "Allow",
      "Action": "s3:ListBucket",
      "Resource": "arn:aws:s3:::YOUR-BUCKET"
    },
    {
      "Sid": "ReadWriteDeleteObjects",
      "Effect": "Allow",
      "Action": ["s3:PutObject", "s3:DeleteObject"],
      "Resource": "arn:aws:s3:::YOUR-BUCKET/*"
    }
  ]
}
```

Copy the role ARN (`arn:aws:iam::ACCOUNT_ID:role/plateful-frontend-deploy`).

## 4. GitHub repository settings

Settings > Secrets and variables > Actions

| Type | Name | Value |
|---|---|---|
| **Secret** | `AWS_ROLE_ARN` | the role ARN from step 3 |
| Variable | `AWS_REGION` | e.g. `eu-west-1` (the bucket's region) |
| Variable | `S3_BUCKET` | `YOUR-BUCKET` (name only, no `s3://`) |
| Variable | `VITE_API_URL` | public URL of your backend API, e.g. `https://api.example.com` |

`VITE_API_URL` is baked into the public JS at build time (not a secret). The build on `main` fails if it is unset, so the site never ships pointing at `localhost:8000`.

Backend note (not touched by this change): the backend's allowed frontend origin (`FRONTEND_ORIGIN`) and cookie/CORS settings must include your S3 website URL, or login will fail in the browser.

## 5. Commit and push

Run from the **repository root** (the folder that contains `frontend/`). Copy `.github/workflows/frontend-ci-cd.yml` and `docs/frontend-cicd-setup.md` there first.

```bash
git checkout main && git pull
git checkout -b ci/frontend-pipeline
git status                      # confirm node_modules/ and .env.local are NOT listed
git add .github/workflows/frontend-ci-cd.yml docs/frontend-cicd-setup.md
git commit -m "ci: add frontend CI/CD pipeline (tests, audit, build, S3 deploy)"
git push -u origin ci/frontend-pipeline
```

Open a pull request into `main` (GitHub prints the link, or `gh pr create --fill`). Check it, then merge to trigger the first deploy.

> If `git status` shows `node_modules/` or `.env.local`, add them to the root `.gitignore` before committing.

## 6. Verify

1. **PR run**: Actions tab > "Frontend CI/CD" on your PR: `Unit tests`, `Security audit`, `Build` are green and `Deploy to S3` does **not** appear.
2. **Merge to `main`**: a new run starts; all four jobs, including `Deploy to S3`, go green. The run summary shows the ZIP path.
3. **S3 artifact**: S3 console > bucket > `artifacts/frontend/` contains `plateful-frontend-<run#>-<sha>.zip`. Or:
   ```bash
   aws s3 ls s3://YOUR-BUCKET/artifacts/frontend/
   ```
4. **Site files**: bucket root has `index.html` and `assets/`.
5. **Live site**: open the website endpoint from *Properties > Static website hosting*. Check the app loads, reload on a deep link (e.g. `/orders`) still renders, and the browser Network tab shows requests going to your `VITE_API_URL`.

## Troubleshooting

- `Not authorized to perform sts:AssumeRoleWithWebIdentity`: the trust policy `sub` must exactly match `repo:OWNER/REPO:ref:refs/heads/main` (case-sensitive), and the OIDC provider must exist.
- `403` on the website: Block Public Access still on, or the bucket policy is missing or has the wrong bucket name.
- `npm audit` fails: run `npm audit` in `frontend/`, fix with `npm audit fix` or update the package; the build will not run until it passes.
