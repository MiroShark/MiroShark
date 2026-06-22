# Railway Deployment Runbook

## Overview
This runbook documents the complete Railway deployment process for MiroShark backend-only staging service.

## Prerequisites
- Railway account with project access
- Git repository with Railway integration configured
- Neo4j database (Railway-hosted or external)
- OpenAI-compatible API key (or local LLM setup)

## Step 1: Railway Project Setup

### 1.1 Create Railway Project
1. Log in to Railway dashboard
2. Create new project: "MiroShark Backend Staging"
3. Connect GitHub repository
4. Select branch: `feat/railway-miroshark-api-staging`

### 1.2 Configure Railway Service
1. Add new service → Deploy from GitHub
2. Select repository and branch
3. Railway will detect `railway.json` and use `Dockerfile.railway`
4. Service name: `miroshark-backend-staging`

## Step 2: Environment Variables

### 2.1 Required Variables
Set these in Railway service environment variables:

```bash
# === Application Mode ===
FLASK_DEBUG=false

# === Internal API Authentication ===
# Generate with: openssl rand -hex 32
MIROSHARK_INTERNAL_KEY=<generate-secure-key>

# === Flask Configuration ===
SECRET_KEY=<generate-secure-key>

# === LLM Configuration ===
LLM_PROVIDER=openai
LLM_API_KEY=<your-api-key>
LLM_BASE_URL=https://api.openai.com/v1
LLM_MODEL_NAME=xiaomi/mimo-v2.5

# === Neo4j Configuration ===
NEO4J_URI=<your-neo4j-uri>
NEO4J_USER=neo4j
NEO4J_PASSWORD=<your-neo4j-password>
```

### 2.2 Optional Variables
Copy from `railway.env.example` as needed for your specific setup.

## Step 3: Database Setup

### 3.1 Railway Neo4j (Recommended)
1. Add Neo4j service to Railway project
2. Wait for database to be provisioned
3. Copy connection details to environment variables:
   - `NEO4J_URI`: From Railway Neo4j service
   - `NEO4J_USER`: `neo4j`
   - `NEO4J_PASSWORD`: From Railway Neo4j service

### 3.2 External Neo4j
1. Ensure Neo4j is accessible from Railway
2. Set environment variables accordingly
3. Configure network access if needed

## Step 4: Deploy

### 4.1 Initial Deployment
1. Push changes to `feat/railway-miroshark-api-staging` branch
2. Railway will auto-deploy on push
3. Monitor build logs in Railway dashboard

### 4.2 Verify Deployment
1. Check Railway service status: should be "Running"
2. Click service → "Networking" to get public URL
3. Test health endpoint: `curl https://<service-url>.railway.app/health`
4. Expected response: `{"status": "ok"}`

## Step 5: Smoke Testing

### 5.1 Automated Smoke Test
Use the provided smoke test script:

```bash
# Set environment variables
export SMOKE_TEST_URL=https://<service-url>.railway.app
export MIROSHARK_INTERNAL_KEY=<your-key>

# Run smoke test
python scripts/smoke_test.py
```

### 5.2 Manual Health Check
```bash
curl https://<service-url>.railway.app/health
```

### 5.3 Manual Protected API Test
```bash
# Test without auth (should fail with 401)
curl https://<service-url>.railway.app/api/graph/ontology/generate

# Test with auth (should pass or return 400 for missing fields)
curl -H "x-miroshark-internal-key: <your-key>" \
  https://<service-url>.railway.app/api/graph/ontology/generate
```

### 5.4 OpenAPI Docs
```bash
# Should be accessible without auth
curl https://<service-url>.railway.app/api/docs
```

### 5.5 Synthetic Data Seed
For testing with actual data, use the synthetic seed script:

```bash
# Set Neo4j environment variables
export NEO4J_URI=<your-neo4j-uri>
export NEO4J_USER=neo4j
export NEO4J_PASSWORD=<your-password>

# Create synthetic test data
python scripts/synthetic_seed.py

# Clean up synthetic data after testing
python scripts/synthetic_seed.py cleanup
```

## Step 6: MVP and Deep Test Protocols

After basic smoke tests pass, execute comprehensive test protocols to validate API functionality:

### 6.1 MVP Test Protocol
For basic API validation with minimal data (2-3 rounds):
- See `docs/plans/2026-05-24-mvp-deep-test-protocol.md` for detailed instructions
- Execute 2-3 rounds of simulation with minimal entities
- Validate basic API functionality and authentication
- Document results

### 6.2 Deep Test Protocol
For comprehensive validation with realistic data (5 rounds):
- See `docs/plans/2026-05-24-mvp-deep-test-protocol.md` for detailed instructions
- Execute 5 rounds of simulation with increasing complexity
- Validate performance, edge cases, and stress handling
- Document results and monitor resource usage

### 6.3 Test Execution
Both protocols can be executed manually after deployment:
- Set environment variables for Railway service URL and internal key
- Follow the step-by-step instructions in the protocol document
- Monitor Railway service logs and metrics during testing
- Clean up synthetic test data after completion

## Step 7: Integration

### 7.1 Bazodiac Pattern Analysis Integration
1. Provide Railway service URL to Bazodiac team
2. Share `MIROSHARK_INTERNAL_KEY` via secure channel
3. Document API contract in Bazodiac integration docs

### 7.2 Monitoring
1. Enable Railway metrics
2. Set up error logging (if needed)
3. Monitor service health via Railway dashboard

## Troubleshooting

### Build Failures
- Check `railway.json` configuration
- Verify `Dockerfile.railway` syntax
- Review build logs in Railway dashboard

### Runtime Errors
- Check Railway service logs
- Verify environment variables are set
- Test health endpoint first
- Check Neo4j connectivity

### Auth Issues
- Verify `MIROSHARK_INTERNAL_KEY` is set
- Check header format: `x-miroshark-internal-key`
- Review auth guard logs

## Rollback

### If Deployment Fails
1. Railway auto-rolls back on failure
2. Check previous deployment logs
3. Fix issues and push new commit

### Manual Rollback
1. Revert to previous commit
2. Push to branch
3. Railway will auto-deploy

## Security Notes

### Secrets Management
- Never commit secrets to repository
- Use Railway environment variables for all secrets
- Rotate keys regularly
- Use strong random keys for `MIROSHARK_INTERNAL_KEY`

### Network Security
- API routes protected by internal key
- Health endpoint is public (for Railway health checks)
- OpenAPI docs are public (for API discovery)

## Maintenance

### Regular Tasks
- Monitor Railway service health
- Review logs for errors
- Update dependencies as needed
- Rotate keys periodically

### Updates
1. Update code in `feat/railway-miroshark-api-staging` branch
2. Push to trigger Railway deployment
3. Monitor deployment
4. Run smoke tests

## Support

### Documentation
- See `README_DEPLOYMENT.md` for deployment overview
- See `docs/plans/2026-05-24-miroshark-railway-deployment.md` for implementation plan
- See `railway.env.example` for environment variable reference

### Contacts
- DevOps team for Railway issues
- Backend team for application issues
- Security team for auth issues
