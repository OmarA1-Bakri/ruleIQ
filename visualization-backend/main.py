from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime, timedelta
import random
import numpy as np
import uvicorn

app = FastAPI(title="RuleIQ Visualization API", version="1.0.0")

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:3001",
        "*",
    ],  # In production, specify exact origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Health Check Endpoint
@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "service": "RuleIQ Visualization Backend",
        "version": "1.0.0",
        "uptime": random.randint(1000, 100000),
        "metrics": {
            "cpu_usage": round(random.uniform(10, 90), 2),
            "memory_usage": round(random.uniform(30, 80), 2),
            "active_connections": random.randint(10, 500),
        },
    }


# Time Series Data Endpoint
@app.get("/timeseries")
async def get_timeseries(points: int = 100, streams: int = 3):
    """Generate time series data for ECharts line/area charts"""

    base_time = datetime.now() - timedelta(hours=points)
    time_points = []

    for i in range(points):
        time_points.append((base_time + timedelta(hours=i)).isoformat())

    # Generate multiple data streams
    series_data = []
    series_names = [
        "Compliance Score",
        "Security Index",
        "Performance Metric",
        "Risk Factor",
        "Efficiency Rate",
    ]

    for stream in range(min(streams, len(series_names))):
        # Generate realistic looking data with trends
        base_value = random.uniform(50, 80)
        trend = random.uniform(-0.2, 0.3)
        volatility = random.uniform(5, 15)

        values = []
        current = base_value

        for i in range(points):
            # Add trend
            current += trend
            # Add random walk
            current += random.gauss(0, volatility / 10)
            # Add some seasonality
            current += np.sin(i / 10) * volatility / 2
            # Keep within bounds
            current = max(0, min(100, current))

            values.append(round(current, 2))

        series_data.append(
            {
                "name": series_names[stream],
                "data": values,
                "type": "line" if stream < 2 else "area",
                "smooth": True,
                "color": ["#8B5CF6", "#A855F7", "#C084FC", "#E9D5FF", "#C0C0C0"][stream],
            }
        )

    return {
        "timestamps": time_points,
        "series": series_data,
        "metadata": {
            "updated_at": datetime.now().isoformat(),
            "points": points,
            "streams": len(series_data),
        },
    }


# Candlestick Data Endpoint
@app.get("/candles")
async def get_candlestick_data(days: int = 30):
    """Generate candlestick data for financial charts"""

    candles = []
    base_price = 100
    current_price = base_price
    base_time = datetime.now() - timedelta(days=days)
    for day in range(days):
        # Generate realistic OHLC data
        daily_volatility = random.uniform(2, 8)
        random.gauss(0, 1)

        # Opening price (gap from previous close)
        gap = random.gauss(0, daily_volatility / 4)
        open_price = current_price + gap

        # Generate intraday movements
        high = open_price + abs(random.gauss(0, daily_volatility))
        low = open_price - abs(random.gauss(0, daily_volatility))

        # Closing price
        close = random.uniform(low, high)
        current_price = close

        # Volume with some correlation to volatility
        volume = int(1000000 * (1 + abs(high - low) / base_price) * random.uniform(0.5, 1.5))

        candles.append(
            {
                "timestamp": (base_time + timedelta(days=day)).isoformat(),
                "open": round(open_price, 2),
                "high": round(high, 2),
                "low": round(low, 2),
                "close": round(close, 2),
                "volume": volume,
                "color": "#10B981" if close >= open_price else "#EF4444",
            }
        )

    # Add moving averages
    ma_5 = []
    ma_20 = []

    for i in range(len(candles)):
        if i >= 4:
            ma_5.append(round(sum(c["close"] for c in candles[i - 4 : i + 1]) / 5, 2))
        else:
            ma_5.append(None)

        if i >= 19:
            ma_20.append(round(sum(c["close"] for c in candles[i - 19 : i + 1]) / 20, 2))
        else:
            ma_20.append(None)

    return {
        "candles": candles,
        "indicators": {"ma5": ma_5, "ma20": ma_20},
        "metadata": {
            "symbol": "RULE/IQ",
            "exchange": "Quantum Exchange",
            "updated_at": datetime.now().isoformat(),
        },
    }


# Network Graph Data Endpoint
@app.get("/graph")
async def get_network_graph(nodes: int = 50, clusters: int = 5):
    """Generate network graph data for Sigma.js visualization"""

    # Generate nodes
    graph_nodes = []
    node_clusters = {}

    # Define cluster centers and colors
    cluster_colors = ["#8B5CF6", "#A855F7", "#C084FC", "#10B981", "#F59E0B"]
    cluster_names = [
        "Core Systems",
        "Security Layer",
        "Data Pipeline",
        "User Interface",
        "External APIs",
    ]

    for i in range(nodes):
        cluster_id = i % clusters
        if cluster_id not in node_clusters:
            node_clusters[cluster_id] = []

        node = {
            "id": f"node_{i}",
            "label": f"{cluster_names[cluster_id]} #{i}",
            "x": random.uniform(-100, 100),
            "y": random.uniform(-100, 100),
            "size": random.uniform(5, 20),
            "color": cluster_colors[cluster_id],
            "cluster": cluster_id,
            "metrics": {
                "traffic": random.randint(100, 10000),
                "latency": round(random.uniform(1, 100), 2),
                "errors": random.randint(0, 50),
            },
        }

        graph_nodes.append(node)
        node_clusters[cluster_id].append(i)

    # Generate edges with higher probability within clusters
    edges = []
    edge_count = 0

    for i in range(nodes):
        # Connect to nodes in same cluster (higher probability)
        same_cluster = node_clusters[i % clusters]
        for j in same_cluster:
            if i != j and random.random() < 0.3:  # 30% chance within cluster
                edges.append(
                    {
                        "id": f"edge_{edge_count}",
                        "source": f"node_{i}",
                        "target": f"node_{j}",
                        "weight": random.uniform(0.1, 1),
                        "color": cluster_colors[i % clusters] + "40",  # Add transparency
                    }
                )
                edge_count += 1
        # Connect to nodes in other clusters (lower probability)
        for j in range(nodes):
            if (
                i != j and (j % clusters) != (i % clusters) and random.random() < 0.05
            ):  # 5% chance between clusters
                edges.append(
                    {
                        "id": f"edge_{edge_count}",
                        "source": f"node_{i}",
                        "target": f"node_{j}",
                        "weight": random.uniform(0.1, 0.5),
                        "color": "#C0C0C040",  # Silver with transparency
                    }
                )
                edge_count += 1

    return {
        "nodes": graph_nodes,
        "edges": edges,
        "metadata": {
            "node_count": len(graph_nodes),
            "edge_count": len(edges),
            "clusters": clusters,
            "density": len(edges) / (nodes * (nodes - 1) / 2) if nodes > 1 else 0,
            "updated_at": datetime.now().isoformat(),
        },
    }


# Vega-Lite Spec Endpoint
@app.get("/vega-spec")
async def get_vega_spec(chart_type: str = "scatter"):
    """Generate Vega-Lite specifications for various chart types"""

    # Generate sample data
    data_points = []
    for i in range(100):
        data_points.append(
            {
                "x": random.gauss(50, 15),
                "y": random.gauss(50, 15),
                "category": f"Category {random.randint(1, 5)}",
                "value": random.uniform(10, 100),
                "timestamp": (datetime.now() - timedelta(hours=100 - i)).isoformat(),
            }
        )

    specs = {
        "scatter": {
            "$schema": "https://vega.github.io/schema/vega-lite/v5.json",
            "description": "Interactive Scatter Plot",
            "data": {"values": data_points},
            "mark": {"type": "point", "filled": True, "size": 100},
            "encoding": {
                "x": {"field": "x", "type": "quantitative", "title": "X Axis"},
                "y": {"field": "y", "type": "quantitative", "title": "Y Axis"},
                "color": {
                    "field": "category",
                    "type": "nominal",
                    "scale": {"range": ["#8B5CF6", "#A855F7", "#C084FC", "#10B981", "#F59E0B"]},
                },
                "tooltip": [
                    {"field": "x", "type": "quantitative", "format": ".2f"},
                    {"field": "y", "type": "quantitative", "format": ".2f"},
                    {"field": "category", "type": "nominal"},
                ],
            },
            "config": {
                "background": "#0A0A0B",
                "axis": {
                    "gridColor": "#374151",
                    "domainColor": "#9CA3AF",
                    "tickColor": "#9CA3AF",
                    "labelColor": "#9CA3AF",
                },
                "legend": {"labelColor": "#9CA3AF", "titleColor": "#F3F4F6"},
            },
        }
    }

    return specs.get(chart_type, specs["scatter"])


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)
