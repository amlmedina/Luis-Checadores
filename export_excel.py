import sqlite3
import os
import pandas as pd

# Rutas
DB_PATH = "./Checador/default.db"
OUTPUT_EXCEL = "./registros_asistencia.xlsx"

def main():
    if not os.path.exists(DB_PATH):
        print(f"Error: No se encontró la base de datos en {DB_PATH}")
        return

    print("Leyendo registros desde SQLite...")
    conn = sqlite3.connect(DB_PATH)
    
    # Query to fetch all punches joined with employee details
    query = """
        SELECT e.emp_pin AS PIN, 
               e.emp_firstname || ' ' || COALESCE(e.emp_lastname, '') AS Nombre, 
               p.punch_time AS [Fecha y Hora]
        FROM att_punches p
        JOIN hr_employee e ON p.employee_id = e.id
        ORDER BY p.punch_time DESC;
    """
    
    df = pd.read_sql_query(query, conn)
    conn.close()
    
    print(f"Se cargaron {len(df)} registros.")
    
    # Export to Excel
    print(f"Exportando a {OUTPUT_EXCEL}...")
    df.to_excel(OUTPUT_EXCEL, index=False)
    print("¡Archivo de Excel creado con éxito!")

if __name__ == "__main__":
    main()
