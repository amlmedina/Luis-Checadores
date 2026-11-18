/**
 * API gratuita en Google Apps Script para alimentar el Dashboard Web directo desde Google Sheets.
 * 1. Abre tu Google Sheets -> Extensiones -> Apps Script.
 * 2. Pega este código y guarda.
 * 3. Haz clic en "Implementar" -> "Nueva implementación" -> Tipo: "Aplicación web".
 *    - Ejecutar como: "Yo"
 *    - Quién tiene acceso: "Cualquier usuario"
 * 4. Copia la URL de la aplicación web y pégala en APPS_SCRIPT_URL dentro de docs/index.html.
 */
function doGet() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var sheet = ss.getSheetByName("Checadas_ADMS");
  if (!sheet) {
    return ContentService.createTextOutput(JSON.stringify({ error: "No existe la hoja Checadas_ADMS" }))
      .setMimeType(ContentService.MimeType.JSON);
  }

  var data = sheet.getDataRange().getValues();
  if (data.length <= 1) {
    return ContentService.createTextOutput(JSON.stringify({ metadata: {}, records: [] }))
      .setMimeType(ContentService.MimeType.JSON);
  }

  // Cargar catálogo PIN -> Nombre desde Sheet1 y/o Empleados
  var pinToName = {};
  ["Sheet1", "Empleados"].forEach(function(tabName) {
    var s = ss.getSheetByName(tabName);
    if (!s) return;
    var rows = s.getDataRange().getValues();
    for (var r = 1; r < rows.length; r++) {
      var p = String(rows[r][0] || "").trim();
      var n = String(rows[r][1] || "").trim();
      if (p && n && !pinToName[p]) pinToName[p] = n;
    }
  });

  var grouped = {};
  var latestStr = "";

  for (var i = 1; i < data.length; i++) {
    var pin = String(data[i][0] || "").trim();
    var fechaHoraRaw = data[i][1];
    var tienda = String(data[i][5] || "SinTienda").trim();
    if (!pin || !fechaHoraRaw) continue;

    var dt = new Date(fechaHoraRaw);
    if (isNaN(dt.getTime())) continue;

    var fecha = Utilities.formatDate(dt, ss.getSpreadsheetTimeZone(), "yyyy-MM-dd");
    var hora = Utilities.formatDate(dt, ss.getSpreadsheetTimeZone(), "HH:mm:ss");
    var full = fecha + " " + hora;
    if (full > latestStr) latestStr = full;

    var key = pin + "|" + fecha + "|" + tienda;
    if (!grouped[key]) grouped[key] = { pin: pin, fecha: fecha, tienda: tienda, punches: [] };
    grouped[key].punches.push(dt);
  }

  var records = [];
  for (var k in grouped) {
    var g = grouped[k];
    g.punches.sort(function(a, b) { return a - b; });
    var p = g.punches;
    var fmt = function(d) { return Utilities.formatDate(d, ss.getSpreadsheetTimeZone(), "HH:mm:ss"); };
    var dur = function(ms) {
      if (ms <= 0) return "0h 00m";
      var m = Math.floor(ms / 60000);
      return Math.floor(m / 60) + "h " + ("0" + (m % 60)).slice(-2) + "m";
    };

    var entrada = fmt(p[0]);
    var salidaComer = "";
    var regresoComer = "";
    var salida = "";
    var horas = "";

    if (p.length === 2) {
      salida = fmt(p[1]);
      horas = dur(p[1] - p[0]);
    } else if (p.length === 3) {
      salidaComer = fmt(p[1]);
      salida = fmt(p[2]);
      horas = dur(p[2] - p[0]);
    } else if (p.length >= 4) {
      salidaComer = fmt(p[1]);
      regresoComer = fmt(p[2]);
      salida = fmt(p[p.length - 1]);
      horas = dur((p[p.length - 1] - p[0]) - (p[2] - p[1]));
    }

    records.push({
      pin: g.pin,
      nombre: pinToName[g.pin] || ("PIN " + g.pin),
      fecha: g.fecha,
      hora: entrada,
      salida_comer: salidaComer,
      regreso_comer: regresoComer,
      salida: salida,
      horas_trabajadas: horas,
      tienda: g.tienda
    });
  }

  var payload = {
    metadata: {
      db_mtime: "Google Sheets en vivo",
      latest_punch: latestStr,
      total_records: records.length
    },
    records: records
  };

  return ContentService.createTextOutput(JSON.stringify(payload))
    .setMimeType(ContentService.MimeType.JSON);
}
