/**
 * Genera un reporte amigable de asistencias agrupando las marcas por día y empleado.
 * Calcula la hora de entrada (primer registro), la de salida (último registro) y las horas trabajadas.
 */
function generarReporteAmigable() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  
  // 1. Obtener la hoja con los datos crudos (Sheet1 o primera pestaña)
  var rawSheet = ss.getActiveSheet();
  var rawData = rawSheet.getDataRange().getValues();
  
  if (rawData.length <= 1) {
    SpreadsheetApp.getUi().alert("No hay suficientes datos en la hoja actual para generar un reporte.");
    return;
  }
  
  // 2. Procesar datos (Saltando cabeceras en index 0)
  // Estructura: { "Nombre (PIN)": { "YYYY-MM-DD": [marcas_de_tiempo] } }
  var records = {};
  
  for (var i = 1; i < rawData.length; i++) {
    var pin = rawData[i][0];
    var nombre = rawData[i][1];
    var fechaHoraStr = rawData[i][2]; // Formato esperado: YYYY-MM-DD HH:MM:SS o fecha de JS
    
    if (!pin || !nombre || !fechaHoraStr) continue;
    
    var dateObj = new Date(fechaHoraStr);
    if (isNaN(dateObj.getTime())) continue; // Validar fecha
    
    var empleadoKey = nombre + " (PIN: " + pin + ")";
    var fechaKey = Utilities.formatDate(dateObj, Session.getScriptTimeZone(), "yyyy-MM-dd");
    var horaStr = Utilities.formatDate(dateObj, Session.getScriptTimeZone(), "HH:mm:ss");
    
    if (!records[empleadoKey]) {
      records[empleadoKey] = {};
    }
    if (!records[empleadoKey][fechaKey]) {
      records[empleadoKey][fechaKey] = [];
    }
    
    records[empleadoKey][fechaKey].push(dateObj);
  }
  
  // 3. Crear o limpiar la hoja de Reporte
  var reportSheetName = "Reporte de Asistencia";
  var reportSheet = ss.getSheetByName(reportSheetName);
  if (reportSheet) {
    reportSheet.clear();
  } else {
    reportSheet = ss.insertSheet(reportSheetName);
  }
  
  // 4. Preparar cabeceras y estructura del reporte
  var outputData = [
    ["Empleado", "Fecha", "Primer Registro (Entrada)", "Último Registro (Salida)", "Horas en Sitio"]
  ];
  
  // Ordenar empleados alfabéticamente
  var empleados = Object.keys(records).sort();
  
  for (var j = 0; j < empleados.length; j++) {
    var emp = empleados[j];
    var fechas = Object.keys(records[emp]).sort(); // Fechas de menor a mayor
    
    for (var k = 0; k < fechas.length; k++) {
      var fecha = fechas[k];
      var marcas = records[emp][fecha];
      
      // Ordenar las marcas de tiempo de este día cronológicamente
      marcas.sort(function(a, b) { return a - b; });
      
      var entradaObj = marcas[0];
      var salidaObj = marcas[marcas.length - 1];
      
      var entradaStr = Utilities.formatDate(entradaObj, Session.getScriptTimeZone(), "HH:mm:ss");
      var salidaStr = (marcas.length > 1) ? Utilities.formatDate(salidaObj, Session.getScriptTimeZone(), "HH:mm:ss") : "Sin registro de salida";
      
      // Calcular horas transcurridas
      var horasEnSitio = "";
      if (marcas.length > 1) {
        var diffMs = salidaObj - entradaObj;
        var diffHrs = Math.floor(diffMs / (1000 * 60 * 60));
        var diffMins = Math.floor((diffMs % (1000 * 60 * 60)) / (1000 * 60));
        horasEnSitio = diffHrs + "h " + diffMins + "m";
      } else {
        horasEnSitio = "1 marca (N/A)";
      }
      
      outputData.push([emp, fecha, entradaStr, salidaStr, horasEnSitio]);
    }
  }
  
  // 5. Escribir y estilizar el reporte
  reportSheet.getRange(1, 1, outputData.length, outputData[0].length).setValues(outputData);
  
  // Estilo estético profesional (Tonos Azules/Grises)
  reportSheet.getRange("A1:E1")
    .setBackground("#1A73E8") // Azul moderno de Google
    .setFontColor("white")
    .setFontWeight("bold")
    .setFontSize(11)
    .setHorizontalAlignment("center");
    
  reportSheet.getRange(2, 1, outputData.length - 1, outputData[0].length)
    .setFontSize(10)
    .setVerticalAlignment("middle");

  // Alinear columnas
  reportSheet.getRange(2, 2, outputData.length - 1, 3).setHorizontalAlignment("center"); // Fechas y horas al centro
  reportSheet.getRange(2, 5, outputData.length - 1, 1).setHorizontalAlignment("center"); // Horas totales
  
  // Bordes delgados
  reportSheet.getRange(1, 1, outputData.length, 5).setBorder(true, true, true, true, true, true, "#E0E0E0", SpreadsheetApp.BorderStyle.SOLID);
  
  // Ajustar ancho de columnas automáticamente
  for (var col = 1; col <= 5; col++) {
    reportSheet.autoResizeColumn(col);
  }
  
  // Activar la nueva hoja
  ss.setActiveSheet(reportSheet);
  
  SpreadsheetApp.getUi().alert("¡Reporte generado con éxito en la pestaña 'Reporte de Asistencia'!");
}

/**
 * Añade un menú personalizado en la hoja de cálculo al abrir el archivo.
 */
function onOpen() {
  var ui = SpreadsheetApp.getUi();
  ui.createMenu('Reportes Checador')
      .addItem('Generar Reporte de Asistencias', 'generarReporteAmigable')
      .addToUi();
}
