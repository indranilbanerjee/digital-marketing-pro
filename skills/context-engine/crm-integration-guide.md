# CRM Integration Guide — Connection Patterns & Data Sync

How the Digital Marketing Pro plugin connects to CRMs, maps marketing data to CRM objects, and keeps records synchronized across systems.

---

## Section 1: Supported CRMs

| CRM | MCP Server | Auth Type | Read | Write | Key Objects |
|---|---|---|---|---|---|
| **Salesforce** | `mcp-salesforce` | OAuth 2.0 | Yes | Yes | Leads, Contacts, Accounts, Opportunities, Campaigns |
| **HubSpot** | `@anthropic/mcp-hubspot` | API Key / OAuth | Yes | Yes (beta) | Contacts, Companies, Deals, Tickets |
| **Zoho CRM** | `mcp-zoho-crm` | OAuth 2.0 | Yes | Yes | Leads, Contacts, Accounts, Deals, Campaigns |
| **Pipedrive** | `mcp-pipedrive` | API Token | Yes | Yes | Persons, Organizations, Deals, Activities |

**Setup:** Set the relevant API key or OAuth credentials in `.env`. The MCP server configuration in `.mcp.json` handles connection routing. Each brand can use a different CRM (see Section 7: Multi-CRM Setup).

---

## Section 2: Field Mapping

How brand profile and marketing data fields map to CRM object fields across platforms.

### Contact & Company Fields

| Brand Profile / Marketing Field | Salesforce | HubSpot | Zoho | Pipedrive |
|---|---|---|---|---|
| `company_name` | Account.Name | Company.name | Account.Account_Name | Organization.name |
| `contact.email` | Lead.Email / Contact.Email | Contact.email | Lead.Email / Contact.Email | Person.email |
| `contact.phone` | Lead.Phone / Contact.Phone | Contact.phone | Lead.Phone / Contact.Phone | Person.phone |
| `contact.first_name` | Lead.FirstName | Contact.firstname | Lead.First_Name | Person.first_name |
| `contact.last_name` | Lead.LastName | Contact.lastname | Lead.Last_Name | Person.last_name |
| `contact.title` | Lead.Title | Contact.jobtitle | Lead.Designation | Person.job_title |
| `contact.source` | Lead.LeadSource | Contact.hs_lead_source | Lead.Lead_Source | Person.source |

### Deal & Campaign Fields

| Marketing Field | Salesforce | HubSpot | Zoho | Pipedrive |
|---|---|---|---|---|
| `deal_value` | Opportunity.Amount | Deal.amount | Deal.Amount | Deal.value |
| `deal_stage` | Opportunity.StageName | Deal.dealstage | Deal.Stage | Deal.stage_id |
| `deal_close_date` | Opportunity.CloseDate | Deal.closedate | Deal.Closing_Date | Deal.expected_close_date |
| `campaign_name` | Campaign.Name | (custom property) | Campaign.Campaign_Name | (custom field) |
| `campaign_status` | Campaign.Status | (custom property) | Campaign.Status | (custom field) |
| `utm_source` | Lead.UTM_Source__c (custom) | Contact.hs_analytics_source | Lead.UTM_Source (custom) | Person.utm_source (custom) |

**Note:** Fields marked "(custom)" require creating a custom field/property in the CRM before the plugin can write to them. Use `crm-sync.py --action setup-fields --crm {crm}` to auto-create required custom fields.

---

## Section 3: Data Sync Patterns

### One-Way Push (Plugin to CRM)

The most common pattern. The plugin is the source of truth for marketing data and pushes to the CRM.

| Use Case | Trigger | CRM Action |
|---|---|---|
| Lead import from campaign | Campaign execution or form submission | Create Lead/Contact |
| Deal update from pipeline analysis | Pipeline review or scoring change | Update Opportunity/Deal |
| Campaign record creation | Campaign launch via `/dm:launch-campaign` | Create Campaign object |
| Activity logging | Email send, ad click, webinar registration | Create Activity/Task |

```bash
python crm-sync.py --brand {slug} --action push --object lead --data '{"email": "...", "source": "q3-webinar"}'
```

### Two-Way Sync (Plugin and CRM)

Used when both systems hold authoritative data. The CRM has sales activity and deal progression; the plugin has marketing engagement and scoring.

| Direction | Data | Example |
|---|---|---|
| Plugin → CRM | Marketing score, campaign membership, content engagement | Lead score updated from 45 to 82 |
| CRM → Plugin | Deal stage changes, revenue data, sales feedback | Deal moved to "Closed Won" — attribute to campaign |

**Conflict resolution:** Last-write-wins with audit trail. Every sync operation logs: field, old value, new value, source (plugin or CRM), timestamp. Audit log at `~/.claude-marketing/brands/{slug}/crm-sync-log.json`.

### Event-Triggered Sync

Automated syncs fired by specific marketing or sales events.

| Event | Sync Action |
|---|---|
| Campaign execution | Create/update CRM Campaign record |
| Lead form submission | Create CRM Lead with UTM data |
| Lead score crosses threshold (80+) | Update CRM Lead status to "Sales-Ready", notify sales |
| Deal stage changes to "Closed Won" | Trigger attribution update in plugin |
| Email hard bounce | Update CRM Contact status to "Invalid Email" |

---

## Section 4: Deduplication Rules

Before creating any CRM record, the plugin checks for existing matches. Rules are applied in priority order:

| Priority | Method | Match Criteria | Confidence |
|---|---|---|---|
| 1 | Email match | Exact match, case-insensitive | Highest |
| 2 | Phone match | Normalized: strip spaces, dashes, parentheses, country code prefix | High |
| 3 | Company + Name | Company name exact + contact name fuzzy (Levenshtein distance ≤ 2) | Medium |
| 4 | Domain match | Extract domain from email → match to company | Company-level only |

**Always check dedup BEFORE creating records:**
```bash
python crm-sync.py --brand {slug} --action check-dedup --email "user@example.com" --phone "+1-555-0123"
```

**Merge behavior:** When a match is found, the plugin updates the existing record rather than creating a duplicate. If multiple matches are found, the highest-confidence match is used and the others are flagged for manual review.

---

## Section 5: Campaign Linking

How marketing campaigns connect to CRM campaign objects for attribution and reporting.

| CRM | Campaign Object | Lead/Contact Association | Attribution Model |
|---|---|---|---|
| **Salesforce** | Campaign | CampaignMember (links Leads/Contacts to Campaign with Status and ResponseDate) | Influence model via CampaignInfluence or custom attribution |
| **HubSpot** | Custom properties or Campaigns (Marketing Hub Professional+) | Contact timeline events, custom association | HubSpot attribution reports or custom |
| **Zoho** | Campaign | Associate Leads/Contacts via Campaign Member | Zoho Campaign analytics or custom |
| **Pipedrive** | Custom fields or Activities linked to Deals | Activity association on Deal/Person | Custom attribution via plugin |

**Plugin tracking:** Every campaign execution logs a `crm_campaign_id` via:
```bash
python execution-tracker.py --action log-execution --campaign-id {id} --crm-campaign-id {crm_id}
```

This creates a bidirectional link: the plugin knows which CRM campaign corresponds to each marketing campaign, and the CRM campaign links back to the plugin's campaign ID via a custom field.

---

## Section 6: Lead Scoring Integration

The plugin's lead scoring system (defined in `skills/marketing-automation/lead-scoring.md`) generates a 0-100 marketing score. This score must be synced to the CRM for sales team visibility.

### Score Field Mapping

| CRM | Field | Type | Notes |
|---|---|---|---|
| **Salesforce** | `Lead.Marketing_Score__c` / `Contact.Marketing_Score__c` | Number (custom field) | Create via Setup > Object Manager > Fields |
| **HubSpot** | `hubspot_score` (built-in) or custom contact property | Number | Built-in scoring available in Marketing Hub Professional+ |
| **Zoho** | `Marketing_Score` (custom field) | Number | Create via Settings > Modules > Fields |
| **Pipedrive** | Custom field on Person | Number | Create via Settings > Data fields |

### Sync Frequency

| Trigger | Action |
|---|---|
| Score change (any amount) | Queue sync — batch executes every 15 minutes |
| Score crosses a threshold boundary | Immediate sync + notification |
| Daily batch (midnight local) | Full reconciliation of all scored leads |

### Threshold Actions

| Score Range | Status | CRM Action |
|---|---|---|
| 80-100 | Sales-Ready | Update Lead status, notify assigned sales rep, create Task/Activity |
| 50-79 | Nurture | Enroll in nurture sequence, update Lead status to "Marketing Qualified" |
| 20-49 | Cold | Continue automated nurture, no sales notification |
| 0-19 | Inactive | Flag for re-engagement campaign or suppression after 90 days |

---

## Section 7: Multi-CRM Setup (Agency Pattern)

Agencies managing multiple brands can connect each brand to a different CRM.

**How it works:**
- Credential profiles (`credential-manager.py`) map each brand to its CRM and credentials
- The active CRM is determined by the brand's credential profile via the `default_crm` field
- Switching brands (via `/dm:switch-brand`) automatically switches CRM context

**Credential profile structure:**
```json
{
  "brand_slug": "acme-corp",
  "default_crm": "salesforce",
  "crm_credentials": {
    "salesforce": {
      "env_prefix": "ACME_SF"
    }
  }
}
```

**Environment variables follow the pattern:** `{ENV_PREFIX}_CLIENT_ID`, `{ENV_PREFIX}_CLIENT_SECRET`, `{ENV_PREFIX}_REFRESH_TOKEN`.

**Example multi-brand setup:**

| Brand | CRM | Env Prefix | Notes |
|---|---|---|---|
| Acme Corp | Salesforce | `ACME_SF` | Enterprise CRM, full read/write |
| BetaWidget | HubSpot | `BETA_HS` | Marketing Hub Professional |
| LocalShop | Pipedrive | `LOCAL_PD` | Small business, deal-focused |
| HealthCo | Zoho CRM | `HEALTH_ZO` | HIPAA-aware configuration |

---

## Section 8: Data Privacy

### GDPR Compliance

| Requirement | Implementation |
|---|---|
| Document legal basis for processing | Store `consent_basis` field on every CRM record (consent, legitimate interest, contract) |
| Respect data subject requests | `crm-sync.py --action dsr --type {access/delete/port} --email "..."` |
| Data retention policy | Configure max retention per brand; auto-flag records exceeding retention period |
| Data Processing Agreements | Required with every CRM vendor — verify before connecting |

### CCPA Compliance

| Requirement | Implementation |
|---|---|
| Honor opt-out requests | `crm-sync.py --action opt-out --email "..."` — suppresses across all sync operations |
| Do not sell data | Plugin never transfers CRM data to third parties |
| Disclosure on collection | Lead forms must include privacy notice linking to brand's privacy policy |

### General Security Rules

| Rule | Detail |
|---|---|
| Credential storage | CRM credentials in `.env` ONLY — never in marketing data files, campaign plans, or logs |
| Audit trail | Every CRM write operation logged with: timestamp, user/agent, action, fields modified, old/new values |
| Access logging | All CRM read operations logged with: timestamp, query, records accessed, purpose |
| Cross-border transfers | If brand operates in multiple jurisdictions, apply the most restrictive privacy rules across all CRM operations |
| Encryption | All MCP connections use TLS. No CRM data stored in plaintext intermediate files |

### Privacy by Default

When creating new CRM integrations:
1. Start with read-only access — add write permissions only when needed
2. Minimize data synced — only push fields required for the use case
3. Set retention limits at connection time
4. Enable audit logging before the first sync
5. Document the data flow in the brand's credential profile
