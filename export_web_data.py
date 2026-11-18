import json
import os
import sqlite3
from datetime import datetime
import gspread
import pandas as pd
from google.oauth2.service_account import Credentials

DB_PATH = "./Checador/default.db"
STORE_MAP_FILE = "terminal_store_map.json"
OUTPUT_JSON = "./docs/data.json"
SPREADSHEET_ID = "1B_MvLNFyZUoLlQwyZopDK487_5zQEv2V4HXbf9zhj-w"
ADMS_SHEET_NAME = "Checadas_ADMS"
CREDS_FILE = "Servicio.json"


def get_pin_name_map():
    """Lee el catálogo PIN -> Nombre desde default.db si existe."""
    if not os.path.exists(DB_PATH):
        return {}
    try:
        conn = sqlite3.connect(DB_PATH)
        df = pd.read_sql_query(
            "SELECT emp_pin AS PIN, TRIM(emp_firstname || ' ' || COALESCE(emp_lastname, '')) AS Nombre FROM hr_employee",
            conn,
        )
        conn.close()
        return {str(r["PIN"]): r["Nombre"] for _, r in df.iterrows() if r["Nombre"]}
    except Exception:
        return {}


def load_from_google_sheets():
    """Lee las checadas de la pestaña Checadas_ADMS en Google Sheets."""
    creds_json = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON")
    if creds_json:
        creds_info = json.loads(creds_json)
    elif os.path.exists(CREDS_FILE):
        with open(CREDS_FILE, "r", encoding="utf-8") as f:
            creds_info = json.load(f)
    else:
        return pd.DataFrame()

    try:
        scopes = ["https://www.googleapis.com/auth/spreadsheets.readonly"]
        creds = Credentials.from_service_account_info(creds_info, scopes=scopes)
        client = gspread.authorize(creds)
        sh = client.open_by_key(SPREADSHEET_ID)
        ws = sh.worksheet(ADMS_SHEET_NAME)
        data = ws.get_all_records()
        if not data:
            return pd.DataFrame()
        df = pd.DataFrame(data)
        pin_map = get_pin_name_map()
        df["PIN"] = df["PIN"].astype(str)
        df["Nombre"] = df["PIN"].map(pin_map).fillna("PIN " + df["PIN"])
        df["Fecha_Hora"] = pd.to_datetime(df["Fecha_Hora"])
        df["Tienda"] = df["Tienda"].astype(str)
        return df[["PIN", "Nombre", "Fecha_Hora", "Tienda"]]
    except Exception as e:
        print(f"Aviso: No se pudo leer {ADMS_SHEET_NAME} de Google Sheets: {e}")
        return pd.DataFrame()


def format_duration(seconds):
    if seconds <= 0:
        return "0h 00m"
    mins = int(seconds // 60)
    hrs = mins // 60
    rem_mins = mins % 60
    return f"{hrs}h {rem_mins:02d}m"


def main():
    df = load_from_google_sheets()
    source_label = "Google Sheets (Checadas_ADMS)"

    if df.empty:
        print("No hay registros en Checadas_ADMS.")
        return

    df["Fecha"] = df["Fecha_Hora"].dt.strftime("%Y-%m-%d")

    records = []
    grouped = df.groupby(["PIN", "Nombre", "Fecha", "Tienda"], sort=False)

    for (pin, nombre, fecha, tienda), group in grouped:
        punches = group["Fecha_Hora"].sort_values().tolist()
        entrada = punches[0]
        salida_comer = None
        regreso_comer = None
        salida = None
        horas_trabajadas = ""

        if len(punches) == 2:
            salida = punches[1]
            horas_trabajadas = format_duration((salida - entrada).total_seconds())
        elif len(punches) == 3:
            salida_comer = punches[1]
            salida = punches[2]
            horas_trabajadas = format_duration((salida - entrada).total_seconds())
        elif len(punches) >= 4:
            salida_comer = punches[1]
            regreso_comer = punches[2]
            salida = punches[-1]
            total_sec = (salida - entrada).total_seconds() - (regreso_comer - salida_comer).total_seconds()
            horas_trabajadas = format_duration(total_sec)

        records.append({
            "pin": str(pin),
            "nombre": nombre,
            "fecha": fecha,
            "hora": entrada.strftime("%H:%M:%S"),
            "salida_comer": salida_comer.strftime("%H:%M:%S") if salida_comer else "",
            "regreso_comer": regreso_comer.strftime("%H:%M:%S") if regreso_comer else "",
            "salida": salida.strftime("%H:%M:%S") if salida else "",
            "horas_trabajadas": horas_trabajadas,
            "tienda": tienda,
        })

    payload = {
        "metadata": {
            "db_mtime": f"{source_label} - {datetime.now().strftime('%d/%m/%Y %H:%M')}",
            "latest_punch": df["Fecha_Hora"].max().strftime("%d/%m/%Y %H:%M"),
            "generated_at": datetime.now().strftime("%d/%m/%Y %H:%M"),
            "total_records": len(records),
        },
        "records": records,
    }

    os.makedirs(os.path.dirname(OUTPUT_JSON), exist_ok=True)
    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False)

    print(f"Exportados {len(records)} registros desde {source_label} a {OUTPUT_JSON}")


if __name__ == "__main__":
    main()
