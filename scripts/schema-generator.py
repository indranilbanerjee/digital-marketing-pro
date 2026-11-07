#!/usr/bin/env python3
"""Generate JSON-LD structured data markup for common schema.org types."""

import argparse
import json
import sys
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _common  # noqa: E402

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
    "BroadcastEvent": {
        "required": ["name", "startDate"],
        "recommended": ["description", "thumbnailUrl", "contentUrl", "embedUrl", "endDate"],
        "context_type": "VideoObject",
        "note": "Wraps VideoObject with publication.BroadcastEvent for LIVE badge in search",
    },
    "Clip": {
        "required": ["name", "description", "thumbnailUrl", "uploadDate"],
        "recommended": ["contentUrl", "hasPart"],
        "context_type": "VideoObject",
        "note": "Key moments/chapters within a video. Provide 'hasPart' as list of {name, startOffset, endOffset, url}",
    },
    "SeekToAction": {
        "required": ["name", "description", "thumbnailUrl", "uploadDate", "contentUrl"],
        "recommended": [],
        "context_type": "VideoObject",
        "note": "Enables seek functionality in video rich results",
    },
    "SoftwareSourceCode": {
        "required": ["name", "codeRepository"],
        "recommended": ["description", "programmingLanguage", "runtimePlatform", "author", "license", "dateCreated", "dateModified"],
        "context_type": "SoftwareSourceCode",
    },
    "SoftwareApplication": {
        "required": ["name"],
        "recommended": ["applicationCategory", "operatingSystem", "offers", "aggregateRating"],
        "context_type": "SoftwareApplication",
    },
    "ProductGroup": {
        "required": ["name", "hasVariant"],
        "recommended": ["description", "productGroupID", "variesBy"],
        "context_type": "ProductGroup",
        "note": "E-commerce product variants grouped by attributes. Provide 'hasVariant' as list of Product objects",
    },
    "ProfilePage": {
        "required": ["name"],
        "recommended": ["url", "description", "sameAs"],
        "context_type": "ProfilePage",
        "note": "Author/creator profile pages. Enhances E-E-A-T signals via mainEntity Person markup",
    },
    "Certification": {
        "required": ["name", "certificationIdentification"],
        "recommended": ["issuedBy"],
        "context_type": "Product",
        "note": "Product certifications. Replaced EnergyConsumptionDetails (April 2025)",
    },
    "ItemList": {
        "required": ["name", "itemListElement"],
        "recommended": ["itemListOrder", "numberOfItems"],
        "context_type": "ItemList",
        "note": "Roundup/listicle pages. Provide 'itemListElement' as list of {name, url, position}",
    },
}

# Schema types that are deprecated or restricted — always warn
DEPRECATIONS = {
    "HowTo": "DEPRECATED (Sept 2023): Rich results removed. Use Article format with step-by-step structure instead.",
    "FAQPage": "RESTRICTED (Aug 2023): Rich results limited to government and health authority sites only.",
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


def build_broadcast_event_schema(data):
    """Build VideoObject with BroadcastEvent publication for LIVE badge."""
    schema = {"@context": "https://schema.org", "@type": "VideoObject"}
    publication = {"@type": "BroadcastEvent", "isLiveBroadcast": True}
    for key, val in data.items():
        if key in ("startDate", "endDate"):
            publication[key] = val
        else:
            schema[key] = val
    schema["publication"] = publication
    return schema


def build_clip_schema(data):
    """Build VideoObject with Clip hasPart for key moments."""
    schema = {"@context": "https://schema.org", "@type": "VideoObject"}
    parts = data.pop("hasPart", data.pop("clips", []))
    for key, val in data.items():
        schema[key] = val
    if parts:
        clip_list = []
        for clip in parts:
            clip_obj = {"@type": "Clip"}
            clip_obj.update(clip)
            clip_list.append(clip_obj)
        schema["hasPart"] = clip_list
    return schema


def build_seek_to_action_schema(data):
    """Build VideoObject with SeekToAction potentialAction."""
    schema = {"@context": "https://schema.org", "@type": "VideoObject"}
    target_url = data.pop("targetUrl", data.pop("target", ""))
    for key, val in data.items():
        schema[key] = val
    if target_url:
        schema["potentialAction"] = {
            "@type": "SeekToAction",
            "target": f"{target_url}?t={{seek_to_second_number}}",
            "startOffset-input": "required name=seek_to_second_number",
        }
    return schema


def build_profile_page_schema(data):
    """Build ProfilePage with mainEntity Person for E-E-A-T."""
    person = {"@type": "Person"}
    for key, val in data.items():
        person[key] = val
    return {
        "@context": "https://schema.org",
        "@type": "ProfilePage",
        "mainEntity": person,
    }


def build_item_list_schema(data):
    """Build ItemList for roundup/listicle pages."""
    schema = {"@context": "https://schema.org", "@type": "ItemList"}
    items = data.pop("itemListElement", data.pop("items", []))
    for key, val in data.items():
        schema[key] = val
    if items:
        list_items = []
        for i, item in enumerate(items):
            list_item = {"@type": "ListItem", "position": item.get("position", i + 1)}
            if isinstance(item, str):
                list_item["name"] = item
            else:
                list_item.update({k: v for k, v in item.items() if k != "position"})
                if "position" not in item:
                    list_item["position"] = i + 1
            list_items.append(list_item)
        schema["itemListElement"] = list_items
    if "numberOfItems" not in schema and items:
        schema["numberOfItems"] = len(items)
    return schema


def build_product_group_schema(data):
    """Build ProductGroup with hasVariant for e-commerce variants."""
    schema = {"@context": "https://schema.org", "@type": "ProductGroup"}
    variants = data.pop("hasVariant", data.pop("variants", []))
    for key, val in data.items():
        schema[key] = val
    if variants:
        variant_list = []
        for v in variants:
            variant = {"@type": "Product"}
            for vk, vv in v.items():
                if vk == "offers" and isinstance(vv, dict):
                    offer = {"@type": "Offer"}
                    offer.update(vv)
                    variant["offers"] = offer
                else:
                    variant[vk] = vv
            variant_list.append(variant)
        schema["hasVariant"] = variant_list
    return schema


# Register all builders (new types added)
BUILDERS.update({
    "BroadcastEvent": build_broadcast_event_schema,
    "Clip": build_clip_schema,
    "SeekToAction": build_seek_to_action_schema,
    "ProfilePage": build_profile_page_schema,
    "ItemList": build_item_list_schema,
    "ProductGroup": build_product_group_schema,
})


def generate_schema(schema_type, data):
    """Generate the JSON-LD for the given type and data."""
    spec = SCHEMA_SPECS.get(schema_type)
    if not spec:
        return {"error": f"Unsupported type: {schema_type}", "supported": list(SCHEMA_SPECS.keys())}

    # Validate required fields
    missing = [f for f in spec["required"] if f not in data or not data[f]]
    warnings = []

    # Check for deprecated/restricted schema types
    if schema_type in DEPRECATIONS:
        warnings.append(DEPRECATIONS[schema_type])

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
        data = _common.json_text(args.data, "--data")
    except json.JSONDecodeError as e:
        print(json.dumps({"error": f"Invalid JSON in --data: {str(e)}"}))
        sys.exit(1)

    if not isinstance(data, dict):
        print(json.dumps({"error": "--data must be a JSON object"}))
        sys.exit(1)

    result = generate_schema(args.type, data)
    _common.finish(result)


if __name__ == "__main__":
    main()
