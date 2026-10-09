# How to Get a Production C2PA Signing Certificate

**Audience:** Brand operators preparing to sign AI-generated marketing assets for EU markets ahead of EU AI Act Article 50 enforcement on **2 August 2026**.
**Applies to:** `/digital-marketing-pro:c2pa-metadata` + `scripts/embed-c2pa.py`.

## Why this matters

The plugin ships with a **dev path** that auto-generates a self-signed 90-day certificate so you can test the signing flow without any external setup. Assets signed with the dev cert sign successfully and round-trip-verify locally, but at [contentcredentials.org/verify](https://contentcredentials.org/verify) they show as **"Signature present, signer not in trust list"**. EU AI Act Article 50 requires the marking to be "in a machine-readable format using open, interoperable standards" — a self-signed signature is technically machine-readable but won't pass any practical compliance review or third-party verification.

For production deployment, you need a certificate from a **CAI-recognized signing authority**. Here is how.

## Recognized authorities (July 2026)

The [Content Authenticity Initiative (CAI)](https://contentauthenticity.org/) maintains a trust list of issuers. The four practical paths as of July 2026:

### Option A — Adobe Content Credentials (easiest for content brands)

- **Who it's for:** Brands already using Adobe Creative Cloud (Photoshop, Lightroom, Illustrator, Premiere, After Effects).
- **How:** Adobe Content Credentials is built into Creative Cloud apps. Generate a Content Credentials identity through Adobe ID; assets signed via Creative Cloud carry an Adobe-issued C2PA signature that verifies cleanly.
- **For scripted / API signing (our plugin path):** Use the open-source `c2patool` CLI from the Coalition for Content Provenance and Authenticity (CAI) — docs at https://opensource.contentauthenticity.org/docs/c2patool/. For a production trust-listed signing certificate, contact the CAI via https://contentauthenticity.org/ to be onboarded as a signing partner; Adobe and several certificate authorities issue C2PA-compliant certificates for partners.
- **Cost:** Currently free for the basic identity; enterprise tiers TBD.
- **Cert format:** PEM-encoded ECDSA P-256 (compatible with our scripts' default `alg=b"es256"`).

### Option B — Truepic (best for high-volume / API-first brands)

- **Who it's for:** Brands signing many assets programmatically (e.g. a production content pipeline generating 500+ posts/month).
- **How:** Truepic operates a commercial C2PA signing service. Sign up at https://www.truepic.com, get an API key, configure the signing endpoint. Their service can either issue you a certificate to use locally OR sign on your behalf via API.
- **Cost:** Tiered SaaS pricing; contact for enterprise quote.
- **Cert format:** PEM-encoded ECDSA P-256.

### Option C — Numbers Protocol (decentralized / web3-leaning)

- **Who it's for:** Brands that want the provenance metadata anchored to a public ledger as well as C2PA.
- **How:** https://numbersprotocol.io — partner program issues C2PA-compliant certificates plus optional on-chain anchoring.
- **Cost:** Free tier exists; paid tiers for higher volume.

### Option D — Microsoft Azure Confidential Ledger (Azure shop)

- **Who it's for:** Enterprises already running on Azure with key-management policies that require Azure-resident keys.
- **How:** Azure Key Vault + Confidential Ledger can issue and host C2PA signing keys; integrate via Azure SDK.
- **Cost:** Azure consumption pricing.

## What you'll get

Each path produces (or hosts) a pair of files:

- A **certificate** (`.pem` — public part, contains issuer info, validity period, your organization name)
- A **private key** (`.pem` — secret, used to sign manifests)

The certificate is what verifiers check against the CAI trust list. The private key never leaves your machine (or your KMS — see "Production key management" below).

## How to use the production cert

Once you have `cert.pem` and `key.pem` from any of the four authorities above:

```
/digital-marketing-pro:c2pa-metadata \
    --input asset.png --output signed.png \
    --brand "Acme Corp" --generator "Vertex AI image model" \
    --ai-claim ai-generated-content \
    --ai-disclosure \
    --signing-cert /secure/c2pa-prod-cert.pem \
    --signing-key /secure/c2pa-prod-key.pem
```

`--ai-disclosure` adds the **C2PA 2.4 `c2pa.ai-disclosure` assertion** alongside the IPTC digital-source-type claim — the machine-readable marking the EU AI Act Article 50 deployer pathway relies on. Include it on every production sign of AI-generated assets bound for EU markets.

## Production key management — do this right

1. **Never commit cert + key to git.** Put them outside the repo, in a path only the production signing user can read (e.g. `/secure/c2pa/` with mode `400` on Unix or restricted ACL on Windows).
2. **Don't bake the key path into agent files / scripts.** Pass it via the `--signing-key` flag (paired with `--signing-cert`) at runtime, or read it from an environment variable in your own wrapper script.
3. **Use a secret store for team environments.** AWS Secrets Manager, GCP Secret Manager, HashiCorp Vault, Azure Key Vault — fetch the cert + key at signing time, don't persist them on disk where multiple users can reach them.
4. **Rotate annually.** Most CAI-recognized certs have a 1-year validity period. Set a calendar reminder; rotation is just "swap the file, signed assets going forward use the new key, previously signed assets stay verifiable because the old cert's signature is preserved in the manifest".
5. **If the key is ever compromised, revoke immediately** via the issuing authority's process and re-issue.

## What you still need a human for (even with a production cert)

- **Deepfake disclosure overlay** — Article 50 requires synthetic audio/image/video of real persons/places/objects to additionally carry a *visible* disclosure. C2PA manifest alone is not enough for deepfakes.
- **AI-text editorial responsibility claim** — Article 50 allows you to skip AI-generated-text disclosure for matters of public interest IF a human reviewer assumes editorial responsibility. Keep a documented human-review record (reviewer name, date, scope) for each piece; your brand still needs an internal sign-off process.
- **Legal sign-off per jurisdiction** — C2PA is the technical mechanism. Whether your specific deployment satisfies Article 50 in your specific EU market is your counsel's call.

## Verification testing

After production signing, verify before publishing:

1. Open the Content Credentials verify tool (https://contentcredentials.org/verify) and check a sample signed asset there
2. Confirm it shows your brand name as signer, the IPTC digital-source-type matches your claim, and the trust-list lookup is green (not "signer not in trust list")
3. Adobe Photoshop / Lightroom 2026+ also display Content Credentials natively — open the signed asset there as a sanity check

## Timeline guidance

| When | What to do |
|---|---|
| Today | Pick an authority (A/B/C/D above). For most brands, Adobe (A) or Truepic (B) is the right fit. |
| This week | Start the application / signup process. Adobe is typically 1–5 business days for a partner cert; Truepic onboarding is faster (account → API key → certificate within a day or two). |
| Before 2 Aug 2026 | Cert in hand, key-management in place, production-signing tested end-to-end against [contentcredentials.org/verify](https://contentcredentials.org/verify) |
| After 2 Aug 2026 | EU AI Act Article 50 enforcement active. Penalties up to €15M / 3% global turnover. |

Article 50 applies on **2 August 2026 — days away**. If you don't yet have a production cert, start today: Truepic's onboarding (account → API key → certificate) is the fastest path, and the dev-cert flow keeps your pipeline testable while you wait.

## Related plugin references

- `skills/context-engine/compliance-rules.md` Section 1.1b — EU AI Act Article 50 regulatory rule pack
- `skills/context-engine/eu-code-of-practice.md` — final Code of Practice on Transparency of AI-Generated Content (10 June 2026)
- `skills/c2pa-metadata/SKILL.md` — the signing skill this guide supports
