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
        ORDER BY p.punch_time DESC;
    """
    df = pd.read_sql_query(query, conn)
    conn.close()

    if df.empty:
        print("No hay registros en la base de datos.")
        return

    df["Fecha_Hora"] = pd.to_datetime(df["Fecha_Hora"])
    df["Fecha"] = df["Fecha_Hora"].dt.strftime("%Y-%m-%d")
    df["Hora"] = df["Fecha_Hora"].dt.strftime("%H:%M:%S")

    store_map = get_store_map()
    df["Tienda"] = df["ID_Checador"].astype(str).map(store_map).fillna(df["Nombre_Checador"])

    # Primer registro (llegada) por empleado, fecha y checador
    df_arrivals = (
        df.sort_values("Fecha_Hora")
        .groupby(["PIN", "Nombre", "Fecha", "ID_Checador", "Tienda"], as_index=False)
        .first()
    )

    records = [
        {
            "pin": str(row["PIN"]),
            "nombre": row["Nombre"],
            "fecha": row["Fecha"],
            "hora": row["Hora"],
            "tienda": row["Tienda"],
        }
        for _, row in df_arrivals.iterrows()
    ]

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
