"""
Visualization Service for generating charts and graphs from data.

Supports multiple chart types using matplotlib and plotly for static and interactive visualizations.
Charts can be returned as base64 encoded images or saved to files.
"""

import base64
import io
import logging
import os
import re
import warnings
from datetime import datetime
from typing import Any, Literal

import matplotlib
import matplotlib.pyplot as plt
import pandas as pd
import plotly.express as px
import seaborn as sns

from shared.utils.provider_errors import aeris_unavailable_message

# Use non-interactive backend for server environments
matplotlib.use("Agg")

# Suppress font warnings for missing Unicode characters (subscripts/superscripts)
warnings.filterwarnings('ignore', category=UserWarning, module='matplotlib')

logger = logging.getLogger(__name__)

ChartType = Literal[
    "line", "bar", "scatter", "histogram", "box", "heatmap", "pie", "area", "violin", "timeseries"
]

ChartFormat = Literal["base64", "file", "plotly_json"]


class VisualizationService:
    """Service for creating data visualizations and charts."""

    def __init__(self):
        """Initialize visualization service with default styles."""
        # Set professional style for matplotlib
        sns.set_style("whitegrid")
        plt.rcParams.update(
            {
                "figure.figsize": (10, 6),  # Slightly smaller for faster rendering
                "figure.dpi": 90,  # Reduced DPI for faster generation
                "font.family": "DejaVu Sans",  # Font that supports Unicode subscripts
                "font.size": 10,
                "axes.labelsize": 11,
                "axes.titlesize": 13,
                "legend.fontsize": 9,
                "xtick.labelsize": 9,
                "ytick.labelsize": 9,
            }
        )

    def generate_chart(
        self,
        data: list[dict[str, Any]] | pd.DataFrame,
        chart_type: ChartType,
        x_column: str | None = None,
        y_column: str | None = None,
        title: str | None = None,
        x_label: str | None = None,
        y_label: str | None = None,
        color_column: str | None = None,
        output_format: ChartFormat = "base64",
        interactive: bool = False,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """
        Generate a chart from data.

        Args:
            data: Data as list of dicts or pandas DataFrame
            chart_type: Type of chart to generate
            x_column: Column name for x-axis
            y_column: Column name for y-axis (can be list for multiple series)
            title: Chart title
            x_label: X-axis label
            y_label: Y-axis label
            color_column: Column to use for color coding
            output_format: Output format (base64, file, plotly_json)
            interactive: Use plotly for interactive charts
            **kwargs: Additional parameters specific to chart type

        Returns:
            dict with chart data, metadata, and generation info
        """
        try:
            # Convert list of dicts to DataFrame if needed
            if isinstance(data, list):
                if not data:
                    raise ValueError("Empty data provided")
                df = pd.DataFrame(data)
            else:
                df = data.copy()

            # OPTIMIZATION: Limit data size to prevent timeout and memory issues
            # For chart visualization, prioritize recent/relevant data
            MAX_ROWS = 1000  # Reduced from 5000 for faster processing
            original_row_count = len(df)
            data_was_sampled = False

            if len(df) > MAX_ROWS:
                logger.warning(f"Large dataset ({len(df)} rows) detected. Sampling to {MAX_ROWS} rows for visualization.")
                data_was_sampled = True

                # Intelligent sampling: prioritize recent data for time-series
                # Keep last 70%, first 20%, sample middle 10%
                last_count = int(MAX_ROWS * 0.7)
                first_count = int(MAX_ROWS * 0.2)
                middle_count = MAX_ROWS - last_count - first_count

                last_part = df.tail(last_count)
                first_part = df.head(first_count)

                if len(df) > (first_count + last_count + 10):
                    middle_part = df.iloc[first_count:-last_count].sample(
                        min(middle_count, len(df) - first_count - last_count),
                        random_state=42
                    )
                    df = pd.concat([first_part, middle_part, last_part]).sort_index()
                else:
                    df = pd.concat([first_part, last_part]).sort_index()

                logger.info(f"Sampled dataset: {original_row_count} → {len(df)} rows (prioritizing recent data)")

            # Auto-detect columns if not provided
            if x_column is None and len(df.columns) > 0:
                x_column = df.columns[0]
            if y_column is None and len(df.columns) > 1:
                y_column = df.columns[1]

            # Set default labels
            if title is None:
                title = f"{chart_type.title()} Chart"
            if x_label is None and x_column:
                x_label = x_column
            if y_label is None and y_column:
                y_label = y_column if isinstance(y_column, str) else "Value"

            # Generate chart based on type and format
            if interactive or output_format == "plotly_json":
                result = self._generate_plotly_chart(
                    df,
                    chart_type,
                    x_column,
                    y_column,
                    title,
                    x_label,
                    y_label,
                    color_column,
                    **kwargs,
                )
            else:
                result = self._generate_matplotlib_chart(
                    df,
                    chart_type,
                    x_column,
                    y_column,
                    title,
                    x_label,
                    y_label,
                    color_column,
                    output_format=output_format,
                    **kwargs,
                )

            # Add metadata with sampling info
            result.update(
                {
                    "chart_type": chart_type,
                    "timestamp": datetime.now().isoformat(),
                    "data_rows": len(df),
                    "original_rows": original_row_count,
                    "data_sampled": data_was_sampled,
                    "columns_used": {"x": x_column, "y": y_column, "color": color_column},
                    "sampling_notice": (
                        f"📊 Data sampled: Showing {len(df)} of {original_row_count} data points "
                        f"(prioritizing recent data for clarity)"
                    ) if data_was_sampled else None,
                }
            )

            return result

        except Exception as e:
            logger.error(f"Error generating chart: {e}", exc_info=True)
            return {
                "success": False,
                "error": "Unable to generate a visualization with the provided data and parameters.",
                "message": aeris_unavailable_message(),
                "chart_type": chart_type,
            }

    def _generate_matplotlib_chart(
        self,
        df: pd.DataFrame,
        chart_type: ChartType,
        x_column: str | None,
        y_column: str | None,
        title: str,
        x_label: str | None,
        y_label: str | None,
        color_column: str | None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Generate chart using matplotlib."""
        fig, ax = plt.subplots(figsize=kwargs.get("figsize", (12, 6)))

        try:
            # Handle multiple y columns - convert to list
            if y_column is None:
                y_columns = []
            elif isinstance(y_column, str):
                # Handle comma-separated columns for multi-series
                if ',' in y_column:
                    y_columns = [col.strip() for col in y_column.split(',')]
                else:
                    y_columns = [y_column]
            else:
                y_columns = list(y_column)  # type: ignore

            # For histogram, if no y_column provided, use first numeric column
            if chart_type == "histogram" and not y_columns:
                numeric_cols = df.select_dtypes(include=['number']).columns.tolist()
                if numeric_cols:
                    y_columns = [numeric_cols[0]]
                else:
                    raise ValueError("No numeric columns found for histogram")

            if chart_type == "line":
                for y_col in y_columns:
                    ax.plot(df[x_column], df[y_col], marker="o", label=y_col)
                ax.legend()

            elif chart_type == "bar":
                if len(y_columns) == 1:
                    ax.bar(df[x_column], df[y_columns[0]])
                else:
                    df.plot(x=x_column, y=y_columns, kind="bar", ax=ax)

            elif chart_type == "scatter":
                if color_column and color_column in df.columns:
                    scatter = ax.scatter(
                        df[x_column],
                        df[y_columns[0]],
                        c=df[color_column],
                        cmap="viridis",
                        alpha=0.6,
                    )
                    plt.colorbar(scatter, ax=ax, label=color_column)
                else:
                    ax.scatter(df[x_column], df[y_columns[0]], alpha=0.6)

            elif chart_type == "histogram":
                ax.hist(df[y_columns[0]], bins=kwargs.get("bins", 30), edgecolor="black", alpha=0.7)
                x_label = y_columns[0]
                y_label = "Frequency"

            elif chart_type == "box":
                if len(y_columns) == 1:
                    ax.boxplot(df[y_columns[0]])
                else:
                    df[y_columns].boxplot(ax=ax)

            elif chart_type == "area":
                for y_col in y_columns:
                    ax.fill_between(df[x_column], df[y_col], alpha=0.4, label=y_col)
                ax.legend()

            elif chart_type == "pie":
                ax.pie(df[y_columns[0]], labels=df[x_column], autopct="%1.1f%%")

            elif chart_type == "violin":
                parts = ax.violinplot(
                    [df[y_col].dropna() for y_col in y_columns], showmeans=True, showmedians=True
                )
                ax.set_xticks(range(1, len(y_columns) + 1))
                ax.set_xticklabels(y_columns)

            elif chart_type == "timeseries":
                # Try to parse x_column as datetime
                df[x_column] = pd.to_datetime(df[x_column], errors="coerce")
                for y_col in y_columns:
                    ax.plot(df[x_column], df[y_col], marker="o", label=y_col)
                ax.legend()
                plt.xticks(rotation=45)

            else:
                # Default to line chart
                for y_col in y_columns:
                    ax.plot(df[x_column], df[y_col], marker="o", label=y_col)
                ax.legend()

            # Set labels and title
            ax.set_title(title, fontsize=14, fontweight="bold")
            if x_label and chart_type != "pie":
                ax.set_xlabel(x_label, fontsize=12)
            if y_label and chart_type != "pie":
                ax.set_ylabel(y_label, fontsize=12)

            # Improve layout
            plt.tight_layout()

            output_format: str = str(kwargs.get("output_format", "base64")).lower()

            # Option A: write chart to a file and return an API URL (best for markdown rendering)
            if output_format == "file":
                storage_dir = os.getenv("CHART_STORAGE_DIR", "/app/data/charts")
                os.makedirs(storage_dir, exist_ok=True)

                # Create a safe filename from title + timestamp
                safe_title = re.sub(r"[^a-zA-Z0-9_-]+", "-", (title or "chart").strip()).strip("-")
                safe_title = safe_title[:60] if safe_title else "chart"
                filename = f"{safe_title}-{datetime.now().strftime('%Y%m%d-%H%M%S-%f')}.png"
                file_path = os.path.join(storage_dir, filename)

                plt.savefig(file_path, format="png", dpi=100, bbox_inches="tight")
                plt.close(fig)

                public_base_url = os.getenv("PUBLIC_BASE_URL", "").rstrip("/")
                chart_path = f"/api/v1/visualization/charts/{filename}"
                chart_url = f"{public_base_url}{chart_path}" if public_base_url else chart_path

                # Return a URL so markdown renderers can load the image.
                return {
                    "success": True,
                    "chart_data": chart_url,
                    "format": "png",
                    "engine": "matplotlib",
                    "storage": "file",
                    "file_name": filename,
                }

            # Option B: base64 data URI (may be blocked by some markdown renderers/sanitizers)
            buffer = io.BytesIO()
            plt.savefig(buffer, format="png", dpi=100, bbox_inches="tight")
            buffer.seek(0)
            image_base64 = base64.b64encode(buffer.read()).decode("utf-8")
            plt.close(fig)

            return {
                "success": True,
                "chart_data": f"data:image/png;base64,{image_base64}",
                "format": "png",
                "engine": "matplotlib",
                "storage": "base64",
            }

        except Exception as e:
            plt.close(fig)
            raise e

    def _generate_plotly_chart(
        self,
        df: pd.DataFrame,
        chart_type: ChartType,
        x_column: str | None,
        y_column: str | None,
        title: str,
        x_label: str | None,
        y_label: str | None,
        color_column: str | None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Generate interactive chart using plotly."""
        try:
            # Handle multiple y columns - convert to list
            if y_column is None:
                y_columns = []
            elif isinstance(y_column, str):
                y_columns = [y_column]
            else:
                y_columns = list(y_column)  # type: ignore

            if chart_type == "line" or chart_type == "timeseries":
                fig = px.line(
                    df,
                    x=x_column,
                    y=y_columns,
                    title=title,
                    color=color_column if color_column else None,
                )

            elif chart_type == "bar":
                fig = px.bar(
                    df,
                    x=x_column,
                    y=y_columns,
                    title=title,
                    color=color_column if color_column else None,
                )

            elif chart_type == "scatter":
                fig = px.scatter(
                    df,
                    x=x_column,
                    y=y_columns[0],
                    title=title,
                    color=color_column if color_column else None,
                )

            elif chart_type == "histogram":
                fig = px.histogram(df, x=y_columns[0], title=title, nbins=kwargs.get("bins", 30))

            elif chart_type == "box":
                fig = px.box(df, y=y_columns, title=title)

            elif chart_type == "area":
                fig = px.area(df, x=x_column, y=y_columns, title=title)

            elif chart_type == "pie":
                fig = px.pie(df, values=y_columns[0], names=x_column, title=title)

            elif chart_type == "violin":
                fig = px.violin(df, y=y_columns[0], title=title, box=True)

            else:
                # Default to line chart
                fig = px.line(df, x=x_column, y=y_columns, title=title)

            # Update layout
            fig.update_layout(
                xaxis_title=x_label,
                yaxis_title=y_label,
                hovermode="x unified",
                template="plotly_white",
            )

            # Convert to JSON or static image
            return {
                "success": True,
                "chart_data": fig.to_json(),
                "format": "plotly_json",
                "engine": "plotly",
            }

        except Exception as e:
            logger.error(f"Error generating plotly chart: {e}")
            raise e

    def generate_time_series_chart(
        self,
        data: list[dict[str, Any]] | pd.DataFrame,
        time_column: str,
        value_columns: list[str],
        title: str = "Time Series Analysis",
        **kwargs: Any,
    ) -> dict[str, Any]:
        """
        Convenience method for time series charts.

        Args:
            data: Data as list of dicts or DataFrame
            time_column: Column to use for time (x-axis)
            value_columns: One or more columns to plot on y-axis
            title: Chart title
            **kwargs: Additional chart parameters
        """
        return self.generate_chart(
            data=data,
            chart_type="timeseries",
            x_column=time_column,
            y_column=value_columns,
            title=title,
            x_label="Time",
            y_label="Value",
            **kwargs,
        )

    def generate_comparison_chart(
        self,
        data: list[dict[str, Any]] | pd.DataFrame,
        category_column: str,
        value_column: str,
        title: str = "Comparison Chart",
        chart_type: Literal["bar", "line"] = "bar",
        **kwargs: Any,
    ) -> dict[str, Any]:
        """
        Convenience method for comparison charts.

        Args:
            data: Data to compare
            category_column: Column for categories (x-axis)
            value_column: Column for values (y-axis)
            title: Chart title
            chart_type: Bar or line chart
            **kwargs: Additional chart parameters
        """
        return self.generate_chart(
            data=data,
            chart_type=chart_type,
            x_column=category_column,
            y_column=value_column,
            title=title,
            **kwargs,
        )


# Singleton instance
_visualization_service = None


def get_visualization_service() -> VisualizationService:
    """Get or create visualization service singleton."""
    global _visualization_service
    if _visualization_service is None:
        _visualization_service = VisualizationService()
    return _visualization_service
