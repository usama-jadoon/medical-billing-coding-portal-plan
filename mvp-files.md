# MVP File Map

## Root

```text
medical-coding-portal/
├── README.md
├── plan.md
├── architecture.md
├── security.md
├── coding-sources.md
├── ai-spec.md
├── data-model.md
├── commands.md
├── mvp-files.md
├── docker-compose.yml
├── .env.example
├── .gitignore
├── package.json
├── pnpm-workspace.yaml
└── apps/
```

## Web

```text
apps/web/
├── src/
│   ├── app/
│   │   ├── login/
│   │   ├── dashboard/
│   │   ├── encounters/
│   │   ├── upload/
│   │   ├── review/
│   │   ├── references/
│   │   └── settings/
│   ├── components/
│   │   ├── document-viewer/
│   │   ├── code-candidates/
│   │   ├── evidence-panel/
│   │   ├── validation-panel/
│   │   └── source-panel/
│   └── lib/
│       ├── api.ts
│       └── auth.ts
```

## API

```text
services/api/
├── app.py
├── api/
│   ├── auth.py
│   ├── organizations.py
│   ├── encounters.py
│   ├── documents.py
│   ├── coding.py
│   ├── reviews.py
│   └── references.py
├── domain/
│   ├── encounters/
│   ├── coding/
│   ├── evidence/
│   └── reviews/
├── db/
│   ├── models/
│   ├── session.py
│   └── migrations/
├── security/
│   ├── auth.py
│   ├── permissions.py
│   └── tenant.py
└── tests/
```

## Workers

```text
services/worker/
├── tasks/
│   ├── ocr.py
│   ├── extraction.py
│   ├── coding.py
│   ├── validation.py
│   └── references.py
└── worker.py
```

## Rules

```text
rulesets/
├── professional/
│   ├── em/
│   └── validation/
├── emergency/
├── outpatient/
├── inpatient/
├── surgery/
├── anesthesia/
├── radiology/
├── laboratory/
├── behavioral-health/
└── dental/
```

## Tests

```text
tests/
├── fixtures/
│   ├── synthetic-er/
│   ├── synthetic-office/
│   └── synthetic-dental/
├── extraction/
├── coding/
├── rules/
├── security/
├── tenant-isolation/
└── e2e/
```

## First implementation order

1. Auth/RBAC
2. Organization isolation
3. Encounter creation
4. Upload
5. OCR
6. Evidence viewer
7. Structured facts
8. Candidate code abstraction
9. Rule engine
10. Human review
11. Audit
12. Reference center
13. Export

Do not build every coding specialty first.
