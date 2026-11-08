"""Downloads contain only results from the requested published run."""
import csv
import io


def csv_value(value):
    if value is None:
        return ""
    if isinstance(value, str) and value.lstrip().startswith(("=", "+", "-", "@")):
        return "'" + value
    return value


def sites_csv(run):
    buffer = io.StringIO(newline="")
    fields = ["run_id", "is_demo", "risk_unit", "site_id", "site_type", "road_name", "length_mi", "fsi_rate", "rank", "flagged", "in_hin", "map_segment_id"]
    writer = csv.DictWriter(buffer, fieldnames=fields)
    writer.writeheader()
    for site in sorted(run.sites, key=lambda feature: feature.properties.rank):
        row = {**site.properties.model_dump(), "run_id": run.run_id, "risk_unit": run.risk_unit, "is_demo": run.is_demo}
        writer.writerow({field: csv_value(row.get(field)) for field in fields})
    return buffer.getvalue()
