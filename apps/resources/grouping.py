"""Group resources by subcategory for the listing pages."""

from __future__ import annotations


def group_by_subcategory(resources):
    """Group an iterable of resources by subcategory.

    Returns a list of ``{"subcategory": <ResourceSubcategory|None>, "resources": [...]}``
    ordered by the subcategory's (display_order, name); resources without a
    subcategory come last. Resource order within each group is preserved.
    """
    buckets: dict = {}
    order = []
    for resource in resources:
        sub = resource.subcategory
        key = sub.pk if sub is not None else None
        if key not in buckets:
            buckets[key] = {"subcategory": sub, "resources": []}
            order.append(key)
        buckets[key]["resources"].append(resource)

    def sort_key(key):
        sub = buckets[key]["subcategory"]
        if sub is None:
            return (1, 0, "")
        return (0, sub.display_order, sub.name)

    return [buckets[key] for key in sorted(order, key=sort_key)]
