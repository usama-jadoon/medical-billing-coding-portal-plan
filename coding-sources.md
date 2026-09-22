# Coding Sources / Licensing

## Source hierarchy

Use official sources first.

### ICD-10-CM

Primary:
- CDC/NCHS ICD-10-CM files
- CMS/NCHS official guidelines

The official CDC page publishes fiscal-year releases and identifies FY27 as beginning October 1, 2026.

Do not hard-code "current" forever.
Resolve code-set version by service date.

### CPT

CPT is maintained by AMA.

Commercial/electronic use requires appropriate licensing.

Do not scrape and redistribute CPT content.

Architecture must support:

```text
CPT provider adapter
```

with licensed data/API/import.

### HCPCS

Use CMS official HCPCS resources.

### NCCI

Use CMS NCCI edits and policy manual.

NCCI should be represented as a validation/reference layer, not as an LLM instruction.

### NCD/LCD

Use CMS coverage references where applicable.

Do not assume Medicare coverage rules apply to every payer.

### CDT

Dental CDT is maintained by ADA.

Commercial use requires appropriate license.

Keep CDT behind separate:

```text
dental-coding-provider
```

Do not copy CDT into public repository.

## Official references

CMS:
https://www.cms.gov/

CDC ICD-10-CM:
https://www.cdc.gov/nchs/icd/icd-10-cm/files.html

AMA CPT:
https://www.ama-assn.org/practice-management/cpt/cpt-code-set-basics-and-resources

CMS NCCI:
https://www.cms.gov/medicare/coding-billing/national-correct-coding-initiative-ncci-edits/medicare-ncci-policy-manual

ADA CDT:
https://www.ada.org/publications/cdt

## "Live access" design

Do not build generic web scraping.

Build Reference Center:

```text
Official source
    |
    +--> API/feed/import if officially permitted
    |
    +--> cached metadata
    |
    +--> source URL
    |
    +--> effective date
    |
    +--> last verified date
```

UI:

```text
Code Candidate
  |
  +-- Source
  +-- Version
  +-- Effective date
  +-- Official reference
  +-- Relevant policy
```

For sources without an API/license, open official source in new tab instead of copying protected content into product.

## Important

"coding.com" or random coding websites are not automatically authoritative.

Portal should distinguish:

- Official government source
- Code-set owner
- Payer source
- Educational/reference source
- Third-party source
