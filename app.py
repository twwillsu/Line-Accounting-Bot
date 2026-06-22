/**
 * LINE 記帳機器人 — Google Sheets 自動報表 v3
 * 功能：記帳明細美化（灰底+圖表）、歷史紀錄即時更新、月初自動清除
 */

const DETAIL_SHEET = "記帳明細";
const HISTORY_SHEET = "歷史紀錄";

// =============================================
// 📌 初始化：執行一次即可
// =============================================
function setupSheet() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();

  // 記帳明細
  let detail = ss.getSheetByName(DETAIL_SHEET) || ss.insertSheet(DETAIL_SHEET);
  detail.getRange("A1:E1")
    .setValues([["日期時間", "品項", "分類", "金額", "付款人"]])
    .setBackground("#27ACB2").setFontColor("#ffffff").setFontWeight("bold");
  detail.setColumnWidths(1, 5, 130);
  detail.setColumnWidth(1, 155);
  detail.setColumnWidth(2, 140);
  detail.setColumnWidth(4, 80);

  // 歷史紀錄
  let history = ss.getSheetByName(HISTORY_SHEET) || ss.insertSheet(HISTORY_SHEET);

  // 清除所有舊觸發器
  ScriptApp.getProjectTriggers().forEach(t => ScriptApp.deleteTrigger(t));

  // 每日凌晨月初清除
  ScriptApp.newTrigger("midnightTask").timeBased().everyDays(1).atHour(0).create();

  // onChange 觸發器（試算表內容異動時觸發）
  ScriptApp.newTrigger("onSheetChange").forSpreadsheet(ss).onChange().create();

  SpreadsheetApp.getUi().alert("✅ 初始化完成！觸發器已設定。");
}

// =============================================
// 🔔 試算表變動時觸發（新增記帳 → 立即更新）
// =============================================
function onSheetChange(e) {
  try {
    const ss = SpreadsheetApp.getActiveSpreadsheet();
    const sheet = ss.getActiveSheet();
    if (sheet.getName() !== DETAIL_SHEET) return;
    formatDetailSheet();
    updateHistory();
  } catch(err) {
    Logger.log("onSheetChange error: " + err);
  }
}

// =============================================
// 🕛 每日凌晨任務（月初清除明細）
// =============================================
function midnightTask() {
  const now = new Date();
  updateHistory(); // 先存歷史
  if (now.getDate() === 1) {
    clearDetailSheet(); // 再清明細
  }
  formatDetailSheet();
}

// =============================================
// 🗑️ 清除記帳明細（保留標題）
// =============================================
function clearDetailSheet() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const sheet = ss.getSheetByName(DETAIL_SHEET);
  const lastRow = sheet.getLastRow();
  if (lastRow > 1) {
    sheet.getRange(2, 1, lastRow - 1, 5).clearContent().setBackground(null);
    sheet.getCharts().forEach(c => sheet.removeChart(c));
    // 清除圖表輔助資料欄
    const lastCol = sheet.getLastColumn();
    if (lastCol > 5) sheet.getRange(1, 7, lastRow, lastCol - 6).clearContent().setBackground(null);
  }
}

// =============================================
// 🎨 美化記帳明細（單數行灰底 + 圓餅圖 + 折線圖）
// =============================================
function formatDetailSheet() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const sheet = ss.getSheetByName(DETAIL_SHEET);
  const lastRow = sheet.getLastRow();
  if (lastRow < 2) return;

  const dataRows = lastRow - 1;

  // 單數筆（第1,3,5...筆）= 第2,4,6...列 → 灰底
  for (let r = 2; r <= lastRow; r++) {
    if ((r % 2) === 0) {
      sheet.getRange(r, 1, 1, 5).setBackground("#EFEFEF");
    } else {
      sheet.getRange(r, 1, 1, 5).setBackground(null);
    }
  }

  // 讀取資料
  const data = sheet.getRange(2, 1, dataRows, 5).getValues();
  const categoryMap = {};
  const dateMap = {};

  data.forEach(row => {
    if (!row[0] && !row[1]) return;
    const category = row[2] || "其他";
    const amount = parseFloat(row[3]) || 0;

    // 分類統計（圓餅圖）
    categoryMap[category] = (categoryMap[category] || 0) + amount;

    // 日期統計（折線圖）
    let dateKey = "";
    if (row[0] instanceof Date) {
      dateKey = Utilities.formatDate(row[0], "Asia/Taipei", "MM/dd");
    } else if (row[0]) {
      dateKey = String(row[0]).substring(5, 10); // MM/DD
    }
    if (dateKey) dateMap[dateKey] = (dateMap[dateKey] || 0) + amount;
  });

  // 清除舊圖表和輔助欄
  sheet.getCharts().forEach(c => sheet.removeChart(c));
  const lastCol = sheet.getLastColumn();
  if (lastCol >= 7) sheet.getRange(1, 7, Math.max(lastRow, 20), Math.max(lastCol - 6, 6)).clearContent().setBackground(null);

  // === G欄：圓餅圖資料 ===
  const cats = Object.entries(categoryMap).sort((a, b) => b[1] - a[1]);
  sheet.getRange("G1:H1").setValues([["分類", "金額"]])
    .setBackground("#27ACB2").setFontColor("#fff").setFontWeight("bold");
  cats.forEach(([cat, amt], i) => {
    sheet.getRange(2 + i, 7).setValue(cat);
    sheet.getRange(2 + i, 8).setValue(amt);
  });

  // === J欄：折線圖資料 ===
  const dates = Object.entries(dateMap).sort((a, b) => a[0].localeCompare(b[0]));
  sheet.getRange("J1:K1").setValues([["日期", "金額"]])
    .setBackground("#27ACB2").setFontColor("#fff").setFontWeight("bold");
  dates.forEach(([date, amt], i) => {
    sheet.getRange(2 + i, 10).setValue(date);
    sheet.getRange(2 + i, 11).setValue(amt);
  });

  // === 圓餅圖 ===
  if (cats.length > 0) {
    const pieRange = sheet.getRange(1, 7, cats.length + 1, 2);
    const pieChart = sheet.newChart()
      .setChartType(Charts.ChartType.PIE)
      .addRange(pieRange)
      .setPosition(1, 13, 0, 0)
      .setOption("title", "支出分類圓餅圖")
      .setOption("width", 420).setOption("height", 300)
      .setOption("pieHole", 0.35)
      .setOption("legend", { position: "right" })
      .build();
    sheet.insertChart(pieChart);
  }

  // === 折線圖 ===
  if (dates.length > 0) {
    const lineRange = sheet.getRange(1, 10, dates.length + 1, 2);
    const lineChart = sheet.newChart()
      .setChartType(Charts.ChartType.LINE)
      .addRange(lineRange)
      .setPosition(18, 13, 0, 0)
      .setOption("title", "每日支出折線圖")
      .setOption("width", 420).setOption("height", 300)
      .setOption("curveType", "function")
      .setOption("vAxis", { title: "NT$" })
      .build();
    sheet.insertChart(lineChart);
  }
}

// =============================================
// 📈 歷史紀錄（每人每月詳細，即時更新）
// =============================================
function updateHistory() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const detailSheet = ss.getSheetByName(DETAIL_SHEET);
  const historySheet = ss.getSheetByName(HISTORY_SHEET);

  const lastRow = detailSheet.getLastRow();
  if (lastRow < 2) return;

  const data = detailSheet.getRange(2, 1, lastRow - 1, 5).getValues();

  // { "2026/06": { "Will": { total: 500, items: {"餐飲": 300, "交通": 200} } } }
  const monthPersonMap = {};

  data.forEach(row => {
    if (!row[1] && !row[3]) return; // 跳過空行
    let month;
    if (row[0] instanceof Date) {
      month = Utilities.formatDate(row[0], "Asia/Taipei", "yyyy/MM");
    } else if (row[0]) {
      month = String(row[0]).substring(0, 7);
    } else {
      return;
    }

    const category = row[2] || "其他";
    const amount = parseFloat(row[3]) || 0;
    const payer = row[4] || "未知";

    if (!monthPersonMap[month]) monthPersonMap[month] = {};
    if (!monthPersonMap[month][payer]) monthPersonMap[month][payer] = { total: 0, items: {} };
    monthPersonMap[month][payer].total += amount;
    monthPersonMap[month][payer].items[category] = (monthPersonMap[month][payer].items[category] || 0) + amount;
  });

  if (Object.keys(monthPersonMap).length === 0) return;

  // 收集所有人名和分類
  const allPersons = new Set();
  const allCategories = new Set();
  Object.values(monthPersonMap).forEach(persons => {
    Object.keys(persons).forEach(p => allPersons.add(p));
    Object.values(persons).forEach(pd => Object.keys(pd.items).forEach(c => allCategories.add(c)));
  });
  const personList = Array.from(allPersons).sort();
  const catList = Array.from(allCategories).sort();

  // 清除歷史工作表
  historySheet.clearContents();
  historySheet.getCharts().forEach(c => historySheet.removeChart(c));

  // 標題列
  const headerRow = ["月份"];
  personList.forEach(p => {
    headerRow.push(`${p} 合計`);
    catList.forEach(c => headerRow.push(`${p} - ${c}`));
  });
  historySheet.getRange(1, 1, 1, headerRow.length)
    .setValues([headerRow])
    .setBackground("#7B66FF").setFontColor("#ffffff").setFontWeight("bold");

  // 資料列
  const months = Object.keys(monthPersonMap).sort();
  months.forEach((month, rowIdx) => {
    const rowData = [month];
    personList.forEach(person => {
      const pd = monthPersonMap[month][person] || { total: 0, items: {} };
      rowData.push(pd.total);
      catList.forEach(cat => rowData.push(pd.items[cat] || 0));
    });
    const r = 2 + rowIdx;
    historySheet.getRange(r, 1, 1, rowData.length).setValues([rowData]);
    // 單數行灰底
    if (rowIdx % 2 === 0) {
      historySheet.getRange(r, 1, 1, rowData.length).setBackground("#EFEFEF");
    }
  });

  // 欄寬
  historySheet.setColumnWidth(1, 80);
  for (let c = 2; c <= headerRow.length; c++) historySheet.setColumnWidth(c, 100);

  // === 折線圖輔助資料（每人合計） ===
  const chartStartCol = headerRow.length + 2;
  const chartHeaders = ["月份", ...personList.map(p => `${p} 合計`)];
  historySheet.getRange(1, chartStartCol, 1, chartHeaders.length)
    .setValues([chartHeaders])
    .setBackground("#27ACB2").setFontColor("#fff").setFontWeight("bold");

  months.forEach((month, i) => {
    const rowVals = [month];
    personList.forEach(person => {
      rowVals.push((monthPersonMap[month][person] || { total: 0 }).total);
    });
    historySheet.getRange(2 + i, chartStartCol, 1, rowVals.length).setValues([rowVals]);
  });

  // 折線圖
  const chartDataRange = historySheet.getRange(1, chartStartCol, months.length + 1, personList.length + 1);
  const lineChart = historySheet.newChart()
    .setChartType(Charts.ChartType.LINE)
    .addRange(chartDataRange)
    .setPosition(months.length + 3, 1, 0, 0)
    .setOption("title", "各人每月花費趨勢")
    .setOption("width", 600).setOption("height", 350)
    .setOption("curveType", "function")
    .setOption("legend", { position: "bottom" })
    .setOption("vAxis", { title: "NT$" })
    .build();
  historySheet.insertChart(lineChart);
}

// 手動觸發（測試用）
function manualUpdate() {
  formatDetailSheet();
  updateHistory();
  SpreadsheetApp.getUi().alert("✅ 已更新記帳明細樣式與歷史紀錄！");
}
