import streamlit as st
import pandas as pd
import sqlite3
import os
import json
import plotly.express as px
from datetime import datetime, time

# Page configuration
st.set_page_config(
    page_title="Control de Asistencias - Recursos Humanos",
    page_icon="📋",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom Styling (Minimal Slate/Zinc theme with professional typography)
st.markdown("""
    <style>
    .main .block-container {
        padding-top: 2rem;
        padding-bottom: 2rem;
    }
    .metric-card {
        background-color: #F8FAFC;
        border: 1px solid #E2E8F0;
        border-radius: 12px;
        padding: 1.5rem;
        text-align: center;
        box-shadow: 0 1px 3px 0 rgba(0, 0, 0, 0.1);
    }
    .metric-value {
        font-size: 2rem;
        font-weight: 700;
        color: #1E293B;
    }
    .metric-label {
        font-size: 0.875rem;
        color: #64748B;
        margin-top: 0.25rem;
    }
    </style>
""", unsafe_allow_html=True)

DB_PATH = "./Checador/default.db"
PIN_CONFIG_FILE = "pin_config.json"

def get_saved_pin():
    """Reads the saved PIN from pin_config.json, defaults to '3465'."""
    if os.path.exists(PIN_CONFIG_FILE):
        try:
            with open(PIN_CONFIG_FILE, "r") as f:
                config = json.load(f)
                return str(config.get("pin", "3465"))
        except Exception:
            return "3465"
    return "3465"

def save_new_pin(new_pin):
    """Saves the new PIN to pin_config.json."""
    try:
        with open(PIN_CONFIG_FILE, "w") as f:
            json.dump({"pin": str(new_pin)}, f)
        return True
    except Exception:
        return False

@st.cache_data
def load_data_from_sqlite():
    """Loads raw records directly from the local SQLite database."""
    if not os.path.exists(DB_PATH):
        return pd.DataFrame()
    
    conn = sqlite3.connect(DB_PATH)
    query = """
        SELECT e.emp_pin AS PIN, 
               e.emp_firstname || ' ' || COALESCE(e.emp_lastname, '') AS Nombre, 
               p.punch_time AS Fecha_Hora
        FROM att_punches p
        JOIN hr_employee e ON p.employee_id = e.id
        ORDER BY p.punch_time DESC;
    """
    df = pd.read_sql_query(query, conn)
    conn.close()
    
    # Process date and time columns
    df['Fecha_Hora'] = pd.to_datetime(df['Fecha_Hora'])
    df['Fecha'] = df['Fecha_Hora'].dt.date
    df['Hora'] = df['Fecha_Hora'].dt.time
    df['Minutos_del_dia'] = df['Fecha_Hora'].dt.hour * 60 + df['Fecha_Hora'].dt.minute
    
    # Filter to get only the FIRST punch per employee per day (Arrival Time)
    df_arrivals = df.sort_values('Fecha_Hora').groupby(['PIN', 'Nombre', 'Fecha']).first().reset_index()
    return df_arrivals

# Initialize authentication state
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

# ----------------- LOGIN SCREEN -----------------
if not st.session_state.authenticated:
    st.title("🔑 Acceso al Sistema de RH")
    st.markdown("Por favor, ingresa el PIN de seguridad para acceder al panel de asistencia.")
    
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.write("")
        st.markdown("<div style='background-color:#F8FAFC; border:1px solid #E2E8F0; border-radius:12px; padding:2rem; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);'>", unsafe_allow_html=True)
        pin_input = st.text_input("PIN de Acceso", type="password", key="login_pin")
        
        if st.button("Entrar", use_container_width=True):
            correct_pin = get_saved_pin()
            if pin_input == correct_pin:
                st.session_state.authenticated = True
                st.rerun()
            else:
                st.error("PIN incorrecto. Inténtalo de nuevo.")
        st.markdown("</div>", unsafe_allow_html=True)
    st.stop()  # Stop rendering the rest of the app if not logged in

# ----------------- MAIN APP CONTENT (Authenticated) -----------------

# Load data
df = load_data_from_sqlite()

if df.empty:
    st.error("No se pudo cargar la base de datos local. Verifica que la carpeta 'Checador' y el archivo 'default.db' existan en este directorio.")
else:
    # Sidebar Filters
    st.sidebar.image("https://img.icons8.com/color/96/worker-male.png", width=80)
    st.sidebar.title("Filtros de Control")
    
    # 1. Date filter
    min_date = df['Fecha'].min()
    max_date = df['Fecha'].max()
    date_range = st.sidebar.date_input(
        "Rango de Fechas",
        value=(min_date, max_date),
        min_value=min_date,
        max_value=max_date
    )
    
    # 2. Tolerance Limit Slider (Grace Period)
    st.sidebar.subheader("Parámetros de Tolerancia")
    limit_hour = st.sidebar.slider(
        "Hora límite de entrada (Puntual)",
        min_value=time(8, 0),
        max_value=time(13, 0),
        value=time(11, 15),
        step=pd.Timedelta(minutes=5).to_pytimedelta()
    )
    
    # 3. Employee selector
    employees = ["Todos"] + sorted(df['Nombre'].unique().tolist())
    selected_employee = st.sidebar.selectbox("Seleccionar Empleado", employees)
    
    # 4. PIN Management Section in Sidebar
    st.sidebar.write("---")
    st.sidebar.subheader("Seguridad")
    with st.sidebar.expander("Cambiar PIN de Acceso"):
        old_pin = st.text_input("PIN Actual", type="password", key="old_pin")
        new_pin = st.text_input("PIN Nuevo", type="password", key="new_pin")
        confirm_pin = st.text_input("Confirmar PIN", type="password", key="confirm_pin")
        
        if st.button("Actualizar PIN", use_container_width=True):
            saved_pin = get_saved_pin()
            if old_pin != saved_pin:
                st.error("El PIN actual es incorrecto.")
            elif new_pin != confirm_pin:
                st.error("El PIN nuevo y la confirmación no coinciden.")
            elif len(new_pin) < 4:
                st.error("El PIN debe tener al menos 4 caracteres.")
            else:
                if save_new_pin(new_pin):
                    st.success("¡PIN actualizado con éxito!")
                else:
                    st.error("Error al guardar el nuevo PIN.")
                    
    # Log out button
    if st.sidebar.button("Cerrar Sesión", use_container_width=True):
        st.session_state.authenticated = False
        st.rerun()
    
    # Filter Data based on selection
    filtered_df = df.copy()
    
    # Apply date filter
    if isinstance(date_range, tuple) and len(date_range) == 2:
        start_date, end_date = date_range
        filtered_df = filtered_df[(filtered_df['Fecha'] >= start_date) & (filtered_df['Fecha'] <= end_date)]
        
    # Apply employee filter
    if selected_employee != "Todos":
        filtered_df = filtered_df[filtered_df['Nombre'] == selected_employee]
        
    # Determine punctuality state
    limit_in_minutes = limit_hour.hour * 60 + limit_hour.minute
    filtered_df['Estado'] = filtered_df['Minutos_del_dia'].apply(
        lambda x: 'Puntual' if x <= limit_in_minutes else 'Retardo'
    )
    
    # Main Dashboard Header
    st.title("📋 Control de Asistencia y Puntualidad")
    st.markdown("### Vista de Recursos Humanos")
    st.write(f"Reporte desde **{min_date.strftime('%d/%m/%Y')}** hasta **{max_date.strftime('%d/%m/%Y')}**.")
    st.write("---")
    
    # KPI metrics calculation
    total_records = len(filtered_df)
    active_employees = filtered_df['Nombre'].nunique()
    lates = len(filtered_df[filtered_df['Estado'] == 'Retardo'])
    ontimes = len(filtered_df[filtered_df['Estado'] == 'Puntual'])
    
    punctuality_rate = (ontimes / total_records * 100) if total_records > 0 else 0
    
    # Render KPI Cards in columns
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.markdown(f"""
            <div class="metric-card">
                <div class="metric-value">{active_employees}</div>
                <div class="metric-label">👥 Empleados Activos</div>
            </div>
        """, unsafe_allow_html=True)
        
    with col2:
        st.markdown(f"""
            <div class="metric-card">
                <div class="metric-value">{total_records}</div>
                <div class="metric-label">📅 Días Totales Registrados</div>
            </div>
        """, unsafe_allow_html=True)
        
    with col3:
        color = "#16A34A" if punctuality_rate >= 80 else "#D97706" if punctuality_rate >= 60 else "#DC2626"
        st.markdown(f"""
            <div class="metric-card">
                <div class="metric-value" style="color: {color}">{punctuality_rate:.1f}%</div>
                <div class="metric-label">✅ Tasa de Puntualidad (antes de {limit_hour.strftime('%H:%M %p')})</div>
            </div>
        """, unsafe_allow_html=True)
        
    with col4:
        st.markdown(f"""
            <div class="metric-card">
                <div class="metric-value" style="color: #DC2626">{lates}</div>
                <div class="metric-label">⚠️ Total de Retardos</div>
            </div>
        """, unsafe_allow_html=True)
        
    st.write(" ")
    st.write(" ")
    
    # Charts Section
    chart_col1, chart_col2 = st.columns(2)
    
    with chart_col1:
        st.markdown("#### Historial Diario de Puntualidad")
        # Aggregating daily data
        daily_stats = filtered_df.groupby(['Fecha', 'Estado']).size().reset_index(name='Cantidad')
        
        fig = px.bar(
            daily_stats, 
            x='Fecha', 
            y='Cantidad', 
            color='Estado',
            color_discrete_map={'Puntual': '#16A34A', 'Retardo': '#DC2626'},
            barmode='stack',
            height=350
        )
        fig.update_layout(
            margin=dict(l=20, r=20, t=10, b=20),
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)',
            legend_title_text=''
        )
        st.plotly_chart(fig, use_container_width=True)
        
    with chart_col2:
        st.markdown("#### Distribución de Horas de Llegada")
        
        # Convert times to decimal hours for plotting
        filtered_df['Hora_Decimal'] = filtered_df['Minutos_del_dia'] / 60
        
        fig2 = px.histogram(
            filtered_df,
            x='Hora_Decimal',
            nbins=24,
            color='Estado',
            color_discrete_map={'Puntual': '#16A34A', 'Retardo': '#DC2626'},
            labels={'Hora_Decimal': 'Hora del Día (Formato Decimal)'},
            height=350
        )
        
        # Add vertical line for the limit
        limit_decimal = limit_in_minutes / 60
        fig2.add_vline(x=limit_decimal, line_width=2, line_dash="dash", line_color="#E2E8F0", 
                      annotation_text=f"Límite {limit_hour.strftime('%H:%M')}", 
                      annotation_position="top left")
        
        fig2.update_layout(
            margin=dict(l=20, r=20, t=10, b=20),
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)',
            legend_title_text='',
            yaxis_title_text='Frecuencia'
        )
        st.plotly_chart(fig2, use_container_width=True)
        
    st.write(" ")
    
    # Detailed Data Table Section
    st.markdown("#### Tabla de Registros Detallada")
    
    # Clean dataframe for display
    display_df = filtered_df[['PIN', 'Nombre', 'Fecha', 'Hora', 'Estado']].copy()
    display_df['Fecha'] = display_df['Fecha'].apply(lambda x: x.strftime('%d/%m/%Y'))
    display_df['Hora'] = display_df['Hora'].apply(lambda x: x.strftime('%H:%M:%S'))
    
    # Styling table based on status
    st.dataframe(
        display_df,
        use_container_width=True,
        hide_index=True
    )
    
    # Export options
    csv = display_df.to_csv(index=False, encoding='utf-8-sig').encode('utf-8-sig')
    st.download_button(
        label="📥 Descargar Reporte en Excel (CSV)",
        data=csv,
        file_name=f"reporte_asistencia_{datetime.now().strftime('%Y%m%d')}.csv",
        mime="text/csv"
    )
