"""Starter contract and read-only local adapter for published model outputs."""
import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Annotated, Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator

Nonnegative = Annotated[float, Field(ge=0, allow_inf_nan=False)]
Probability = Annotated[float, Field(ge=0, le=1, allow_inf_nan=False)]
Identifier = Annotated[str, Field(min_length=1, max_length=120, pattern=r"^[A-Za-z0-9_.-]+$")]
Position = tuple[Annotated[float, Field(ge=-180, le=180, allow_inf_nan=False)], Annotated[float, Field(ge=-90, le=90, allow_inf_nan=False)]]

class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid")

class LineGeometry(Contract):
    type: Literal["LineString"]
    coordinates: list[Position] = Field(min_length=2)

class PointGeometry(Contract):
    type: Literal["Point"]
    coordinates: Position

class SiteProperties(Contract):
    site_id: Identifier
    site_type: Literal["segment", "intersection"]
    road_name: str = Field(min_length=1, max_length=200)
    map_segment_id: str | None = None
    length_mi: Nonnegative | None = None
    fsi_rate: Nonnegative | None = None
    rank: int = Field(ge=1, strict=True)
    flagged: bool = Field(strict=True)
    in_hin: bool | None = None
    top_factors: list[str] = Field(default_factory=list)
    crash_history: str | None = None

class SiteFeature(Contract):
    type: Literal["Feature"] = "Feature"
    properties: SiteProperties
    geometry: Annotated[LineGeometry | PointGeometry, Field(discriminator="type")]

    @model_validator(mode="after")
    def matching_geometry(self):
        if self.geometry.type != ("LineString" if self.properties.site_type == "segment" else "Point"):
            raise ValueError("Site type and geometry must agree")
        return self

class MethodResult(Contract):
    method: Literal["A", "B", "C"]
    label: str
    capture_rate: Probability
    confidence_interval: tuple[Probability, Probability]
    flagged_mileage: Nonnegative
    test_fsi_count: int = Field(ge=0, strict=True)

    @model_validator(mode="after")
    def ordered_interval(self):
        if self.confidence_interval[0] > self.confidence_interval[1]:
            raise ValueError("Confidence interval must be ordered")
        return self

class Backtest(Contract):
    training_cutoff: str
    test_window: str
    methods: list[MethodResult]

    @model_validator(mode="after")
    def unique_methods(self):
        if len({method.method for method in self.methods}) != len(self.methods):
            raise ValueError("Backtest methods must be unique")
        return self

class Memo(Contract):
    title: str
    text: str
    references: list[str] = Field(min_length=1)
    grounding_passed: bool = Field(strict=True)

    @model_validator(mode="after")
    def passed_grounding(self):
        if not self.grounding_passed:
            raise ValueError("Only memos marked grounding-passed may be published")
        return self

class PublishedRun(Contract):
    schema_version: Literal["1.0"] = "1.0"
    run_id: Identifier
    model_name: str = Field(min_length=1)
    published_at: datetime
    status: Literal["published"]
    is_demo: bool = Field(default=False, strict=True)
    risk_unit: str = Field(min_length=1)
    sites: list[SiteFeature]
    backtest: Backtest | None = None
    memos: dict[str, Memo] = Field(default_factory=dict)

    @model_validator(mode="after")
    def valid_references(self):
        ids = [site.properties.site_id for site in self.sites]
        if len(ids) != len(set(ids)):
            raise ValueError("Site IDs must be unique within a run")
        mappings = [site.properties.map_segment_id for site in self.sites if site.properties.map_segment_id is not None]
        if len(mappings) != len(set(mappings)) or any(not mapping for mapping in mappings):
            raise ValueError("Optional map-section mappings must be nonempty and unique within a run")
        if not set(self.memos).issubset(ids):
            raise ValueError("Memos must reference sites in the same run")
        if self.published_at.tzinfo is None:
            raise ValueError("Published timestamp requires a timezone")
        return self

def results_directory():
    return Path(os.environ.get("ATSC_MODEL_RESULTS_DIR", Path(__file__).resolve().parents[1] / "data" / "published"))

def load_runs(directory=None):
    """A broken new file must not hide other valid published runs."""
    runs, invalid = {}, 0
    for path in sorted((directory or results_directory()).glob("*.json")):
        try:
            run = PublishedRun.model_validate_json(path.read_text())
            if run.run_id in runs:
                raise ValueError("Duplicate run ID")
            runs[run.run_id] = run
        except (ValueError, OSError) as error:
            logging.getLogger(__name__).warning("Ignoring invalid model output %s: %s", path.name, error)
            invalid += 1
    return sorted(runs.values(), key=lambda run: run.published_at, reverse=True), invalid

def run_summary(run):
    return {**run.model_dump(mode="json", exclude={"sites", "backtest", "memos"}), "site_count": len(run.sites)}

if __name__ == "__main__":
    import sys
    run = PublishedRun.model_validate_json(Path(sys.argv[1]).read_text())
    print(json.dumps(run_summary(run), indent=2))
