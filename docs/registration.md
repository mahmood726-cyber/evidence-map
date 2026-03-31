# EvidenceMap — Protocol Registration

## Registration Details

| Field | Value |
|-------|-------|
| **Registration ID** | EVM-2026-001 |
| **Tool name** | EvidenceMap |
| **Version** | v1.0 |
| **Registration date** | 2026-03-31 |
| **Registered by** | Mahmood Alhusseini |
| **Affiliation** | Independent Clinical Research Unit, London, UK |

## Tool Description

EvidenceMap is a free, browser-based evidence gap map generator. It produces:

- GRADE-colored bubble charts (bubble area proportional to study count k)
- Heatmaps (cell intensity proportional to k)
- Gap priority tables (composite priority score 0–100)
- CSV import/export; PNG/HTML export

No installation required. Single HTML file. MIT licence.

## URLs

- **Live tool**: https://mahmood726-cyber.github.io/evidence-map/
- **Source code**: https://github.com/mahmood726-cyber/evidence-map
- **Protocol paper**: https://mahmood726-cyber.github.io/evidence-map/docs/protocol.html
- **Results paper**: https://mahmood726-cyber.github.io/evidence-map/docs/results.html

## Novel Features Registered

1. Bubble sizing by study count k (square-root area scaling)
2. GRADE certainty color palette (5-level, WCAG AA compliant)
3. Direction arrows overlay (Beneficial/Harmful/No effect/Mixed/Unknown)
4. Automated gap priority ranking (composite score formula)

## Safety Verification

All pre-ship safety checks passed (div balance, script integrity, function uniqueness,
ID uniqueness, localStorage key uniqueness, WCAG contrast).

## Citation

Alhusseini M. EvidenceMap: A Browser-Based Evidence Gap Map Generator — Protocol.
E156 Micro-Paper EVM-2026-001, 2026.
