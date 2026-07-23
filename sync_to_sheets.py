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
SHEET_NAME = "Sheet1"
DRIVE_FOLDER_ID = "1iRf_enMw1ELIfnszm25vDre-2NkPHhcB"
LOCAL_DB_PATH = "temp_downloaded_default.db"
CREDS_FILE = "Servicio.json"

def download_database_from_drive(creds_info):
    scopes = ["https://www.googleapis.com/auth/drive.readonly"]
    creds = Credentials.from_service_account_info(creds_info, scopes=scopes)
    drive_service = build("drive", "v3", credentials=creds)

    print(f"Buscando archivos de base de datos en la carpeta de Drive: {DRIVE_FOLDER_ID}...")
    try:
        # Search for .db files in the specified folder
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

        # Download the file
        request = drive_service.files().get_media(fileId=file_id)
        fh = io.BytesIO()
        downloader = MediaIoBaseDownload(fh, request)
        done = False
        while not done:
            status, done = downloader.next_chunk()
            print(f"Descargando: {int(status.progress() * 100)}%")

        # Save bytes to a local SQLite file
        with open(LOCAL_DB_PATH, "wb") as f:
            f.write(fh.getvalue())
        
        print("Base de datos descargada con éxito.")
        return True

    except Exception as e:
        print(f"Error al descargar desde Google Drive: {e}")
        print("\n[IMPORTANTE] Verifica si has activado la API de Google Drive en Google Cloud Console y compartido la carpeta con tu Cuenta de Servicio.")
        return False

def main():
    # 1. Load credentials info
    creds_json = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON")
    if creds_json:
        creds_info = json.loads(creds_json)
    elif os.path.exists(CREDS_FILE):
        with open(CREDS_FILE, "r") as f:
            creds_info = json.load(f)
    else:
        print("Error: No se encontró la variable de entorno GOOGLE_SERVICE_ACCOUNT_JSON ni el archivo Servicio.json.")
        return

    # 2. Download SQLite database from Google Drive
    if not download_database_from_drive(creds_info):
        print("Sincronización cancelada debido a un error de descarga.")
        return

    # 3. Read data from downloaded SQLite
    print("Leyendo registros de asistencia desde la base de datos descargada...")
    conn = sqlite3.connect(LOCAL_DB_PATH)
    cursor = conn.cursor()
    
    # We query the tables (supporting default.db layout)
    try:
        cursor.execute("""
            SELECT e.emp_pin AS PIN, 
                   e.emp_firstname || ' ' || COALESCE(e.emp_lastname, '') AS Nombre, 
                   p.punch_time AS Fecha_Hora
            FROM att_punches p
            JOIN hr_employee e ON p.employee_id = e.id
            ORDER BY p.punch_time DESC;
        """)
        rows = cursor.fetchall()
    except Exception as e:
        print(f"Error al leer las tablas de asistencia en la base de datos descargada: {e}")
        conn.close()
        return

    conn.close()
    
    # Prepare data payload (header + rows)
    data_to_write = [["PIN", "Nombre", "Fecha y Hora"]] + [list(row) for row in rows]
    print(f"Se extrajeron {len(rows)} registros.")

    # 4. Authenticate with Google Sheets
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]
    creds = Credentials.from_service_account_info(creds_info, scopes=scopes)
    client = gspread.authorize(creds)

    # 5. Write data to Google Sheets
    print(f"Actualizando la hoja de cálculo con ID: {SPREADSHEET_ID}...")
    try:
        sh = client.open_by_key(SPREADSHEET_ID)
        try:
            worksheet = sh.worksheet(SHEET_NAME)
        except gspread.exceptions.WorksheetNotFound:
            worksheet = sh.get_worksheet(0)
            
        worksheet.clear()
        worksheet.update(values=data_to_write, range_name="A1")
        print("¡Sincronización completada con éxito!")
        
        # Clean up the temporary file
        if os.path.exists(LOCAL_DB_PATH):
            os.remove(LOCAL_DB_PATH)
            
    except Exception as e:
        print(f"Error al actualizar Google Sheets: {e}")

if __name__ == "__main__":
    main()
