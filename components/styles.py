import streamlit as st


def inject_scada_styles():
    """Inyecta el tema oscuro fijo y los estilos CSS personalizados para SCADA."""
    bg_color = "#0E1117"
    card_bg = "#161B22"
    card_border = "#30363D"
    text_color = "#FFFFFF"
    text_muted = "#94A3B8"
    metric_color = "#58A6FF"

    st.markdown(
        f"""
        <style>
        .stApp {{
            background-color: {bg_color} !important;
        }}
        [data-testid="stSidebar"] {{
            background-color: {card_bg} !important;
            border-right: 1px solid {card_border} !important;
        }}
        .stApp h1, .stApp h2, .stApp h3, .stApp h4, .stApp p, .stApp span, .stApp label {{
            color: {text_color} !important;
        }}
        [data-testid="stVerticalBlock"] > div[data-testid="stBlock"] {{
            background-color: {card_bg} !important;
            border: 1px solid {card_border} !important;
            border-radius: 12px;
            padding: 16px;
            box-sizing: border-box;
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
        }}
        [data-testid="stColumn"] {{
            min-width: 0 !important;
            box-sizing: border-box;
        }}
        [data-testid="stMetricValue"] {{
            font-size: 2rem !important;
            font-weight: 700;
            color: {metric_color} !important;
        }}
        [data-testid="stMetricLabel"] {{
            color: {text_muted} !important;
            font-weight: 600;
            font-size: 1.05rem !important;
        }}
        [data-baseweb="tab"] {{
            font-size: 1.15rem !important;
            font-weight: 700 !important;
        }}
        .substate-label {{
            color: {text_muted};
            font-size: 0.75rem;
            font-weight: 600;
            margin-top: 10px;
        }}
        .substate-value {{
            color: {metric_color};
            font-size: 1rem;
            font-weight: 700;
            line-height: 1.2;
            overflow-wrap: anywhere;
        }}
        .industrial-alert-pulse {{
            color: #FFFFFF !important;
            background-color: rgba(248, 113, 113, 0.18) !important;
            border: 1px solid #F87171 !important;
            padding: 12px 14px;
            border-radius: 10px;
            margin-bottom: 10px;
            font-weight: 600;
        }}
        .industrial-alert-pulse strong {{
            color: #FFFFFF !important;
        }}
        .industrial-alert-compact {{
            color: #FFFFFF !important;
            background-color: rgba(248, 113, 113, 0.12) !important;
            border-left: 3px solid #F87171 !important;
            padding: 5px 10px;
            margin: 3px 0;
            font-size: 13px;
        }}
        .maintenance-badge {{
            display: inline-block;
            color: #FFFFFF !important;
            background-color: #991B1B !important;
            border: 1px solid #F87171 !important;
            border-radius: 14px;
            padding: 4px 10px;
            font-size: 12px;
            font-weight: 700;
            animation: blink 1.2s step-start infinite;
            cursor: help;
        }}
        .industrial-alert-failure {{
            color: #FFFFFF !important;
            background-color: #991B1B !important;
            border: 2px solid #F87171 !important;
            padding: 14px 16px;
            border-radius: 8px;
            margin: 5px 0 10px;
            font-size: 18px;
            font-weight: 700;
        }}
        .status-badge {{
            display: inline-block;
            padding: 8px 18px;
            border-radius: 20px;
            font-weight: 700;
            font-size: 16px;
            color: #FFFFFF !important;
            text-align: center;
        }}
        .status-on {{
            background-color: #16A34A;
            border: 1px solid #4ADE80;
        }}
        .status-off, .status-offline {{
            background-color: #DC2626;
            border: 1px solid #F87171;
            animation: blink 1.2s step-start infinite;
        }}
        .equipment-offline {{ opacity: 0.35; }}
        .js-plotly-plot .plotly .main-svg {{
            overflow: visible !important;
        }}
        div[data-testid="stPlotlyChart"] {{
            width: 100% !important;
            min-width: 0 !important;
        }}
        @keyframes blink {{
            50% {{ opacity: 0.35; }}
        }}
        .service-mini-card {{
            background-color: rgba(15, 23, 42, 0.85);
            border: 1px solid #30363D;
            border-radius: 8px;
            padding: 8px 10px;
            margin-top: 8px;
            margin-bottom: 2px;
            width: min(100%, 300px);
        }}
        .service-mini-label {{
            color: #94A3B8;
            font-size: 0.68rem;
            font-weight: 700;
            letter-spacing: 0.08em;
            text-transform: uppercase;
            margin-bottom: 6px;
        }}
        .service-mini-bar {{
            height: 8px;
            width: 100%;
            background-color: #21262D;
            border-radius: 999px;
            overflow: hidden;
        }}
        .service-mini-bar-fill {{
            height: 100%;
            border-radius: 999px;
            transition: width 0.35s ease;
        }}
        .service-mini-values {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-top: 5px;
            gap: 8px;
            color: #E2E8F0;
            font-size: 0.72rem;
            font-weight: 700;
        }}
        .admin-config-box {{
            background: rgba(15, 23, 42, 0.9);
            border: 1px solid #1F6FEB;
            border-radius: 12px;
            padding: 12px 12px 8px;
            margin: 6px 0 12px;
            box-shadow: inset 0 0 0 1px rgba(31, 111, 235, 0.18);
        }}
        .admin-config-header {{
            color: #8AB4FF;
            font-size: 0.68rem;
            font-weight: 800;
            letter-spacing: 0.12em;
            text-transform: uppercase;
            margin-bottom: 8px;
        }}
        [data-testid="stSidebar"] div[data-testid="stTextInput"] > div {{
            background: rgba(15, 23, 42, 0.8);
            border-radius: 10px;
            border: 1px solid #1F6FEB;
        }}
        [data-testid="stSidebar"] div[data-testid="stTextInput"] input {{
            background: transparent;
            color: #F8FAFC;
            font-weight: 600;
        }}
        [data-testid="stSidebar"] div[data-testid="stNumberInput"] > div {{
            background: rgba(15, 23, 42, 0.8);
            border-radius: 10px;
            border: 1px solid #334155;
        }}
        [data-testid="stSidebar"] div[data-testid="stNumberInput"] input {{
            background: transparent;
            color: #F8FAFC;
            font-weight: 600;
        }}
        [data-testid="stSidebar"] div[data-testid="stButton"] > button {{
            border-radius: 10px;
            font-weight: 700;
        }}
        @media (max-width: 767px) {{
            [data-testid="stMainBlockContainer"] {{
                padding: 1rem 0.75rem 2rem;
            }}
            [data-testid="stHorizontalBlock"] {{
                flex-wrap: wrap !important;
                gap: 0.75rem;
            }}
            [data-testid="stHorizontalBlock"] > [data-testid="stColumn"] {{
                flex: 1 1 100% !important;
                width: 100% !important;
                min-width: 0 !important;
            }}
            [data-baseweb="tab-list"] {{
                overflow-x: auto;
                flex-wrap: nowrap;
            }}
            [data-baseweb="tab"] {{
                flex: 0 0 auto;
                font-size: 0.95rem !important;
                white-space: nowrap;
            }}
            .stApp h1 {{
                font-size: 1.6rem !important;
                line-height: 1.15 !important;
            }}
            [data-testid="stMetricValue"] {{
                font-size: 1.6rem !important;
            }}
            [data-testid="stVerticalBlock"] > div[data-testid="stBlock"] {{
                padding: 10px;
            }}
            [data-testid="stPlotlyChart"],
            [data-testid="stDataFrame"] {{
                max-width: 100%;
                overflow-x: auto;
            }}
            [data-testid="stDownloadButton"] button,
            [data-testid="stButton"] button {{
                min-height: 44px;
            }}
        }}
        @media (min-width: 768px) and (max-width: 1024px) {{
            [data-testid="stMainBlockContainer"] {{
                padding-left: 1.5rem;
                padding-right: 1.5rem;
            }}
            [data-testid="stHorizontalBlock"] {{
                flex-wrap: wrap !important;
                gap: 1rem;
            }}
            [data-testid="stHorizontalBlock"] > [data-testid="stColumn"] {{
                flex: 1 1 calc(50% - 1rem) !important;
                width: calc(50% - 1rem) !important;
                min-width: 0 !important;
            }}
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )
