import json
import os
import sqlite3
from datetime import datetime
import pandas as pd

DB_PATH = "./Checador/default.db"
STORE_MAP_FILE = "terminal_store_map.json"
OUTPUT_JSON = "./docs/data.json"


def get_store_map():
    if os.path.exists(STORE_MAP_FILE):
        try:
            with open(STORE_MAP_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def format_duration(seconds):
    if seconds <= 0:
        return "0h 00m"
    mins = int(seconds // 60)
    hrs = mins // 60
    rem_mins = mins % 60
    return f"{hrs}h {rem_mins:02d}m"


def main():
    if not os.path.exists(DB_PATH):
        print(f"Error: No se encontró la base de datos en {DB_PATH}")
        return

    conn = sqlite3.connect(DB_PATH)
    query = """
        SELECT e.emp_pin AS PIN,
               TRIM(e.emp_firstname || ' ' || COALESCE(e.emp_lastname, '')) AS Nombre,
               p.punch_time AS Fecha_Hora,
               p.terminal_id AS ID_Checador,
               COALESCE(t.terminal_name, 'Checador ' || p.terminal_id) AS Nombre_Checador
        FROM att_punches p
        JOIN hr_employee e ON p.employee_id = e.id
        LEFT JOIN att_terminal t ON p.terminal_id = t.id
        ORDER BY p.punch_time ASC;
    """
    df = pd.read_sql_query(query, conn)
    conn.close()

    if df.empty:
        print("No hay registros en la base de datos.")
        return

    df["Fecha_Hora"] = pd.to_datetime(df["Fecha_Hora"])
    df["Fecha"] = df["Fecha_Hora"].dt.strftime("%Y-%m-%d")

    store_map = get_store_map()
    df["Tienda"] = df["ID_Checador"].astype(str).map(store_map).fillna(df["Nombre_Checador"])

    records = []
    grouped = df.groupby(["PIN", "Nombre", "Fecha", "ID_Checador", "Tienda"], sort=False)

    for (pin, nombre, fecha, _id_chec, tienda), group in grouped:
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
            "db_mtime": datetime.fromtimestamp(os.path.getmtime(DB_PATH)).strftime("%d/%m/%Y %H:%M"),
            "latest_punch": df["Fecha_Hora"].max().strftime("%d/%m/%Y %H:%M"),
            "generated_at": datetime.now().strftime("%d/%m/%Y %H:%M"),
            "total_records": len(records),
        },
        "records": records,
    }

    os.makedirs(os.path.dirname(OUTPUT_JSON), exist_ok=True)
    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False)

    print(f"Exportados {len(records)} registros a {OUTPUT_JSON}")


if __name__ == "__main__":
    main()
