# Configuración de rutas
$carpetaOrigen = "C:\Program Files (x86)\Reloj Checador Steren\"
$carpetaDestino = "G:\Mi unidad\Checador"

# Asegurar que la carpeta de destino exista en Google Drive
if (-not (Test-Path $carpetaDestino)) {
    New-Item -ItemType Directory -Path $carpetaDestino -Force | Out-Null
}

# Verificar si la carpeta origen existe
if (Test-Path $carpetaOrigen) {
    
    # Copiar todos los archivos de la carpeta origen a la destino
    # -Recurse copia también subcarpetas (por si hay archivos en carpetas de "Data" o "Backup")
    # -Force sobrescribe los archivos existentes
    Copy-Item -Path "$carpetaOrigen\*" -Destination $carpetaDestino -Recurse -Force
    
    Write-Output "¡Éxito! Todos los archivos de la carpeta han sido copiados a Google Drive."
} else {
    Write-Warning "No se encontró la carpeta de origen: $carpetaOrigen"
}