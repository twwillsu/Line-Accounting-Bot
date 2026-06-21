/**
 * LINE 記帳機器人 — Google Sheets 自動報表
 * 使用方式：在 Google Sheets > 擴充功能 > Apps Script 貼上此程式碼
 * 然後執行 setupSheet() 初始化
 */

const DETAIL_SHEET = "記帳明細";
const SUMMARY_SHEET = "本月摘要";
const PERSON_SHEET = "分攤明細";
const HISTORY_SHEET = "歷史紀錄";

// =============================================
// 📌 初始化：建立所有工作表與標題
// =============================================
function setupSheet() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();

  // 1. 記帳明細表
  let detail = ss.getSheetByName(DETAIL_SHEET) || ss.insertSheet(DETAIL_SHEET);
  detail.clearContents();
  const headers = [["日期", "品項", "分類", "金額", "付款人", "記錄時間"]];
  detail.getRange("A1:F1").setValues(headers)
    .setBackground("#27ACB2").setFontColor("#ffffff").setFontWeight("bold");
  detail.setColumnWidth(1, 100);
  detail.setColumnWidth(2, 150);
  detail.setColumnWidth(3, 100);
  detail.setColumnWidth(4, 80);
  detail.setColumnWidth(5, 100);
  detail.setColumnWidth(6, 130);

  // 2. 本月摘要表
  let summary = ss.getSheetByName(SUMMARY_SHEET) || ss.insertSheet(SUMMARY_SHEET);
  summary.clearContents();

  // 3. 分攤明細表
  let person = ss.getSheetByName(PERSON_SHEET) || ss.insertSheet(PERSON_SHEET);
  person.clearContents();

  // 4. 歷史紀錄表
  let history = ss.getSheetByName(HISTORY_SHEET) || ss.insertSheet(HISTORY_SHEET);
  history.clearContents();
  const hHeaders = [["月份", "總支出", "筆數", "最高單筆", "平均每筆"]];
  history.getRange("A1:E1").setValues(hHeaders)
    .setBackground("#7B66FF").setFontColor("#ffffff").setFontWeight("bold");

  // 設定自動觸發：每天更新一次報表
  ScriptApp.getProjectTriggers().forEach(t => ScriptApp.deleteTrigger(t));
  ScriptApp.newTrigger("updateAllReports")
    .timeBased().everyDays(1).atHour(0).create();

  SpreadsheetApp.getUi().alert("✅ 初始化完成！工作表已建立，每日自動更新報表。");
}

// =============================================
// 📊 主函式：更新所有報表
// =============================================
function updateAllReports() {
  updateMonthlySummary();
  updatePersonSplit();
  updateHistory();
}

// =============================================
// 📊 本月摘要（含圓餅圖）
// =============================================
function updateMonthlySummary() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const detailSheet = ss.getSheetByName(DETAIL_SHEET);
  const summarySheet = ss.getSheetByName(SUMMARY_SHEET);
  summarySheet.clearContents();

  const now = new Date();
  const currentMonth = `${now.getFullYear()}/${String(now.getMonth() + 1).padStart(2, "0")}`;

  // 讀取明細資料
  const data = detailSheet.getDataRange().getValues();
  const categoryMap = {};
  let total = 0;
  let count = 0;

  for (let i = 1; i < data.length; i++) {
    const row = data[i];
    if (!row[0]) continue;
    const dateStr = String(row[0]);
    if (!dateStr.startsWith(currentMonth)) continue;

    const category = row[2] || "其他";
    const amount = parseFloat(row[3]) || 0;
    categoryMap[category] = (categoryMap[category] || 0) + amount;
    total += amount;
    count++;
  }

  // 寫入標題
  summarySheet.getRange("A1").setValue(`📊 ${currentMonth} 月支出摘要`)
    .setFontSize(14).setFontWeight("bold");
  summarySheet.getRange("A2").setValue(`總支出：NT$ ${total.toLocaleString()}`).setFontColor("#E74C3C").setFontWeight("bold");
  summarySheet.getRange("A3").setValue(`記帳筆數：${count} 筆`).setFontColor("#666666");

  // 分類表格
  summarySheet.getRange("A5:B5").setValues([["分類", "金額"]])
    .setBackground("#F0F0F0").setFontWeight("bold");

  const categories = Object.entries(categoryMap).sort((a, b) => b[1] - a[1]);
  categories.forEach(([cat, amt], i) => {
    summarySheet.getRange(6 + i, 1).setValue(cat);
    summarySheet.getRange(6 + i, 2).setValue(amt);
  });

  // 建立圓餅圖
  const charts = summarySheet.getCharts();
  charts.forEach(c => summarySheet.removeChart(c));

  if (categories.length > 0) {
    const dataRange = summarySheet.getRange(5, 1, categories.length + 1, 2);
    const chart = summarySheet.newChart()
      .setChartType(Charts.ChartType.PIE)
      .addRange(dataRange)
      .setPosition(5, 4, 0, 0)
      .setOption("title", `${currentMonth} 支出分類`)
      .setOption("width", 450)
      .setOption("height", 350)
      .setOption("pieHole", 0.4)
      .setOption("legend", { position: "right" })
      .build();
    summarySheet.insertChart(chart);
  }
}

// =============================================
// 👥 每人分攤明細
// =============================================
function updatePersonSplit() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const detailSheet = ss.getSheetByName(DETAIL_SHEET);
  const personSheet = ss.getSheetByName(PERSON_SHEET);
  personSheet.clearContents();

  const now = new Date();
  const currentMonth = `${now.getFullYear()}/${String(now.getMonth() + 1).padStart(2, "0")}`;

  const data = detailSheet.getDataRange().getValues();
  const personMap = {};
  let total = 0;

  for (let i = 1; i < data.length; i++) {
    const row = data[i];
    if (!row[0]) continue;
    if (!String(row[0]).startsWith(currentMonth)) continue;
    const payer = row[4] || "未知";
    const amount = parseFloat(row[3]) || 0;
    personMap[payer] = (personMap[payer] || 0) + amount;
    total += amount;
  }

  const persons = Object.keys(personMap);
  const perPerson = persons.length > 0 ? total / persons.length : 0;

  // 標題
  personSheet.getRange("A1").setValue(`👥 ${currentMonth} 分攤明細`)
    .setFontSize(14).setFontWeight("bold");
  personSheet.getRange("A2").setValue(`總支出 NT$ ${total.toLocaleString()}，每人應付 NT$ ${Math.round(perPerson).toLocaleString()}`);

  // 表格標題
  personSheet.getRange("A4:D4").setValues([["成員", "已付金額", "應付金額", "差額（+收/-還）"]])
    .setBackground("#7B66FF").setFontColor("#ffffff").setFontWeight("bold");

  // 每人資料
  Object.entries(personMap).forEach(([person, paid], i) => {
    const diff = paid - perPerson;
    personSheet.getRange(5 + i, 1).setValue(person);
    personSheet.getRange(5 + i, 2).setValue(paid).setNumberFormat("NT$ #,##0");
    personSheet.getRange(5 + i, 3).setValue(Math.round(perPerson)).setNumberFormat("NT$ #,##0");
    const diffCell = personSheet.getRange(5 + i, 4);
    diffCell.setValue(Math.round(diff)).setNumberFormat("NT$ #,##0");
    diffCell.setFontColor(diff >= 0 ? "#27AE60" : "#E74C3C");
  });

  // 長條圖
  const charts = personSheet.getCharts();
  charts.forEach(c => personSheet.removeChart(c));

  if (persons.length > 0) {
    const dataRange = personSheet.getRange(4, 1, persons.length + 1, 2);
    const chart = personSheet.newChart()
      .setChartType(Charts.ChartType.BAR)
      .addRange(dataRange)
      .setPosition(4, 6, 0, 0)
      .setOption("title", "各人支出比較")
      .setOption("width", 450)
      .setOption("height", 300)
      .build();
    personSheet.insertChart(chart);
  }
}

// =============================================
// 📈 歷史紀錄（每月彙整）
// =============================================
function updateHistory() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const detailSheet = ss.getSheetByName(DETAIL_SHEET);
  const historySheet = ss.getSheetByName(HISTORY_SHEET);

  const data = detailSheet.getDataRange().getValues();
  const monthMap = {};

  for (let i = 1; i < data.length; i++) {
    const row = data[i];
    if (!row[0]) continue;
    const dateStr = String(row[0]);
    const month = dateStr.substring(0, 7);
    const amount = parseFloat(row[3]) || 0;

    if (!monthMap[month]) monthMap[month] = { total: 0, count: 0, max: 0 };
    monthMap[month].total += amount;
    monthMap[month].count++;
    if (amount > monthMap[month].max) monthMap[month].max = amount;
  }

  // 清除舊資料（保留標題）
  const lastRow = historySheet.getLastRow();
  if (lastRow > 1) historySheet.getRange(2, 1, lastRow - 1, 5).clearContent();

  // 寫入歷史資料
  const months = Object.keys(monthMap).sort();
  months.forEach((month, i) => {
    const { total, count, max } = monthMap[month];
    historySheet.getRange(2 + i, 1).setValue(month);
    historySheet.getRange(2 + i, 2).setValue(total).setNumberFormat("NT$ #,##0");
    historySheet.getRange(2 + i, 3).setValue(count);
    historySheet.getRange(2 + i, 4).setValue(max).setNumberFormat("NT$ #,##0");
    historySheet.getRange(2 + i, 5).setValue(count > 0 ? Math.round(total / count) : 0).setNumberFormat("NT$ #,##0");
  });

  // 月趨勢折線圖
  const charts = historySheet.getCharts();
  charts.forEach(c => historySheet.removeChart(c));

  if (months.length > 1) {
    const dataRange = historySheet.getRange(1, 1, months.length + 1, 2);
    const chart = historySheet.newChart()
      .setChartType(Charts.ChartType.LINE)
      .addRange(dataRange)
      .setPosition(2, 7, 0, 0)
      .setOption("title", "每月支出趨勢")
      .setOption("width", 500)
      .setOption("height", 300)
      .setOption("curveType", "function")
      .build();
    historySheet.insertChart(chart);
  }
}
