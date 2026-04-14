from __future__ import annotations

import argparse
import json
from datetime import datetime
from io import BytesIO
from pathlib import Path
from typing import Sequence

import july
import matplotlib
matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import seaborn as sns


def _filter_by_range(
    dates: Sequence[datetime],
    values: Sequence[float],
    start: datetime | None = None,
    end: datetime | None = None,
) -> tuple[list[datetime], list[float]]:
    pairs = sorted(zip(dates, values), key=lambda p: p[0])
    if start is not None:
        pairs = [(d, v) for d, v in pairs if d >= start]
    if end is not None:
        pairs = [(d, v) for d, v in pairs if d <= end]
    if not pairs:
        return [], []
    return [d for d, _ in pairs], [v for _, v in pairs]


def trend_plot(
    dates: Sequence[datetime],
    values: Sequence[float],
    *,
    title: str = "",
    goal: float | None = None,
    start: datetime | None = None,
    end: datetime | None = None,
) -> bytes:
    """Scatter plot with regression trendline. Returns PNG bytes."""
    dates, values = _filter_by_range(dates, values, start, end)
    if not dates:
        raise ValueError("trend_plot requires at least one data point")

    fig, ax = plt.subplots(dpi=600)
    sns.regplot(x=[mdates.date2num(d) for d in dates], y=values, ax=ax)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m-%d"))
    plt.xticks(rotation=45)
    if title:
        plt.title(title)

    if goal is not None:
        ax.axhline(y=goal, color="red", linestyle="--", linewidth=2, label=f"Goal: {goal}")
        plt.legend(loc="best")

    y_min = min(values) - 1
    y_max = max(values) + 1
    if goal is not None:
        y_min = min(y_min, goal - 1)
        y_max = max(y_max, goal + 1)
    plt.ylim(y_min, y_max)

    return _figure_to_png(fig)


def calendar_heatmap(
    dates: Sequence[datetime],
    values: Sequence[float],
    *,
    title: str = "",
    start: datetime | None = None,
    end: datetime | None = None,
) -> list[tuple[str, bytes]]:
    """Calendar heatmap. Returns list of (label, png_bytes) tuples.

    Automatically splits into one image per calendar year when data
    spans multiple years.
    """
    dates, values = _filter_by_range(dates, values, start, end)
    if not dates:
        raise ValueError("calendar_heatmap requires at least one data point")

    years = sorted({d.year for d in dates})
    months = {(d.year, d.month) for d in dates}
    cmap = "RdYlGn"
    display = title or "heatmap"

    if len(months) == 1:
        fig = july.month_plot(
            dates, values,
            month=dates[0].month,
            value_label=True,
            title=display,
            titlesize="small",
            dpi=600,
            cmap=cmap,
        )
        return [(display, _figure_to_png(fig))]

    if len(years) == 1:
        fig = july.calendar_plot(
            dates, values,
            dpi=300,
            value_label=True,
            cmap=cmap,
            title=display,
        )
        _fix_calendar_title_spacing(fig)
        return [(display, _figure_to_png(fig, use_tight_layout=False))]

    images: list[tuple[str, bytes]] = []
    for year in years:
        yd = [d for d in dates if d.year == year]
        yv = [v for d, v in zip(dates, values) if d.year == year]
        label = f"{display} ({year})"
        fig = july.calendar_plot(
            yd, yv,
            dpi=300,
            value_label=True,
            cmap=cmap,
            title=label,
        )
        _fix_calendar_title_spacing(fig)
        images.append((label, _figure_to_png(fig, use_tight_layout=False)))
    return images


def _fix_calendar_title_spacing(fig_or_ax) -> None:
    """Push title up and add space between title and month grids."""
    import numpy as np

    if isinstance(fig_or_ax, np.ndarray):
        fig = fig_or_ax.flat[0].figure
    elif hasattr(fig_or_ax, "figure"):
        fig = fig_or_ax.figure
    else:
        fig = fig_or_ax
    fig.subplots_adjust(top=0.72)
    for txt in fig.texts:
        txt.set_y(0.98)


def _figure_to_png(fig_or_ax, *, use_tight_layout: bool = True) -> bytes:
    import numpy as np

    if isinstance(fig_or_ax, np.ndarray):
        fig = fig_or_ax.flat[0].figure
    elif hasattr(fig_or_ax, "figure"):
        fig = fig_or_ax.figure
    else:
        fig = fig_or_ax
    buffer = BytesIO()
    if use_tight_layout:
        fig.tight_layout()
    fig.savefig(buffer, format="png")
    buffer.seek(0)
    data = buffer.getvalue()
    plt.close(fig)
    return data


def main():
    parser = argparse.ArgumentParser(description="Generate scatter and calendar plots")
    parser.add_argument("input_json", help="Path to input JSON file")
    parser.add_argument("--outdir", default="out", help="Output directory (default: out)")
    args = parser.parse_args()

    data = json.loads(Path(args.input_json).read_text())
    dates = [datetime.fromisoformat(p["date"]) for p in data["points"]]
    values = [float(p["value"]) for p in data["points"]]
    title = data.get("title", "")
    goal = data.get("goal")
    start = datetime.fromisoformat(data["start"]) if "start" in data else None
    end = datetime.fromisoformat(data["end"]) if "end" in data else None

    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    trend_bytes = trend_plot(dates, values, title=title, goal=goal, start=start, end=end)
    (outdir / "trend.png").write_bytes(trend_bytes)

    for label, png in calendar_heatmap(dates, values, title=title, start=start, end=end):
        safe_name = label.replace(" ", "_").replace("(", "").replace(")", "")
        (outdir / f"{safe_name}.png").write_bytes(png)

    print(outdir)


if __name__ == "__main__":
    main()
