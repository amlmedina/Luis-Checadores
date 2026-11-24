/**
 * API gratuita en Google Apps Script para alimentar el Dashboard Web directo desde Google Sheets.
 * 1. Abre tu Google Sheets -> Extensiones -> Apps Script.
 * 2. Pega este código y guarda.
 * 3. Haz clic en "Implementar" -> "Gestionar implementaciones" -> Editar (lápiz) -> Nueva versión -> Implementar.
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
      if (p && n) pinToName[p] = n;
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
    // Protección contra doble checada (< 5 min): en entrada toma la más temprana, en salida toma la más tardía
    var rawP = g.punches;
    var p = [];
    var WINDOW_MS = 5 * 60 * 1000;
    for (var idx = 0; idx < rawP.length; idx++) {
      if (p.length === 0) {
        p.push(rawP[idx]);
      } else {
        var diff = rawP[idx] - p[p.length - 1];
        if (diff <= WINDOW_MS) {
          if (p.length > 1) p[p.length - 1] = rawP[idx];
        } else {
          p.push(rawP[idx]);
        }
      }
    }

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

  var config = { tolerance: 5, storeHours: {} };
  var cfgSheet = ss.getSheetByName("Config_Web");
  if (cfgSheet && cfgSheet.getLastRow() >= 1) {
    try {
      var rawCfg = cfgSheet.getRange(1, 1).getValue();
      if (rawCfg) config = JSON.parse(rawCfg);
    } catch (e) {}
  }

  var overrides = {};
  var notesSheet = ss.getSheetByName("Notas_Web");
  if (notesSheet && notesSheet.getLastRow() > 1) {
    var nRows = notesSheet.getDataRange().getValues();
    for (var n = 1; n < nRows.length; n++) {
      var nk = String(nRows[n][0] || "");
      if (nk) {
        overrides[nk] = {
          status: String(nRows[n][1] || ""),
          comment: String(nRows[n][2] || "")
        };
      }
    }
  }

  var payload = {
    metadata: {
      db_mtime: "Google Sheets en vivo",
      latest_punch: latestStr,
      total_records: records.length
    },
    config: config,
    overrides: overrides,
    employees: pinToName,
    records: records
  };

  return ContentService.createTextOutput(JSON.stringify(payload))
    .setMimeType(ContentService.MimeType.JSON);
}

function doPost(e) {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var body = JSON.parse(e.postData.contents || "{}");

  if (body.type === "config") {
    var cfgSheet = ss.getSheetByName("Config_Web") || ss.insertSheet("Config_Web");
    cfgSheet.getRange(1, 1).setValue(JSON.stringify(body.config || {}));
  } else if (body.type === "employee" && body.pin) {
    var empSheet = ss.getSheetByName("Empleados") || ss.insertSheet("Empleados");
    if (empSheet.getLastRow() === 0) {
      empSheet.appendRow(["PIN", "Nombre"]);
    }
    var eRows = empSheet.getDataRange().getValues();
    var eRow = -1;
    for (var j = 1; j < eRows.length; j++) {
      if (String(eRows[j][0]).trim() === String(body.pin).trim()) {
        eRow = j + 1;
        break;
      }
    }
    if (eRow > 0) {
      empSheet.getRange(eRow, 2).setValue(body.name || "");
    } else {
      empSheet.appendRow([String(body.pin).trim(), body.name || ""]);
    }
  } else if (body.type === "override" && body.key) {
    var notesSheet = ss.getSheetByName("Notas_Web") || ss.insertSheet("Notas_Web");
    if (notesSheet.getLastRow() === 0) {
      notesSheet.appendRow(["Key", "Estatus", "Comentario"]);
    }
    var rows = notesSheet.getDataRange().getValues();
    var foundRow = -1;
    for (var i = 1; i < rows.length; i++) {
      if (String(rows[i][0]) === String(body.key)) {
        foundRow = i + 1;
        break;
      }
    }
    var st = body.status || "";
    var cm = body.comment || "";
    if (foundRow > 0) {
      notesSheet.getRange(foundRow, 2, 1, 2).setValues([[st, cm]]);
    } else {
      notesSheet.appendRow([body.key, st, cm]);
    }
  }

  return ContentService.createTextOutput(JSON.stringify({ ok: true }))
    .setMimeType(ContentService.MimeType.JSON);
}
