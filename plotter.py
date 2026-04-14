from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from datetime import datetime
from io import BytesIO
from pathlib import Path
from typing import Iterable

import july
import matplotlib
matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import seaborn as sns


@dataclass(frozen=True)
class MetricPoint:
    recorded_at: datetime
    value: float


@dataclass(frozen=True)
class LabeledImage:
    label: str
    image_bytes: bytes


def _filter_points(
    points: Iterable[MetricPoint],
    start: datetime | None = None,
    end: datetime | None = None,
) -> list[MetricPoint]:
    ordered = sorted(points, key=lambda point: point.recorded_at)
    if start is not None:
        ordered = [p for p in ordered if p.recorded_at >= start]
    if end is not None:
        ordered = [p for p in ordered if p.recorded_at <= end]
    return ordered


def trend_plot(
    metric_name: str,
    points: Iterable[MetricPoint],
    goal_value: float | None = None,
    title: str | None = None,
    start: datetime | None = None,
    end: datetime | None = None,
) -> bytes:
    ordered = _filter_points(points, start=start, end=end)
    if not ordered:
        raise ValueError("trend_plot requires at least one point")

    dates = [point.recorded_at for point in ordered]
    values = [point.value for point in ordered]

    plt.rcParams["figure.dpi"] = 600
    fig, ax = plt.subplots(dpi=600)

    sns.regplot(
        x=[mdates.date2num(value) for value in dates],
        y=values,
        ax=ax,
    )
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m-%d"))
    plt.xticks(rotation=45)
    plt.title(title or metric_name)

    if goal_value is not None:
        ax.axhline(
            y=goal_value,
            color="red",
            linestyle="--",
            linewidth=2,
            label=f"Goal: {goal_value}",
        )
        plt.legend(loc="best")

    y_min = min(values) - 1
    y_max = max(values) + 1
    if goal_value is not None:
        y_min = min(y_min, goal_value - 1)
        y_max = max(y_max, goal_value + 1)
    plt.ylim(y_min, y_max)

    return _figure_to_png(fig)


def calendar_heatmap(
    metric_name: str,
    points: Iterable[MetricPoint],
    title: str | None = None,
    start: datetime | None = None,
    end: datetime | None = None,
) -> list[LabeledImage]:
    ordered = _filter_points(points, start=start, end=end)
    if not ordered:
        raise ValueError("calendar_heatmap requires at least one point")

    dates = [point.recorded_at for point in ordered]
    values = [point.value for point in ordered]
    years = sorted({point.recorded_at.year for point in ordered})
    months = {(point.recorded_at.year, point.recorded_at.month) for point in ordered}
    cmap = "RdYlGn"

    display_name = title or metric_name

    if len(months) == 1:
        only_month = dates[0].month
        fig = july.month_plot(
            dates,
            values,
            month=only_month,
            value_label=True,
            title=display_name,
            titlesize="small",
            dpi=600,
            cmap=cmap,
        )
        return [LabeledImage(label=metric_name, image_bytes=_figure_to_png(fig))]

    if len(years) == 1:
        fig = july.calendar_plot(
            dates,
            values,
            dpi=300,
            value_label=True,
            cmap=cmap,
            title=display_name,
        )
        return [LabeledImage(label=metric_name, image_bytes=_figure_to_png(fig))]

    images: list[LabeledImage] = []
    for year in years:
        year_dates = [point.recorded_at for point in ordered if point.recorded_at.year == year]
        year_values = [point.value for point in ordered if point.recorded_at.year == year]
        fig = july.calendar_plot(
            year_dates,
            year_values,
            dpi=300,
            value_label=True,
            cmap=cmap,
            title=f"{display_name} ({year})",
        )
        images.append(LabeledImage(label=f"{metric_name}_{year}", image_bytes=_figure_to_png(fig)))
    return images


def plot_bundle(
    metric_name: str,
    points: Iterable[MetricPoint],
    goal_value: float | None = None,
    title: str | None = None,
    start: datetime | None = None,
    end: datetime | None = None,
) -> dict[str, object]:
    ordered = _filter_points(points, start=start, end=end)
    return {
        "trend": trend_plot(metric_name=metric_name, points=ordered, goal_value=goal_value, title=title),
        "heatmaps": calendar_heatmap(metric_name=metric_name, points=ordered, title=title),
    }


def metric_points_from_json(payload: str | dict[str, object]) -> dict:
    data = json.loads(payload) if isinstance(payload, str) else payload
    metric_name = str(data["metric_name"])
    goal_value = data.get("goal_value")
    raw_points = data["points"]

    points = [
        MetricPoint(
            recorded_at=datetime.fromisoformat(item["recorded_at"]),
            value=float(item["value"]),
        )
        for item in raw_points
    ]
    result = {
        "metric_name": metric_name,
        "points": points,
        "goal_value": float(goal_value) if goal_value is not None else None,
    }
    if "title" in data:
        result["title"] = str(data["title"])
    if "start" in data:
        result["start"] = datetime.fromisoformat(data["start"])
    if "end" in data:
        result["end"] = datetime.fromisoformat(data["end"])
    return result


def main():
    parser = argparse.ArgumentParser(description="Generate metric trend and heatmap plots")
    parser.add_argument("input_json", help="Path to input JSON payload")
    parser.add_argument("--outdir", default="out", help="Directory to write PNG files into")
    args = parser.parse_args()

    payload = json.loads(Path(args.input_json).read_text())
    parsed = metric_points_from_json(payload)
    bundle = plot_bundle(**parsed)

    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    (outdir / "trend.png").write_bytes(bundle["trend"])
    for image in bundle["heatmaps"]:
        (outdir / f"{image.label}.png").write_bytes(image.image_bytes)

    print(outdir)


def _figure_to_png(fig_or_ax) -> bytes:
    import numpy as np

    if isinstance(fig_or_ax, np.ndarray):
        fig = fig_or_ax.flat[0].figure
    elif hasattr(fig_or_ax, "figure"):
        fig = fig_or_ax.figure
    else:
        fig = fig_or_ax
    buffer = BytesIO()
    fig.tight_layout()
    fig.savefig(buffer, format="png")
    buffer.seek(0)
    image_bytes = buffer.getvalue()
    plt.close(fig)
    return image_bytes


if __name__ == "__main__":
    main()
