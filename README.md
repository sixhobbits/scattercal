# Scattercal

Opinionated metric visualization: scatter plots with trendlines and calendar heatmaps, from simple x/y data.

## Why not just use seaborn / july directly?

Both are great libraries, but every time you want a "quick metric plot" you end up writing the same 30-40 lines of boilerplate:

- Sort and filter points by date range
- Configure matplotlib backends and DPI
- Format x-axis dates
- Add a goal line with legend
- Scale y-axis to fit both data and goal
- Split multi-year data into per-year calendar heatmaps
- Choose month-plot vs calendar-plot based on data span
- Serialize figures to PNG bytes and clean up

metric-plotter wraps all of that into two function calls (`trend_plot` and `calendar_heatmap`) that accept the same simple inputs and always do the right thing.

## Install

```bash
pip install matplotlib seaborn july
```

## API

### `MetricPoint(recorded_at: datetime, value: float)`

A single data point.

### `trend_plot(metric_name, points, goal_value=None, title=None, start=None, end=None) -> bytes`

Scatter plot with seaborn regression trendline. Returns PNG bytes.

### `calendar_heatmap(metric_name, points, title=None, start=None, end=None) -> list[LabeledImage]`

GitHub-style calendar heatmap. Automatically picks the right layout:
- 1 month of data: month plot
- 1 year of data: single calendar
- Multiple years: one calendar per year

### `plot_bundle(metric_name, points, goal_value=None, title=None, start=None, end=None) -> dict`

Returns both `{"trend": bytes, "heatmaps": list[LabeledImage]}` in one call.

### `metric_points_from_json(payload) -> dict`

Parse a JSON payload into kwargs for the other functions.

## Examples

### Scatter plot with trendline and goal

```python
from datetime import datetime
from plotter import MetricPoint, trend_plot

points = [
    MetricPoint(datetime(2025, 1, 5), 3),
    MetricPoint(datetime(2025, 1, 12), 4),
    MetricPoint(datetime(2025, 2, 1), 5),
    MetricPoint(datetime(2025, 2, 15), 4),
    MetricPoint(datetime(2025, 3, 3), 6),
    MetricPoint(datetime(2025, 3, 20), 7),
]

png_bytes = trend_plot("Pullups", points, goal_value=10)

with open("pullups_trend.png", "wb") as f:
    f.write(png_bytes)
```

### 1-month heatmap

```python
from datetime import datetime
from plotter import MetricPoint, calendar_heatmap

points = [MetricPoint(datetime(2025, 3, d), d % 7 + 1) for d in range(1, 32)]

images = calendar_heatmap("Pullups", points,
                          start=datetime(2025, 3, 1),
                          end=datetime(2025, 3, 31))
for img in images:
    with open(f"{img.label}.png", "wb") as f:
        f.write(img.image_bytes)
```

### 3-month heatmap

```python
from datetime import datetime, timedelta
from plotter import MetricPoint, calendar_heatmap

base = datetime(2025, 1, 1)
points = [MetricPoint(base + timedelta(days=d), (d % 10) + 1) for d in range(90)]

images = calendar_heatmap("Pullups", points,
                          start=datetime(2025, 1, 1),
                          end=datetime(2025, 3, 31))
```

### 6-month heatmap

```python
from datetime import datetime, timedelta
from plotter import MetricPoint, calendar_heatmap

base = datetime(2025, 1, 1)
points = [MetricPoint(base + timedelta(days=d), (d % 12) + 1) for d in range(180)]

images = calendar_heatmap("Pullups", points,
                          start=datetime(2025, 1, 1),
                          end=datetime(2025, 6, 30))
```

### 12-month heatmap

```python
from datetime import datetime, timedelta
from plotter import MetricPoint, calendar_heatmap

base = datetime(2025, 1, 1)
points = [MetricPoint(base + timedelta(days=d), (d % 15) + 1) for d in range(365)]

images = calendar_heatmap("Pullups", points,
                          start=datetime(2025, 1, 1),
                          end=datetime(2025, 12, 31))
# Returns 1 image (single year)
```

### 24-month heatmap (auto-splits by year)

```python
from datetime import datetime, timedelta
from plotter import MetricPoint, calendar_heatmap

base = datetime(2024, 1, 1)
points = [MetricPoint(base + timedelta(days=d), (d % 15) + 1) for d in range(730)]

images = calendar_heatmap("Pullups", points,
                          start=datetime(2024, 1, 1),
                          end=datetime(2025, 12, 31))
# Returns 2 images: "Pullups (2024)" and "Pullups (2025)"
for img in images:
    with open(f"{img.label}.png", "wb") as f:
        f.write(img.image_bytes)
```

## CLI

```bash
python plotter.py data.json --outdir out
```

JSON shape:

```json
{
  "metric_name": "pullups",
  "goal_value": 10,
  "title": "Daily Pullups",
  "start": "2025-01-01",
  "end": "2025-12-31",
  "points": [
    {"recorded_at": "2025-01-01T12:00:00", "value": 3},
    {"recorded_at": "2025-01-02T12:00:00", "value": 4}
  ]
}
```

Only `metric_name` and `points` are required. `goal_value`, `title`, `start`, and `end` are optional.
