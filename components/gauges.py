import plotly.graph_objects as go


def draw_gauge(value, title, max_val, color, unit, font_color, track_color):
    fig = go.Figure(
        go.Indicator(
            mode="gauge+number",
            value=value,
            domain={"x": [0.06, 0.94], "y": [0, 0.68]},
            number={
                "font": {"size": 34, "color": font_color},
                "suffix": f" {unit}",
            },
            gauge={
                "axis": {
                    "range": [0, max_val],
                    "tickwidth": 1,
                    "tickcolor": font_color,
                    "tickfont": {"size": 19, "color": font_color},
                },
                "bar": {"color": color},
                "bgcolor": track_color,
                "borderwidth": 0,
            },
        )
    )

    fig.add_annotation(
        text=f"<b>{title}</b>",
        x=0.5,
        y=0.96,
        xref="paper",
        yref="paper",
        showarrow=False,
        font=dict(size=34, color=font_color),
        xanchor="center",
        yanchor="bottom",
    )

    fig.update_layout(
        height=300,
        margin=dict(l=24, r=24, t=52, b=12),
        autosize=True,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
    )
    return fig


def draw_temperature_gauge(value, font_color="#FFFFFF", track_color="#21262D"):
    fig = draw_gauge(
        value, "Temperatura", 100, "#16A34A", "°C", font_color, track_color
    )
    fig.update_traces(
        gauge={
            "steps": [
                {"range": [0, 95], "color": "#166534"},
                {"range": [85, 95], "color": "#A16207"},
                {"range": [95, 100], "color": "#991B1B"},
            ],
            "bar": {"color": "#F8FAFC"},
        }
    )
    return fig


def draw_pressure_gauge(value, font_color="#FFFFFF", track_color="#21262D"):
    fig = draw_gauge(
        value, "Presión Línea", 15, "#00E676", "Bar", font_color, track_color
    )
    fig.update_traces(
        gauge={
            "axis": {
                "range": [0, 15],
                "tickvals": [0, 6.5, 8, 15],
                "ticktext": ["0", "6.5", "8", "15"],
                "tickwidth": 1,
                "tickcolor": font_color,
                "tickfont": {"size": 19, "color": font_color},
            },
            "steps": [
                {"range": [0, 6.5], "color": "#3F3F46"},
                {"range": [6.5, 8], "color": "#166534"},
                {"range": [8, 15], "color": "#991B1B"},
            ],
            "bar": {"color": "#F8FAFC"},
        }
    )
    return fig
