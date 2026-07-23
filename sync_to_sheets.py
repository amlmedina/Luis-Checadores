import sqlite3
import os
import json
import io
import gspread
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload

# Configuration
SPREADSHEET_ID = "1B_MvLNFyZUoLlQwyZopDK487_5zQEv2V4HXbf9zhj-w"
RAW_SHEET_NAME = "Sheet1"
REPORT_SHEET_NAME = "Reporte de Llegadas"
DRIVE_FOLDER_ID = "1Up1Ch18VKQTUeG_LamKo0EbrchlSxiBV"
LOCAL_DB_PATH = "./Checador/default.db"
CREDS_FILE = "Servicio.json"

def download_database_from_drive(creds_info):
    scopes = ["https://www.googleapis.com/auth/drive.readonly"]
    creds = Credentials.from_service_account_info(creds_info, scopes=scopes)
    drive_service = build("drive", "v3", credentials=creds)

    print(f"Buscando archivos de base de datos en la carpeta de Drive: {DRIVE_FOLDER_ID}...")
    try:
        results = drive_service.files().list(
            q=f"'{DRIVE_FOLDER_ID}' in parents and name contains '.db' and trashed = false",
            fields="files(id, name)",
            pageSize=1
        ).execute()
        files = results.get("files", [])

        if not files:
            print("No se encontró ningún archivo .db en la carpeta de Google Drive.")
            return False

        db_file = files[0]
        file_id = db_file["id"]
        file_name = db_file["name"]
        print(f"Archivo encontrado: {file_name} (ID: {file_id}). Descargando...")

        request = drive_service.files().get_media(fileId=file_id)
        fh = io.BytesIO()
        downloader = MediaIoBaseDownload(fh, request)
        done = False
        while not done:
            status, done = downloader.next_chunk()
            print(f"Descargando: {int(status.progress() * 100)}%")

        with open(LOCAL_DB_PATH, "wb") as f:
            f.write(fh.getvalue())
        
        print("Base de datos descargada con éxito.")
        return True

    except Exception as e:
        print(f"Error al descargar desde Google Drive: {e}")
        return False

def main():
    # 1. Load credentials
    creds_json = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON")
    if creds_json:
        creds_info = json.loads(creds_json)
    elif os.path.exists(CREDS_FILE):
        with open(CREDS_FILE, "r") as f:
            creds_info = json.load(f)
    else:
        print("Error: No se encontró la variable de entorno GOOGLE_SERVICE_ACCOUNT_JSON ni el archivo Servicio.json.")
        return

    # 2. Download SQLite database
    if not download_database_from_drive(creds_info):
        print("Sincronización cancelada debido a un error de descarga.")
        return

    # 3. Read data from SQLite
    print("Leyendo marcas desde la base de datos descargada...")
    conn = sqlite3.connect(LOCAL_DB_PATH)
    cursor = conn.cursor()
    
    try:
        # Fetch raw punch events with terminal information
        cursor.execute("""
            SELECT e.emp_pin AS PIN, 
                   e.emp_firstname || ' ' || COALESCE(e.emp_lastname, '') AS Nombre, 
                   p.punch_time AS Fecha_Hora,
                   p.terminal_id AS ID_Checador,
                   COALESCE(t.terminal_name, 'Checador ' || p.terminal_id) AS Nombre_Checador
            FROM att_punches p
            JOIN hr_employee e ON p.employee_id = e.id
            LEFT JOIN att_terminal t ON p.terminal_id = t.id
            ORDER BY p.punch_time DESC;
        """)
        rows = cursor.fetchall()
    except Exception as e:
        print(f"Error al leer las tablas de la base de datos: {e}")
        conn.close()
        return

    conn.close()
    
    # Header + data for Sheet1 (5 columns)
    raw_data_to_write = [["PIN", "Nombre", "Fecha y Hora", "ID Checador", "Nombre Checador"]] + [list(row) for row in rows]
    print(f"Se extrajeron {len(rows)} registros.")

    # 4. Authenticate with Google Sheets
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]
    creds = Credentials.from_service_account_info(creds_info, scopes=scopes)
    client = gspread.authorize(creds)

    # 5. Write to Google Sheets
    print(f"Actualizando la hoja de cálculo con ID: {SPREADSHEET_ID}...")
    try:
        sh = client.open_by_key(SPREADSHEET_ID)
        
        # 5.1 Update Raw Sheet (Sheet1)
        try:
            raw_worksheet = sh.worksheet(RAW_SHEET_NAME)
        except gspread.exceptions.WorksheetNotFound:
            raw_worksheet = sh.get_worksheet(0)
            
        print(f"Escribiendo datos crudos en la pestaña '{RAW_SHEET_NAME}'...")
        raw_worksheet.clear()
        raw_worksheet.update(values=raw_data_to_write, range_name="A1", value_input_option="USER_ENTERED")

        # 5.2 Set up the automated Report Sheet
        try:
            report_worksheet = sh.worksheet(REPORT_SHEET_NAME)
        except gspread.exceptions.WorksheetNotFound:
            print(f"Creando la pestaña '{REPORT_SHEET_NAME}'...")
            report_worksheet = sh.add_worksheet(title=REPORT_SHEET_NAME, rows="100", cols="20")
            
        query_formula = (
            '=QUERY(' + RAW_SHEET_NAME + '!A:E, '
            '"SELECT B, toDate(C), min(C), E WHERE A IS NOT NULL GROUP BY B, toDate(C), E ORDER BY toDate(C) DESC, B ASC '
            'LABEL B \'Nombre\', toDate(C) \'Fecha\', min(C) \'Hora de Llegada\', E \'Checador\' '
            'FORMAT min(C) \'hh:mm:ss AM/PM\'", 1)'
        )
        
        print(f"Insertando fórmula dinámica en '{REPORT_SHEET_NAME}'...")
        report_worksheet.clear()
        report_worksheet.update(values=[[query_formula]], range_name="A1", value_input_option="USER_ENTERED")
        
        # Format the columns for a clean look
        # Set Header styling (Slate Gray background, bold white text)
        header_format = {
            "backgroundColor": {"red": 50/255, "green": 60/255, "blue": 70/255},
            "textFormat": {"foregroundColor": {"red": 1.0, "green": 1.0, "blue": 1.0}, "bold": True, "fontSize": 11},
            "horizontalAlignment": "CENTER"
        }
        
        # Format headers in A1:D1 (4 columns)
        report_worksheet.format("A1:D1", header_format)
        
        print("¡Sincronización y automatización de fórmulas completadas con éxito!")
        
        # Database remains local for Streamlit usage
            
    except Exception as e:
        print(f"Error al actualizar Google Sheets: {e}")

if __name__ == "__main__":
    main()
