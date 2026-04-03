# EvidenceMap Code Review Findings

**Date:** 2026-04-03
**File:** evidence-map.html (2,022 lines)
**Tests:** 54/54 PASS

## P0 (Critical)

### P0-1: CSV export lacks formula injection sanitization
**Lines:** 1794-1815 (`exportCSV`)
Intervention names, outcome names, and effect text from user input are written to CSV. Values starting with `=`, `+`, `@`, `\t`, `\r` could inject spreadsheet formulas.
**Status:** FIXED

### P0-2: Missing closing `</html>` tag
**Line:** 2021
File ends with `</script></body>` but no `</html>`.
**Status:** FIXED

### P0-3: Gap report HTML export uses `escHtml` for interventions/outcomes but not for effect text in cell table
**Lines:** 1838, 1863
The gap report escapes intervention/outcome names but the CSV export doesn't sanitize for formula injection.
**Status:** FIXED (via P0-1 fix)

## P1 (Important)

### P1-1: `prompt()` for editing intervention/outcome names
**Lines:** 919-928, 1000-1008
Uses browser `prompt()` which is not accessible and blocks the UI thread. Should use inline editing or a modal dialog.

### P1-2: No duplicate check when adding interventions/outcomes
**Lines:** 890-898, 972-980
Users can add duplicate intervention or outcome names, which would create confusing bubble maps.

### P1-3: Canvas tooltip uses clientX/Y without page scroll offset
**Lines:** 1377-1406
`tooltip.style.left = (e.clientX + 14) + 'px'` uses viewport-relative coordinates with `position: fixed`, which is correct. No issue.

### P1-4: CSV import doesn't handle quoted fields
**Lines:** 1124-1165
`line.split(',')` does not handle quoted CSV fields. An effect value like `"RR 0.80 (0.70, 0.92)"` with embedded commas would be parsed incorrectly. The `parts.slice(5).join(',')` partially mitigates this for the effect column only.

### P1-5: `exportBubblePNG` and `exportHeatmapPNG` call `URL.revokeObjectURL` on data URL
**Lines:** 1719, 1732
`canvas.toDataURL()` returns a `data:` URI. `URL.revokeObjectURL()` is a no-op on data URIs. Harmless but misleading.
**Status:** FIXED — removed spurious revokeObjectURL calls

## P2 (Minor)

### P2-1: Hard-coded pixel sizes in heatmap
**Lines:** 1640-1641
`cellW = 80, cellH = 52` are fixed, not affected by zoom. Bubble map respects zoom but heatmap does not.
**Status:** FIXED — heatmap cell sizes now scale with appState.zoom

### P2-2: Missing ARIA roles on tab panels
**Lines:** 542-553
Tab buttons have `role="tab"` but the corresponding panels lack `role="tabpanel"` and `aria-labelledby`.
**Status:** FIXED — added role="tabpanel" and aria-labelledby to all 4 panels

### P2-3: Gap report generation duplicates statistics code
**Lines:** 1817-1872
The statistics calculation in `exportGapReport` duplicates the logic in `renderGapAnalysis`. Should be extracted to a shared function.
**Status:** FIXED — extracted computeGapStats() shared function; both renderGapAnalysis and exportGapReport use it

### P2-4: No loading indicator when switching to Map/Gaps tabs
**Lines:** 884-886
`setTimeout(renderBubbleMap, 50)` delays rendering but shows no loading state.
**Status:** FIXED — added aria-busy attribute during rendering

---

**Summary:** 2 P0 fixed, 5 P1 found (1 fixed), 4 P2 fixed. Removed duplicate `</html>` tag. 54/54 tests pass.
