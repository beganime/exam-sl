import fs from "node:fs/promises";
import { Workbook, SpreadsheetFile } from "@oai/artifact-tool";

const sourcePath = "C:/Users/ThinkPad/.codex/attachments/a6cfe610-0107-4439-915a-f1035079923e/pasted-text.txt";
const outputDir = "C:/Users/ThinkPad/Desktop/projects/ExamSL/outputs/examsl_import_prep";
const source = await fs.readFile(sourcePath, "utf8");

const looksLikeLogin = (value) => /@|^[a-zA-Z]{1,5}\d{4,}|^[a-zA-Z0-9._-]{5,}$/.test(value || "");
const subjectPatterns = [
  [/(рус(?:ский)?(?:\s+язык)?|рус\.?(?:\s*яз)?)/iu, "Русский язык"],
  [/(математика|матем|(?:^|[^а-яё])мат(?:[^а-яё]|$))/iu, "Математика"],
  [/(английский(?:\s+язык)?|англ(?:\.\s*яз)?|\bангл\b)/iu, "Английский язык"],
  [/(биология|\bбио\b)/iu, "Биология"],
  [/(химия|\bхим\b)/iu, "Химия"],
  [/(физика|\bфиз\b)/iu, "Физика"],
  [/(информатика|информ\.?|ИКТ)/iu, "Информатика и ИКТ"],
  [/(история|\bист\b)/iu, "История"],
  [/(обществознание|общество|\bобщ\b)/iu, "Обществознание"],
  [/(литература|литер)/iu, "Литература"],
  [/(география|географ)/iu, "География"],
  [/(физкультура|физическая культура)/iu, "Физическая культура"],
];

function normalizeParts(line) {
  const parts = line.split("\t").map((x) => x.trim());
  while (parts.length && !parts[0]) parts.shift();
  while (parts.length && !parts.at(-1)) parts.pop();
  return parts;
}

function extractDate(text) {
  let match = text.match(/\b(\d{1,2})[./](0?7)(?:[./](\d{2,4}))?\b/u);
  if (!match) match = text.match(/(?:^|\s)(1[5-9]|2[0-9])(?:-?го|гo|г)(?=\s|$)/iu);
  if (!match) return "";
  const day = Number(match[1]);
  const year = match[3] ? Number(match[3].length === 2 ? `20${match[3]}` : match[3]) : 2026;
  return new Date(Date.UTC(year, 6, day));
}

function extractTime(text) {
  const withoutDates = text.replace(/\b\d{1,2}[./]0?7(?:[./]\d{2,4})?\b/gu, " ");
  const match = withoutDates.match(/(?:^|\s)([0-2]?\d)[:.\s]([0-5]\d)(?=\s|мск|$|[-—])/iu);
  if (!match) return "";
  return `${String(Number(match[1])).padStart(2, "0")}:${match[2]}`;
}

function extractSubjects(text) {
  return subjectPatterns.filter(([regex]) => regex.test(text)).map(([, label]) => label).join(", ");
}

const rows = [];
for (const rawLine of source.split(/\r?\n/)) {
  const line = rawLine.trim();
  if (!line) continue;
  const p = normalizeParts(rawLine);
  if (!p.length || p.every((x) => /^КФУ$/iu.test(x))) continue;

  let fullName = p[0] || "";
  let login = "";
  let password = "";
  let university = "";
  let clientSource = "";
  let details = "";
  let note = "";

  if (p.length >= 6 && looksLikeLogin(p[2]) && !looksLikeLogin(p[1])) {
    // Блок КФУ: ФИО, специальность, логин, пароль, предмет, время/ответственный.
    university = "КФУ";
    login = p[2] || "";
    password = p[3] || "";
    details = [p[4], ...p.slice(5)].filter(Boolean).join(" — ");
    note = `Специальность: ${p[1]}`;
  } else {
    login = p[1] || "";
    password = p[2] || "";
    university = p[3] || "";
    clientSource = p[4] || "";
    details = p.slice(5).filter(Boolean).join(" | ") || (p.length < 6 ? p.slice(1).filter(Boolean).join(" | ") : "");
  }

  const date = extractDate(details);
  const time = extractTime(details);
  const subject = extractSubjects(details);
  const issues = [];
  if (!login) issues.push("нет логина");
  if (!password) issues.push("нет пароля");
  if (!university) issues.push("нет вуза");
  if (!subject) issues.push("уточнить предмет");
  if (!date) issues.push("уточнить дату");
  if (!time) issues.push("уточнить время");
  if ((university.match(/[,/\\]/g) || []).length || subject.includes(",")) issues.push("возможно, разделить на несколько экзаменов");
  if (note) issues.unshift(note);

  rows.push([
    rows.length + 1,
    "",
    fullName,
    login,
    password,
    university,
    clientSource,
    subject,
    date || "",
    time,
    "Asia/Ashgabat",
    "",
    "",
    details,
    issues.join("; "),
  ]);
}

const workbook = Workbook.create();
const sheet = workbook.worksheets.add("Экзамены");
const guide = workbook.worksheets.add("Инструкция");
sheet.showGridLines = false;
guide.showGridLines = false;

sheet.mergeCells("A1:O1");
sheet.getRange("A1").values = [["ExamSL — подготовка экзаменов к импорту"]];
sheet.getRange("A1:O1").format = {
  fill: "#2F4938",
  font: { bold: true, color: "#FFF9EC", size: 16 },
  verticalAlignment: "center",
};
sheet.getRange("A1:O1").format.rowHeight = 34;
sheet.mergeCells("A2:O2");
sheet.getRange("A2").values = [["Проверьте строки со статусом «УТОЧНИТЬ». Если в исходной строке несколько вузов или предметов — скопируйте строку и оставьте один экзамен в каждой строке."]];
sheet.getRange("A2:O2").format = { fill: "#F2E8D5", font: { color: "#594A36", italic: true }, wrapText: true };
sheet.getRange("A2:O2").format.rowHeight = 32;

const headers = [["№", "Статус", "ФИО", "Логин", "Пароль", "Вуз", "Откуда", "Предмет", "Дата экзамена", "Время", "Часовой пояс", "Контакты", "Ссылка на экзамен", "Исходное расписание", "Что проверить / примечание"]];
sheet.getRange("A3:O3").values = headers;
sheet.getRange(`A4:O${rows.length + 3}`).values = rows;
for (let r = 4; r <= rows.length + 3; r++) {
  sheet.getRange(`B${r}`).formulas = [[`=IF(AND(C${r}<>"",D${r}<>"",E${r}<>"",F${r}<>"",H${r}<>"",I${r}<>"",J${r}<>"",O${r}=""),"ГОТОВО","УТОЧНИТЬ")`]];
}

const table = sheet.tables.add(`A3:O${rows.length + 3}`, true, "ExamImportTable");
table.style = "TableStyleMedium4";
table.showFilterButton = true;
sheet.freezePanes.freezeRows(3);
sheet.freezePanes.freezeColumns(2);

sheet.getRange(`I4:I${rows.length + 3}`).format.numberFormat = "dd.mm.yyyy";
sheet.getRange(`A3:O${rows.length + 3}`).format.verticalAlignment = "top";
sheet.getRange(`C4:O${rows.length + 3}`).format.wrapText = true;
sheet.getRange(`K4:K${rows.length + 3}`).dataValidation = { rule: { type: "list", values: ["Asia/Ashgabat", "Europe/Moscow"] } };
sheet.getRange(`B4:B${rows.length + 3}`).conditionalFormats.add("containsText", { text: "УТОЧНИТЬ", format: { fill: "#FADBD8", font: { color: "#9E2A2B", bold: true } } });
sheet.getRange(`B4:B${rows.length + 3}`).conditionalFormats.add("containsText", { text: "ГОТОВО", format: { fill: "#DDEBDD", font: { color: "#235C37", bold: true } } });
sheet.getRange(`O4:O${rows.length + 3}`).conditionalFormats.add("notContainsBlanks", { format: { fill: "#FFF2CC" } });

const widths = [7, 15, 28, 28, 22, 18, 16, 25, 15, 11, 18, 22, 28, 48, 44];
widths.forEach((width, idx) => { sheet.getRangeByIndexes(0, idx, rows.length + 3, 1).format.columnWidth = width; });
sheet.getRange(`A4:B${rows.length + 3}`).format.horizontalAlignment = "center";
sheet.getRange(`I4:K${rows.length + 3}`).format.horizontalAlignment = "center";

guide.mergeCells("A1:F1");
guide.getRange("A1").values = [["Как подготовить файл для автоматического импорта"]];
guide.getRange("A1:F1").format = { fill: "#2F4938", font: { bold: true, color: "#FFF9EC", size: 15 } };
guide.getRange("A3:F10").values = [
  ["Шаг", "Что сделать", "Обязательно", "Пример", "Правило", "Примечание"],
  [1, "Одна строка = один экзамен", "Да", "Один клиент и один предмет", "Несколько предметов разделить", "Можно дублировать ФИО/логин"],
  [2, "Заполнить ФИО, вуз и предмет", "Да", "Иван Иванов / КФУ / Математика", "Без сокращений желательно", ""],
  [3, "Указать дату", "Да", "21.07.2026", "Реальная дата Excel", "Не писать «21-го»"],
  [4, "Указать одно время начала", "Да", "09:00", "Формат ЧЧ:ММ", "Интервал оставить в примечании"],
  [5, "Проверить часовой пояс", "Да", "Asia/Ashgabat", "МСК при необходимости выбрать отдельно", "ExamSL хранит время Asia/Ashgabat"],
  [6, "Добавить контакты и ссылку", "Нет", "Telegram / https://...", "Можно оставить пустыми", ""],
  [7, "Отфильтровать статус ГОТОВО", "Да", "ГОТОВО", "Перед отправкой не должно быть УТОЧНИТЬ", "Статус считается автоматически"],
];
guide.getRange("A3:F3").format = { fill: "#B88A44", font: { bold: true, color: "#FFFFFF" } };
guide.getRange("A3:F10").format.wrapText = true;
guide.getRange("A3:F10").format.borders = { preset: "inside", style: "thin", color: "#DDD2BE" };
[8, 35, 15, 30, 34, 38].forEach((width, idx) => { guide.getRangeByIndexes(0, idx, 10, 1).format.columnWidth = width; });
guide.getRange("A1:F10").format.verticalAlignment = "top";
guide.freezePanes.freezeRows(3);

await fs.mkdir(outputDir, { recursive: true });
const preview1 = await workbook.render({ sheetName: "Экзамены", range: "A1:O18", scale: 1, format: "png" });
await fs.writeFile(`${outputDir}/preview_exams.png`, new Uint8Array(await preview1.arrayBuffer()));
const preview2 = await workbook.render({ sheetName: "Инструкция", range: "A1:F10", scale: 1.2, format: "png" });
await fs.writeFile(`${outputDir}/preview_guide.png`, new Uint8Array(await preview2.arrayBuffer()));

console.log((await workbook.inspect({ kind: "table", range: "Экзамены!A1:O12", include: "values,formulas", tableMaxRows: 12, tableMaxCols: 15 })).ndjson);
console.log((await workbook.inspect({ kind: "match", searchTerm: "#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A", options: { useRegex: true, maxResults: 50 }, summary: "formula errors" })).ndjson);

const xlsx = await SpreadsheetFile.exportXlsx(workbook);
await xlsx.save(`${outputDir}/ExamSL_данные_для_проверки.xlsx`);
console.log(`ROWS=${rows.length}`);
