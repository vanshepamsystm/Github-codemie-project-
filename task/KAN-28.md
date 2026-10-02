# KAN-28

## Jira
- **Ticket:** KAN-28  
- **Summary:** Add automated API tests for Todo CRUD endpoints and DB behaviors  
- **Link:** https://vvanshahuja.atlassian.net/browse/KAN-28

## Confluence
- **Space:** DEV  
- **Title:** `[KAN-28] Architecture Design — Automated API Tests for Todo CRUD endpoints and DB behaviors`  
- **Link:** https://vvanshahuja.atlassian.net/wiki/spaces/DEV/pages/2523137/KAN-28+Architecture+Design+Automated+API+Tests+for+Todo+CRUD+endpoints+and+DB+behaviors

## HLD
- **Link:** https://vvanshahuja.atlassian.net/wiki/spaces/DEV/pages/2523137/KAN-28+Architecture+Design+Automated+API+Tests+for+Todo+CRUD+endpoints+and+DB+behaviors (same page unless separated)

## LLD
- **Link:** https://vvanshahuja.atlassian.net/wiki/spaces/DEV/pages/2523137/KAN-28+Architecture+Design+Automated+API+Tests+for+Todo+CRUD+endpoints+and+DB+behaviors (same page unless separated)

## PR
- **Repo:** vanshepamsystm/Github-codemie-project-  
- **Source branch (remote):** `KAN-28`  
- **Base branch:** `master`  
- **Title:** `[Codemie] KAN-28: Add automated API tests for Todo CRUD endpoints and DB behaviors`  
- **Link:** https://github.com/vanshepamsystm/Github-codemie-project-/pull/21

## Notes / Updates
- Jira ticket created and Confluence design page published (traceability includes Jira + PR).
- PR opened from branch `KAN-28` into `master`.

## Checklist
- [ ] HLD reviewed
- [ ] LLD reviewed
- [x] Tests added for GET /api/todos
- [x] Tests added for POST /api/todos (valid + empty title -> 400)
- [x] Tests added for PATCH /api/todos/{id} (valid + 404)
- [x] Tests added for DELETE /api/todos/{id} (valid + 404)
- [ ] DB behavior verified (isolation/temporary DB, deterministic ordering)
- [ ] PR reviewed
- [ ] PR merged
- [x] Verified locally
