"""Limit prompt size while retaining complete provider responses in the ledger."""


def compact(value):
    if isinstance(value, dict):
        if "candidates" in value:
            candidates, lookup = {}, {}
            for candidate_id, item in value["candidates"].items():
                key = item.get("url") or item.get("name", candidate_id)
                metadata = {
                    field: item[field]
                    for field in ("day", "available_days")
                    if field in item
                }
                if key in lookup:
                    candidates[candidate_id] = {**metadata, "same_as": lookup[key]}
                else:
                    lookup[key] = candidate_id
                    candidates[candidate_id] = {
                        **metadata,
                        **{
                            field: (
                                item[field][:350]
                                if field == "description"
                                else compact(item[field])
                            )
                            for field in ("name", "kind", "description", "coordinates")
                            if field in item
                        },
                    }
            return {
                **compact(
                    {key: item for key, item in value.items() if key != "candidates"}
                ),
                "candidates": candidates,
            }
        return {
            key: compact(item)
            for key, item in value.items()
            if key
            not in (
                "tool_trace",
                "itineraries",
                "available_flights",
                "hotels",
                "segments",
                "raw_price",
                "fares",
            )
        }
    if isinstance(value, list):
        return [compact(item) for item in value]
    if isinstance(value, str) and len(value) > 800:
        return value[:800]
    return value
