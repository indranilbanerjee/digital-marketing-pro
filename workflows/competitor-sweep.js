export const meta = {
  name: 'competitor-sweep',
  description: 'Research several competitors in parallel (positioning, pricing, content, SEO, paid, AI visibility), each with cited sources, then synthesize one comparison with gaps and opportunities',
  phases: ['Research each competitor', 'Synthesize'],
}

// args: { competitors: ["acme.com", "Rival Inc"], brand?: "brand-slug", as_of?: "YYYY-MM-DD" }
// Read-only: agents browse the public web and read the brand profile; nothing is published or spent.
const input = args || {}
const competitors = Array.isArray(input.competitors) ? input.competitors.filter(Boolean) : []
if (competitors.length === 0) {
  return 'competitor-sweep needs args.competitors — a list of competitor names or domains, e.g. {"competitors": ["acme.com", "rival.io"], "brand": "my-brand"}.'
}
const asOf = input.as_of || 'the current date'
const brandLine = input.brand
  ? `The user's own brand slug is "${input.brand}"; read its profile (~/.claude-marketing/brands/${input.brand}/profile.json) only to understand who the competitor is being compared against.`
  : 'No brand slug was given; research the competitor on its own terms.'

const finding = {
  type: 'object',
  required: ['competitor', 'positioning', 'pricing', 'content_themes', 'seo_signals', 'paid_signals', 'ai_visibility', 'sources'],
  properties: {
    competitor: { type: 'string' },
    positioning: { type: 'string', description: 'One or two sentences; "unknown" if not evidenced' },
    pricing: { type: 'string', description: 'Published plans/prices with the page they came from, or "not published"' },
    content_themes: { type: 'array', items: { type: 'string' } },
    seo_signals: { type: 'array', items: { type: 'string' } },
    paid_signals: { type: 'array', items: { type: 'string' }, description: 'From public ad libraries (Meta Ad Library, Google Ads Transparency Center, LinkedIn Ad Library) only' },
    ai_visibility: { type: 'string', description: 'Whether the competitor appears in AI answers you could observe; "not checked" if you could not' },
    sources: { type: 'array', items: { type: 'string' }, description: 'Every URL a claim above came from' },
  },
}

phase('Research each competitor')
const results = await pipeline(competitors, name =>
  agent(
    `Research the competitor "${name}" as of ${asOf} for a marketing competitive analysis. ${brandLine}\n\n` +
    'Cover positioning, published pricing, recurring content themes, visible SEO signals (titles, topic clusters, structured data), ' +
    'paid activity from public ad libraries, and whether they appear in AI answers you can observe. ' +
    'Every claim must come from a page you actually opened; list those URLs in sources. ' +
    'Write "unknown" or "not published" instead of guessing. Never estimate traffic or spend without a cited tool export.',
    { label: name, schema: finding },
  ),
)
const found = results.filter(Boolean)
log(`Researched ${found.length} of ${competitors.length} competitors`)

phase('Synthesize')
return await agent(
  'You are writing the comparison section of a competitive analysis from these structured findings (JSON):\n\n' +
  JSON.stringify(found, null, 2) +
  '\n\nProduce: a comparison table (positioning, pricing, content, SEO, paid, AI visibility), the three largest gaps the user could exploit, ' +
  'and the claims that rest on a single source. Keep every source URL attached to the claim it supports. ' +
  'Do not add facts that are not in the findings. Use the /digital-marketing-pro:competitor-analysis skill\'s output conventions if it is available.',
  { label: 'synthesis' },
)
