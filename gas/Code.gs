/**
 * 東京ぱたしーグルメ 状態API（ISS-475）
 *
 * 「行った」「たぶん行かない」を Google Sheets に読み書きする Web App。
 * GitHub Pages は静的サイトなので、書き込み先はここしか無い。
 * 置き場: スプレッドシート（config.yaml の sheets.spreadsheet_id）の「拡張機能 > Apps Script」。
 * 手順は gas/README.md。
 *
 * リクエストは POST・本文 JSON（Content-Type は text/plain。application/json だと
 * ブラウザがプリフライトを飛ばし、GAS はそれに応答できない）。
 *   {action: "list", token}                      → {ok, items: [{place_id, name, status, status_date, visited}]}
 *   {action: "set",  token, place_id, name, status} → {ok, place_id, status, status_date}
 * status は visited / skipped / none。
 *
 * token はスクリプトプロパティ GATE_TOKEN と照合する。サイトの目隠しトークン（ISS-518）と同じ値。
 * 合わないリクエストは何も書かずに {ok:false, error:"forbidden"} を返す。
 * 目隠しと同じく「いたずら防止」の位置づけで、完全な認証ではない。
 */

var SHEET_NAME = 'visited';
var LOG_SHEET_NAME = 'status_log';
var STATUSES = ['visited', 'skipped', 'none'];
// 既存の5列の後ろに足す。既存行の位置は変えない（手で開いたときに列がずれないように）
var REQUIRED_HEADERS = ['place_id', 'name', 'date_recommended', 'visited', 'visited_date', 'status', 'status_date'];

function doPost(e) {
  var req;
  try {
    req = JSON.parse((e && e.postData && e.postData.contents) || '{}');
  } catch (err) {
    return json_({ ok: false, error: 'bad_json' });
  }
  if (!checkToken_(req.token)) {
    return json_({ ok: false, error: 'forbidden' });
  }
  try {
    if (req.action === 'list') return json_(list_());
    if (req.action === 'set') return json_(set_(req));
    return json_({ ok: false, error: 'unknown_action' });
  } catch (err) {
    return json_({ ok: false, error: String(err && err.message || err) });
  }
}

// ブラウザで URL を直接開いたとき用。何も返さない（中身を覗けないように）
function doGet() {
  return json_({ ok: true, service: 'tokyo-gourmet-status' });
}

function checkToken_(token) {
  var expected = PropertiesService.getScriptProperties().getProperty('GATE_TOKEN');
  // 未設定のまま公開すると誰でも書けてしまうので、未設定は常に拒否
  if (!expected || typeof token !== 'string') return false;
  return token === expected;
}

function list_() {
  var sheet = getSheet_();
  var cols = ensureHeaders_(sheet);
  var last = sheet.getLastRow();
  var items = [];
  if (last >= 2) {
    var values = sheet.getRange(2, 1, last - 1, sheet.getLastColumn()).getValues();
    values.forEach(function (row) {
      var placeId = String(row[cols.place_id] || '');
      if (!placeId) return;
      items.push({
        place_id: placeId,
        name: String(row[cols.name] || ''),
        status: String(row[cols.status] || ''),
        status_date: fmtDate_(row[cols.status_date]),
        visited: String(row[cols.visited]),
      });
    });
  }
  return { ok: true, items: items };
}

function set_(req) {
  var placeId = String(req.place_id || '');
  var status = String(req.status || '');
  if (!placeId) return { ok: false, error: 'place_id_required' };
  if (STATUSES.indexOf(status) < 0) return { ok: false, error: 'bad_status' };

  // 2台から同時に押しても行が重複しないよう、探索〜書き込みを直列化する
  var lock = LockService.getScriptLock();
  lock.waitLock(10000);
  try {
    var sheet = getSheet_();
    var cols = ensureHeaders_(sheet);
    var width = sheet.getLastColumn();
    var rowIndex = findRow_(sheet, cols, placeId);
    var now = new Date();
    var today = Utilities.formatDate(now, 'Asia/Tokyo', 'yyyy-MM-dd');
    var before = 'none';

    if (rowIndex < 0) {
      var fresh = new Array(width).fill('');
      fresh[cols.place_id] = placeId;
      fresh[cols.name] = String(req.name || '');
      fresh[cols.visited] = 'FALSE';
      sheet.appendRow(fresh);
      rowIndex = sheet.getLastRow();
    } else {
      before = String(sheet.getRange(rowIndex, cols.status + 1).getValue() || 'none');
    }

    var row = sheet.getRange(rowIndex, 1, 1, width).getValues()[0];
    row[cols.status] = status;
    row[cols.status_date] = status === 'none' ? '' : today;
    // 旧来の visited 列も揃える（手作業の読み手が迷わないように）
    if (status === 'visited') {
      row[cols.visited] = 'TRUE';
      row[cols.visited_date] = today;
    } else {
      row[cols.visited] = 'FALSE';
      row[cols.visited_date] = '';
    }
    sheet.getRange(rowIndex, 1, 1, width).setValues([row]);

    // 全変更をログに残す（いたずらで消されても戻せるように）
    getLogSheet_().appendRow([now, placeId, String(req.name || ''), before, status]);

    return { ok: true, place_id: placeId, status: status, status_date: row[cols.status_date] };
  } finally {
    lock.releaseLock();
  }
}

function getSheet_() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var sheet = ss.getSheetByName(SHEET_NAME);
  if (!sheet) {
    sheet = ss.insertSheet(SHEET_NAME);
    sheet.appendRow(REQUIRED_HEADERS);
  }
  return sheet;
}

function getLogSheet_() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var sheet = ss.getSheetByName(LOG_SHEET_NAME);
  if (!sheet) {
    sheet = ss.insertSheet(LOG_SHEET_NAME);
    sheet.appendRow(['timestamp', 'place_id', 'name', 'from', 'to']);
  }
  return sheet;
}

/** 見出し行を読み、足りない列は末尾に足す。{列名: 0始まりの列番号} を返す */
function ensureHeaders_(sheet) {
  var width = Math.max(sheet.getLastColumn(), 1);
  var headers = sheet.getRange(1, 1, 1, width).getValues()[0].map(String);
  REQUIRED_HEADERS.forEach(function (h) {
    if (headers.indexOf(h) < 0) {
      headers.push(h);
      sheet.getRange(1, headers.length).setValue(h);
    }
  });
  var cols = {};
  headers.forEach(function (h, i) { cols[h] = i; });
  return cols;
}

/** place_id の行番号（1始まり）。無ければ -1 */
function findRow_(sheet, cols, placeId) {
  var last = sheet.getLastRow();
  if (last < 2) return -1;
  var ids = sheet.getRange(2, cols.place_id + 1, last - 1, 1).getValues();
  for (var i = 0; i < ids.length; i++) {
    if (String(ids[i][0]) === placeId) return i + 2;
  }
  return -1;
}

function fmtDate_(v) {
  // Sheets が "2026-09-11" を日付に変換して返す。その値は instanceof Date が false になることがある
  if (Object.prototype.toString.call(v) === '[object Date]') {
    return Utilities.formatDate(v, 'Asia/Tokyo', 'yyyy-MM-dd');
  }
  return String(v || '');
}

function json_(obj) {
  return ContentService.createTextOutput(JSON.stringify(obj)).setMimeType(ContentService.MimeType.JSON);
}
