#!/usr/bin/env python3
"""Generate JSON-LD structured data markup for common schema.org types."""

import argparse
import json
import sys

# Required and recommended fields per schema type
SCHEMA_SPECS = {
    "Article": {
        "required": ["headline", "author", "datePublished"],
        "recommended": ["image", "dateModified", "publisher", "description", "mainEntityOfPage"],
        "context_type": "Article",
    },
    "FAQPage": {
        "required": ["questions"],
        "recommended": [],
        "context_type": "FAQPage",
        "note": "Provide 'questions' as a list of {question, answer} objects",
    },
    "HowTo": {
        "required": ["name", "steps"],
        "recommended": ["description", "totalTime", "estimatedCost", "image", "supply", "tool"],
        "context_type": "HowTo",
        "note": "Provide 'steps' as a list of {name, text} objects",
    },
    "Product": {
        "required": ["name"],
        "recommended": ["description", "image", "brand", "sku", "offers", "aggregateRating", "review"],
        "context_type": "Product",
    },
    "LocalBusiness": {
        "required": ["name", "address"],
        "recommended": ["telephone", "openingHours", "image", "url", "priceRange", "geo", "sameAs"],
        "context_type": "LocalBusiness",
    },
    "Organization": {
        "required": ["name"],
        "recommended": ["url", "logo", "sameAs", "contactPoint", "description", "address"],
        "context_type": "Organization",
    },
    "Person": {
        "required": ["name"],
        "recommended": ["jobTitle", "url", "sameAs", "image", "email", "worksFor"],
        "context_type": "Person",
    },
    "Event": {
        "required": ["name", "startDate", "location"],
        "recommended": ["endDate", "description", "image", "offers", "performer", "organizer"],
        "context_type": "Event",
    },
    "VideoObject": {
        "required": ["name", "description", "thumbnailUrl", "uploadDate"],
        "recommended": ["contentUrl", "embedUrl", "duration", "interactionStatistic"],
        "context_type": "VideoObject",
    },
}


def build_faq_schema(data):
    """Build FAQPage JSON-LD from a list of Q&A pairs."""
    questions = data.get("questions", [])
    main_entity = []
    for qa in questions:
        q = qa.get("question", qa.get("q", ""))
        a = qa.get("answer", qa.get("a", ""))
        if q and a:
            main_entity.append({
                "@type": "Question",
                "name": q,
                "acceptedAnswer": {
                    "@type": "Answer",
                    "text": a,
                },
            })
    return {
        "@context": "https://schema.org",
        "@type": "FAQPage",
        "mainEntity": main_entity,
    }


def build_howto_schema(data):
    """Build HowTo JSON-LD from step data."""
    steps = data.get("steps", [])
    how_to_steps = []
    for i, step in enumerate(steps):
        step_obj = {
            "@type": "HowToStep",
            "position": i + 1,
            "name": step.get("name", f"Step {i + 1}"),
            "text": step.get("text", ""),
        }
        if step.get("image"):
            step_obj["image"] = step["image"]
        how_to_steps.append(step_obj)

    schema = {
        "@context": "https://schema.org",
        "@type": "HowTo",
        "name": data.get("name", ""),
        "step": how_to_steps,
    }
    for field in ["description", "totalTime", "estimatedCost", "image"]:
        if data.get(field):
            schema[field] = data[field]
    return schema


def build_product_schema(data):
    """Build Product JSON-LD."""
    schema = {"@context": "https://schema.org", "@type": "Product"}
    for key, val in data.items():
        if key == "offers" and isinstance(val, dict):
            offer = {"@type": "Offer"}
            offer.update(val)
            schema["offers"] = offer
        elif key == "brand" and isinstance(val, str):
            schema["brand"] = {"@type": "Brand", "name": val}
        elif key == "aggregateRating" and isinstance(val, dict):
            rating = {"@type": "AggregateRating"}
            rating.update(val)
            schema["aggregateRating"] = rating
        else:
            schema[key] = val
    return schema


def build_local_business_schema(data):
    """Build LocalBusiness JSON-LD."""
    schema = {"@context": "https://schema.org", "@type": "LocalBusiness"}
    for key, val in data.items():
        if key == "address" and isinstance(val, dict):
            addr = {"@type": "PostalAddress"}
            addr.update(val)
            schema["address"] = addr
        elif key == "geo" and isinstance(val, dict):
            geo = {"@type": "GeoCoordinates"}
            geo.update(val)
            schema["geo"] = geo
        else:
            schema[key] = val
    return schema


def build_event_schema(data):
    """Build Event JSON-LD."""
    schema = {"@context": "https://schema.org", "@type": "Event"}
    for key, val in data.items():
        if key == "location" and isinstance(val, dict):
            loc = {"@type": val.get("@type", "Place")}
            loc.update(val)
            schema["location"] = loc
        elif key == "location" and isinstance(val, str):
            schema["location"] = {"@type": "Place", "name": val}
        elif key == "offers" and isinstance(val, dict):
            offer = {"@type": "Offer"}
            offer.update(val)
            schema["offers"] = offer
        else:
            schema[key] = val
    return schema


def build_generic_schema(schema_type, data):
    """Build a generic JSON-LD schema for types without special handling."""
    schema = {"@context": "https://schema.org", "@type": schema_type}
    for key, val in data.items():
        if key == "publisher" and isinstance(val, dict):
            pub = {"@type": val.get("@type", "Organization")}
            pub.update(val)
            schema["publisher"] = pub
        elif key == "author" and isinstance(val, str):
            schema["author"] = {"@type": "Person", "name": val}
        elif key == "author" and isinstance(val, dict):
            author = {"@type": val.get("@type", "Person")}
            author.update(val)
            schema["author"] = author
        else:
            schema[key] = val
    return schema


BUILDERS = {
    "FAQPage": build_faq_schema,
    "HowTo": build_howto_schema,
    "Product": build_product_schema,
    "LocalBusiness": build_local_business_schema,
    "Event": build_event_schema,
}


def generate_schema(schema_type, data):
    """Generate the JSON-LD for the given type and data."""
    spec = SCHEMA_SPECS.get(schema_type)
    if not spec:
        return {"error": f"Unsupported type: {schema_type}", "supported": list(SCHEMA_SPECS.keys())}

    # Validate required fields
    missing = [f for f in spec["required"] if f not in data or not data[f]]
    warnings = []
    if missing:
        warnings.append(f"Missing required fields: {', '.join(missing)}")

    missing_rec = [f for f in spec["recommended"] if f not in data]
    if missing_rec:
        warnings.append(f"Missing recommended fields: {', '.join(missing_rec)}")

    builder = BUILDERS.get(schema_type, lambda d: build_generic_schema(schema_type, d))
    json_ld = builder(data)

    html_tag = f'<script type="application/ld+json">\n{json.dumps(json_ld, indent=2)}\n</script>'

    result = {
        "schema_type": schema_type,
        "json_ld": json_ld,
        "html_snippet": html_tag,
    }
    if warnings:
        result["warnings"] = warnings
    return result


def main():
    parser = argparse.ArgumentParser(description="Generate JSON-LD structured data markup")
    parser.add_argument("--type", required=True, choices=list(SCHEMA_SPECS.keys()),
                        help="Schema.org type")
    parser.add_argument("--data", required=True, help="JSON string with schema data")
    args = parser.parse_args()

    try:
        data = json.loads(args.data)
    except json.JSONDecodeError as e:
        print(json.dumps({"error": f"Invalid JSON in --data: {str(e)}"}))
        sys.exit(1)

    if not isinstance(data, dict):
        print(json.dumps({"error": "--data must be a JSON object"}))
        sys.exit(1)

    result = generate_schema(args.type, data)
    json.dump(result, sys.stdout, indent=2)
    print()


if __name__ == "__main__":
    main()
