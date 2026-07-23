import sqlite3
import os
import json
import gspread
from google.oauth2.service_account import Credentials

# Configuration
SPREADSHEET_ID = "1B_MvLNFyZUoLlQwyZopDK487_5zQEv2V4HXbf9zhj-w"
SHEET_NAME = "Sheet1"  # Or the actual tab name, e.g. "Hoja 1"
DB_PATH = "./Checador/default.db"
CREDS_FILE = "Servicio.json"

def main():
    # 1. Read data from SQLite
    if not os.path.exists(DB_PATH):
        print(f"Error: No se encontró la base de datos en {DB_PATH}")
        return

    print("Leyendo registros desde SQLite...")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT e.emp_pin AS PIN, 
               e.emp_firstname || ' ' || COALESCE(e.emp_lastname, '') AS Nombre, 
               p.punch_time AS Fecha_Hora
        FROM att_punches p
        JOIN hr_employee e ON p.employee_id = e.id
        ORDER BY p.punch_time DESC;
    """)
    rows = cursor.fetchall()
    conn.close()
    
    # Prepare data payload (header + rows)
    data_to_write = [["PIN", "Nombre", "Fecha y Hora"]] + [list(row) for row in rows]
    print(f"Se encontraron {len(rows)} registros para subir.")

    # 2. Authenticate with Google Sheets API
    # Check environment variable first (secure method for GitHub Actions)
    creds_json = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON")
    
    if creds_json:
        print("Autenticando usando la variable de entorno GOOGLE_SERVICE_ACCOUNT_JSON...")
        creds_info = json.loads(creds_json)
    elif os.path.exists(CREDS_FILE):
        print(f"Autenticando usando el archivo local {CREDS_FILE}...")
        with open(CREDS_FILE, "r") as f:
            creds_info = json.load(f)
    else:
        print("Error: No se encontró la variable de entorno GOOGLE_SERVICE_ACCOUNT_JSON ni el archivo Servicio.json.")
        return

    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]
    
    creds = Credentials.from_service_account_info(creds_info, scopes=scopes)
    client = gspread.authorize(creds)

    # 3. Write data to Google Sheets
    print(f"Conectando a la hoja de cálculo con ID: {SPREADSHEET_ID}...")
    try:
        sh = client.open_by_key(SPREADSHEET_ID)
        # Try to select by index 0 or name
        try:
            worksheet = sh.worksheet(SHEET_NAME)
        except gspread.exceptions.WorksheetNotFound:
            worksheet = sh.get_worksheet(0)
            
        print("Limpiando hoja y escribiendo nuevos registros...")
        worksheet.clear()
        worksheet.update(values=data_to_write, range_name="A1")
        print("¡Sincronización completada con éxito!")
        
    except Exception as e:
        print(f"Error al actualizar Google Sheets: {e}")

if __name__ == "__main__":
    main()
