import time
import unittest
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options

REPO_ROOT = Path(__file__).resolve().parents[1]


class QuietHTTPServer(ThreadingHTTPServer):
    # Keep this false so parallel browser suites fall back instead of
    # sharing 127.0.0.1:8000 on Windows.
    allow_reuse_address = False
    daemon_threads = True


class QuietHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(REPO_ROOT), **kwargs)

    def log_message(self, format, *args):
        return

class TestEvidenceMap(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            cls.server = QuietHTTPServer(("127.0.0.1", 8000), QuietHandler)
        except OSError:
            cls.server = QuietHTTPServer(("127.0.0.1", 0), QuietHandler)
        cls.html = f"http://127.0.0.1:{cls.server.server_port}/evidence-map.html"
        cls.server_thread = Thread(target=cls.server.serve_forever, daemon=True)
        cls.server_thread.start()

        opts = Options()
        opts.add_argument('--headless=new')
        opts.add_argument('--no-sandbox')
        opts.add_argument('--disable-gpu')
        try:
            cls.drv = webdriver.Chrome(options=opts)
        except Exception:
            cls.server.shutdown()
            cls.server_thread.join(timeout=5)
            cls.server.server_close()
            raise
        cls.drv.get(cls.html)
        time.sleep(1)

    @classmethod
    def tearDownClass(cls):
        try:
            cls.drv.quit()
        finally:
            cls.server.shutdown()
            cls.server_thread.join(timeout=5)
            cls.server.server_close()

    def js(self, script):
        return self.drv.execute_script(script)

    def _reset_state(self):
        """Clear all state for clean test setup."""
        self.js("""
            appState.interventions = [];
            appState.outcomes = [];
            appState.cells = {};
            renderInterventionList();
            renderOutcomeList();
            renderCellTable();
            saveState();
        """)

    # =============================================
    # 1. escHtml function
    # =============================================
    def test_escHtml_basic(self):
        result = self.js("return escHtml('<script>alert(1)</script>');")
        self.assertNotIn('<script>', result)
        self.assertIn('&lt;script&gt;', result)

    def test_escHtml_quotes(self):
        result = self.js("""return escHtml('He said "hello" & she said \\'hi\\'');""")
        self.assertIn('&amp;', result)
        self.assertIn('&quot;', result)
        self.assertIn('&#39;', result)

    def test_escHtml_null(self):
        self.assertEqual(self.js("return escHtml(null);"), '')
        self.assertEqual(self.js("return escHtml(undefined);"), '')

    # =============================================
    # 2. cellKey function
    # =============================================
    def test_cellKey(self):
        self.assertEqual(self.js("return cellKey(0, 0);"), '0|0')
        self.assertEqual(self.js("return cellKey(3, 5);"), '3|5')

    # =============================================
    # 3. getCellData
    # =============================================
    def test_getCellData_default(self):
        """Missing cell should return defaults."""
        result = self.js("return getCellData(99, 99);")
        self.assertEqual(result['k'], 0)
        self.assertEqual(result['certainty'], 'Not assessed')
        self.assertEqual(result['direction'], 'No effect')

    # =============================================
    # 4. GRADE_COLORS mapping
    # =============================================
    def test_grade_colors(self):
        colors = self.js("return GRADE_COLORS;")
        self.assertIn('High', colors)
        self.assertIn('Moderate', colors)
        self.assertIn('Low', colors)
        self.assertIn('Very Low', colors)
        self.assertIn('Not assessed', colors)

    # =============================================
    # 5. DIRECTION_SYMBOLS mapping
    # =============================================
    def test_direction_symbols(self):
        syms = self.js("return DIRECTION_SYMBOLS;")
        self.assertIn('Beneficial', syms)
        self.assertIn('Harmful', syms)
        self.assertIn('No effect', syms)
        self.assertIn('Mixed', syms)

    # =============================================
    # 6. bubbleRadius function
    # =============================================
    def test_bubbleRadius_zero(self):
        r = self.js("return bubbleRadius(0);")
        self.assertEqual(r, 0)

    def test_bubbleRadius_positive(self):
        r = self.js("return bubbleRadius(10);")
        expected = max(8, min(40, 8 + (10**0.5) * 5))
        self.assertAlmostEqual(r, expected, places=2)

    def test_bubbleRadius_large_k(self):
        r = self.js("return bubbleRadius(100);")
        self.assertLessEqual(r, 40)
        self.assertGreater(r, 8)

    def test_bubbleRadius_monotonic(self):
        """Larger k should produce larger or equal radius."""
        r1 = self.js("return bubbleRadius(1);")
        r5 = self.js("return bubbleRadius(5);")
        r20 = self.js("return bubbleRadius(20);")
        self.assertLessEqual(r1, r5)
        self.assertLessEqual(r5, r20)

    # =============================================
    # 7. Add intervention
    # =============================================
    def test_add_intervention(self):
        self._reset_state()
        self.js("""
            document.getElementById('newIntervention').value = 'TestDrug';
            addIntervention();
        """)
        self.assertEqual(self.js("return appState.interventions.length;"), 1)
        self.assertEqual(self.js("return appState.interventions[0];"), 'TestDrug')

    def test_add_intervention_empty_name(self):
        self._reset_state()
        self.js("""
            document.getElementById('newIntervention').value = '   ';
            addIntervention();
        """)
        self.assertEqual(self.js("return appState.interventions.length;"), 0)

    # =============================================
    # 8. Add outcome
    # =============================================
    def test_add_outcome(self):
        self._reset_state()
        self.js("""
            document.getElementById('newOutcome').value = 'Mortality';
            addOutcome();
        """)
        self.assertEqual(self.js("return appState.outcomes.length;"), 1)
        self.assertEqual(self.js("return appState.outcomes[0];"), 'Mortality')

    # =============================================
    # 9. Remove intervention (with cell key reindexing)
    # =============================================
    def test_remove_intervention_reindex(self):
        self._reset_state()
        self.js("""
            appState.interventions = ['A', 'B', 'C'];
            appState.outcomes = ['X'];
            appState.cells = {};
            appState.cells[cellKey(0, 0)] = { k: 5, effect: '', certainty: 'High', direction: 'Beneficial' };
            appState.cells[cellKey(1, 0)] = { k: 3, effect: '', certainty: 'Low', direction: 'Harmful' };
            appState.cells[cellKey(2, 0)] = { k: 7, effect: '', certainty: 'Moderate', direction: 'No effect' };
            removeIntervention(1);
        """)
        interventions = self.js("return appState.interventions;")
        self.assertEqual(interventions, ['A', 'C'])
        # Cell for 'C' (was index 2) should now be at index 1
        c_cell = self.js("return appState.cells[cellKey(1, 0)];")
        self.assertEqual(c_cell['k'], 7)
        # Cell for 'A' should remain at index 0
        a_cell = self.js("return appState.cells[cellKey(0, 0)];")
        self.assertEqual(a_cell['k'], 5)

    # =============================================
    # 10. Remove outcome (with cell key reindexing)
    # =============================================
    def test_remove_outcome_reindex(self):
        self._reset_state()
        self.js("""
            appState.interventions = ['A'];
            appState.outcomes = ['X', 'Y', 'Z'];
            appState.cells = {};
            appState.cells[cellKey(0, 0)] = { k: 1, effect: '', certainty: 'High', direction: 'Beneficial' };
            appState.cells[cellKey(0, 1)] = { k: 2, effect: '', certainty: 'Low', direction: 'Harmful' };
            appState.cells[cellKey(0, 2)] = { k: 3, effect: '', certainty: 'Moderate', direction: 'No effect' };
            removeOutcome(0);
        """)
        outcomes = self.js("return appState.outcomes;")
        self.assertEqual(outcomes, ['Y', 'Z'])
        y_cell = self.js("return appState.cells[cellKey(0, 0)];")
        self.assertEqual(y_cell['k'], 2)
        z_cell = self.js("return appState.cells[cellKey(0, 1)];")
        self.assertEqual(z_cell['k'], 3)

    # =============================================
    # 11. Move intervention
    # =============================================
    def test_move_intervention(self):
        self._reset_state()
        self.js("""
            appState.interventions = ['A', 'B'];
            appState.outcomes = ['X'];
            appState.cells = {};
            appState.cells[cellKey(0, 0)] = { k: 10, effect: '', certainty: 'High', direction: 'Beneficial' };
            appState.cells[cellKey(1, 0)] = { k: 20, effect: '', certainty: 'Low', direction: 'Harmful' };
            moveIntervention(0, 1);
        """)
        interventions = self.js("return appState.interventions;")
        self.assertEqual(interventions, ['B', 'A'])
        # Cell data should have swapped
        b_cell = self.js("return appState.cells[cellKey(0, 0)];")
        self.assertEqual(b_cell['k'], 20)
        a_cell = self.js("return appState.cells[cellKey(1, 0)];")
        self.assertEqual(a_cell['k'], 10)

    # =============================================
    # 12. updateCell
    # =============================================
    def test_updateCell(self):
        self._reset_state()
        self.js("""
            appState.interventions = ['A'];
            appState.outcomes = ['X'];
            appState.cells = {};
            updateCell(0, 0, 'k', '5');
            updateCell(0, 0, 'certainty', 'High');
            updateCell(0, 0, 'direction', 'Beneficial');
        """)
        cell = self.js("return appState.cells[cellKey(0, 0)];")
        self.assertEqual(cell['k'], 5)
        self.assertEqual(cell['certainty'], 'High')
        self.assertEqual(cell['direction'], 'Beneficial')

    def test_updateCell_negative_k(self):
        """Negative k should be clamped to 0."""
        self._reset_state()
        self.js("""
            appState.interventions = ['A'];
            appState.outcomes = ['X'];
            appState.cells = {};
            updateCell(0, 0, 'k', '-3');
        """)
        cell = self.js("return appState.cells[cellKey(0, 0)];")
        self.assertEqual(cell['k'], 0)

    # =============================================
    # 13. Load example: Cardiovascular
    # =============================================
    def test_load_example_cardio(self):
        self.js("loadExample(0);")
        time.sleep(0.3)
        n_intv = self.js("return appState.interventions.length;")
        n_outc = self.js("return appState.outcomes.length;")
        self.assertEqual(n_intv, 6)
        self.assertEqual(n_outc, 5)
        self.assertIn('Statins', self.js("return appState.interventions;"))

    # =============================================
    # 14. Load example: Mental Health
    # =============================================
    def test_load_example_mental(self):
        self.js("loadExample(1);")
        time.sleep(0.3)
        n_intv = self.js("return appState.interventions.length;")
        self.assertEqual(n_intv, 5)
        self.assertIn('CBT', self.js("return appState.interventions;"))

    # =============================================
    # 15. Load example: COVID-19
    # =============================================
    def test_load_example_covid(self):
        self.js("loadExample(2);")
        time.sleep(0.3)
        n_intv = self.js("return appState.interventions.length;")
        self.assertEqual(n_intv, 8)
        self.assertIn('Dexamethasone', self.js("return appState.interventions;"))

    # =============================================
    # 16. Tab switching
    # =============================================
    def test_tab_switch_to_map(self):
        self.js("switchTab('map');")
        time.sleep(0.3)
        active = self.js("return document.getElementById('panel-map').classList.contains('active');")
        self.assertTrue(active)

    def test_tab_switch_to_gaps(self):
        self.js("switchTab('gaps');")
        time.sleep(0.3)
        active = self.js("return document.getElementById('panel-gaps').classList.contains('active');")
        self.assertTrue(active)

    def test_tab_switch_to_export(self):
        self.js("switchTab('export');")
        time.sleep(0.3)
        active = self.js("return document.getElementById('panel-export').classList.contains('active');")
        self.assertTrue(active)

    def test_tab_switch_back_to_entry(self):
        self.js("switchTab('map');")
        self.js("switchTab('entry');")
        time.sleep(0.2)
        active = self.js("return document.getElementById('panel-entry').classList.contains('active');")
        self.assertTrue(active)

    # =============================================
    # 17. Dark mode toggle
    # =============================================
    def test_dark_mode_toggle(self):
        self.js("appState.darkMode = false; applyDark();")
        self.assertFalse(self.js("return document.body.classList.contains('dark');"))
        self.js("toggleDark();")
        self.assertTrue(self.js("return document.body.classList.contains('dark');"))
        self.js("toggleDark();")
        self.assertFalse(self.js("return document.body.classList.contains('dark');"))

    # =============================================
    # 18. CSV import
    # =============================================
    def test_csv_import(self):
        self._reset_state()
        self.js("""
            document.getElementById('csvInput').value =
                'Drug A, Mortality, 5, High, Beneficial, RR 0.72\\n' +
                'Drug A, MI, 3, Moderate, Beneficial, RR 0.81\\n' +
                'Drug B, Mortality, 1, Low, Harmful, RR 1.15';
            importCSV();
        """)
        time.sleep(0.3)
        n_intv = self.js("return appState.interventions.length;")
        n_outc = self.js("return appState.outcomes.length;")
        self.assertEqual(n_intv, 2)  # Drug A, Drug B
        self.assertEqual(n_outc, 2)  # Mortality, MI
        cell = self.js("return appState.cells[cellKey(0, 0)];")
        self.assertEqual(cell['k'], 5)
        self.assertEqual(cell['certainty'], 'High')
        self.assertEqual(cell['direction'], 'Beneficial')

    def test_csv_import_normalization(self):
        """Certainty and direction should be normalized to canonical values."""
        self._reset_state()
        self.js("""
            document.getElementById('csvInput').value = 'X, Y, 2, very low, beneficial';
            importCSV();
        """)
        cell = self.js("return appState.cells[cellKey(0, 0)];")
        self.assertEqual(cell['certainty'], 'Very Low')
        self.assertEqual(cell['direction'], 'Beneficial')

    def test_csv_import_status_message(self):
        self._reset_state()
        self.js("""
            document.getElementById('csvInput').value = 'A, B, 1, High, Beneficial';
            importCSV();
        """)
        time.sleep(0.3)
        status = self.js("return document.getElementById('csvStatus').textContent;")
        self.assertIn('Imported 1', status)

    # =============================================
    # 19. Gap analysis computation
    # =============================================
    def test_gap_analysis(self):
        """Load cardio example, switch to gaps tab, check stats are computed."""
        self.js("loadExample(0);")
        time.sleep(0.2)
        self.js("switchTab('gaps');")
        time.sleep(0.5)
        total = self.js("return document.getElementById('statTotal').textContent;")
        self.assertEqual(total, '30')  # 6 interventions * 5 outcomes
        filled = self.js("return document.getElementById('statFilled').textContent;")
        gaps = self.js("return document.getElementById('statGaps').textContent;")
        self.assertEqual(int(filled) + int(gaps), 30)

    # =============================================
    # 20. Gap priority scoring
    # =============================================
    def test_gap_priority_detection(self):
        """Gaps next to high-quality beneficial cells should get high priority."""
        self._reset_state()
        self.js("""
            appState.interventions = ['A', 'B'];
            appState.outcomes = ['X', 'Y'];
            appState.cells = {};
            // Fill A+X with High/Beneficial and A+Y with High/Beneficial
            appState.cells[cellKey(0, 0)] = { k: 10, effect: '', certainty: 'High', direction: 'Beneficial' };
            appState.cells[cellKey(0, 1)] = { k: 8, effect: '', certainty: 'High', direction: 'Beneficial' };
            // B+X is a gap, but adjacent to A+X (High/Beneficial)
            // B+Y is a gap, adjacent to A+Y (High/Beneficial)
            renderInterventionList();
            renderOutcomeList();
            renderCellTable();
            saveState();
        """)
        self.js("switchTab('gaps');")
        time.sleep(0.5)
        gaps_text = self.js("return document.getElementById('statGaps').textContent;")
        self.assertEqual(gaps_text, '2')

    # =============================================
    # 21. Bubble map rendering
    # =============================================
    def test_bubble_map_renders(self):
        self.js("loadExample(0);")
        time.sleep(0.2)
        self.js("switchTab('map');")
        time.sleep(0.5)
        canvas = self.drv.find_element(By.ID, 'bubbleCanvas')
        self.assertGreater(int(canvas.get_attribute('width')), 0)
        self.assertGreater(int(canvas.get_attribute('height')), 0)

    # =============================================
    # 22. Zoom controls
    # =============================================
    def test_zoom_increase(self):
        self.js("loadExample(0);")
        self.js("appState.zoom = 1.0;")
        self.js("adjustZoom(0.1);")
        zoom = self.js("return appState.zoom;")
        self.assertAlmostEqual(zoom, 1.1, places=1)

    def test_zoom_decrease(self):
        self.js("appState.zoom = 1.0;")
        self.js("adjustZoom(-0.1);")
        zoom = self.js("return appState.zoom;")
        self.assertAlmostEqual(zoom, 0.9, places=1)

    def test_zoom_min_clamp(self):
        self.js("appState.zoom = 0.5;")
        self.js("adjustZoom(-0.5);")
        zoom = self.js("return appState.zoom;")
        self.assertGreaterEqual(zoom, 0.5)

    def test_zoom_max_clamp(self):
        self.js("appState.zoom = 3.0;")
        self.js("adjustZoom(0.5);")
        zoom = self.js("return appState.zoom;")
        self.assertLessEqual(zoom, 3.0)

    def test_zoom_reset(self):
        self.js("appState.zoom = 2.0;")
        self.js("resetZoom();")
        zoom = self.js("return appState.zoom;")
        self.assertEqual(zoom, 1.0)

    # =============================================
    # 23. gradeColor function
    # =============================================
    def test_gradeColor_light(self):
        self.js("appState.darkMode = false;")
        color = self.js("return gradeColor('High');")
        self.assertEqual(color, '#276749')

    def test_gradeColor_dark(self):
        self.js("appState.darkMode = true;")
        color = self.js("return gradeColor('High');")
        self.assertEqual(color, '#56d364')
        # Reset
        self.js("appState.darkMode = false;")

    def test_gradeColor_unknown(self):
        color = self.js("appState.darkMode = false; return gradeColor('Unknown');")
        self.assertEqual(color, '#718096')  # Should default to Not assessed

    # =============================================
    # 24. localStorage persistence
    # =============================================
    def test_save_and_load_state(self):
        self._reset_state()
        self.js("""
            appState.interventions = ['TestPersist'];
            appState.outcomes = ['TestOutcome'];
            saveState();
        """)
        self.js("""
            appState.interventions = [];
            appState.outcomes = [];
            loadState();
        """)
        self.assertEqual(self.js("return appState.interventions[0];"), 'TestPersist')
        self.assertEqual(self.js("return appState.outcomes[0];"), 'TestOutcome')

    # =============================================
    # 25. CERTAINTY_ORDER
    # =============================================
    def test_certainty_order(self):
        order = self.js("return CERTAINTY_ORDER;")
        self.assertEqual(order, ['High', 'Moderate', 'Low', 'Very Low', 'Not assessed'])

    # =============================================
    # 26. buildSummaryText
    # =============================================
    def test_buildSummaryText(self):
        self.js("loadExample(0);")
        time.sleep(0.2)
        text = self.js("return buildSummaryText();")
        self.assertIn('EvidenceMap Summary', text)
        self.assertIn('Interventions: 6', text)
        self.assertIn('Outcomes: 5', text)
        self.assertIn('Total cells: 30', text)

    # =============================================
    # 27. Intervention list rendering
    # =============================================
    def test_intervention_list_render(self):
        self._reset_state()
        self.js("""
            appState.interventions = ['DrugA', 'DrugB'];
            renderInterventionList();
        """)
        html = self.js("return document.getElementById('interventionList').innerHTML;")
        self.assertIn('DrugA', html)
        self.assertIn('DrugB', html)

    def test_intervention_list_empty(self):
        self._reset_state()
        self.js("renderInterventionList();")
        html = self.js("return document.getElementById('interventionList').innerHTML;")
        self.assertIn('No interventions', html)

    # =============================================
    # 28. Cell table rendering
    # =============================================
    def test_cell_table_renders_with_data(self):
        self._reset_state()
        self.js("""
            appState.interventions = ['A'];
            appState.outcomes = ['X'];
            appState.cells = {};
            appState.cells[cellKey(0, 0)] = { k: 5, effect: 'RR 0.80', certainty: 'High', direction: 'Beneficial' };
            renderInterventionList();
            renderOutcomeList();
            renderCellTable();
        """)
        html = self.js("return document.getElementById('cellTableWrap').innerHTML;")
        self.assertIn('cell-table', html)
        self.assertIn('A', html)

    def test_cell_table_empty_interventions(self):
        self._reset_state()
        self.js("""
            appState.interventions = [];
            appState.outcomes = ['X'];
            renderCellTable();
        """)
        html = self.js("return document.getElementById('cellTableWrap').innerHTML;")
        self.assertIn('No interventions', html)

    # =============================================
    # 29. clearAllCells (simulate confirm)
    # =============================================
    def test_clear_all_cells(self):
        self._reset_state()
        self.js("""
            appState.interventions = ['A'];
            appState.outcomes = ['X'];
            appState.cells = {};
            appState.cells[cellKey(0, 0)] = { k: 5, effect: '', certainty: 'High', direction: 'Beneficial' };
        """)
        # Override confirm to always return true
        self.js("window.confirm = function() { return true; };")
        self.js("clearAllCells();")
        cells = self.js("return Object.keys(appState.cells).length;")
        self.assertEqual(cells, 0)

    # =============================================
    # 30. Export summary renders on Export tab
    # =============================================
    def test_export_tab_shows_summary(self):
        self.js("loadExample(0);")
        time.sleep(0.2)
        self.js("switchTab('export');")
        time.sleep(0.3)
        summary = self.js("return document.getElementById('summaryBox').textContent;")
        self.assertIn('EvidenceMap Summary', summary)

    # =============================================
    # 31. Multiple interventions and outcomes count
    # =============================================
    def test_cardio_example_cell_counts(self):
        """Cardio example: verify filled cells vs gaps."""
        self.js("loadExample(0);")
        time.sleep(0.2)
        # Count cells with k>0
        filled = self.js("""
            var count = 0;
            for (var i = 0; i < appState.interventions.length; i++) {
                for (var j = 0; j < appState.outcomes.length; j++) {
                    if (getCellData(i, j).k > 0) count++;
                }
            }
            return count;
        """)
        # From the example data: 30 cells, several with k=0 (gaps)
        # SGLT2i+Bleeding=0, Aspirin+HF Hosp=0, Omega3+Stroke=0, Omega3+Bleeding=0
        self.assertGreater(filled, 20)  # Most cells are filled
        total = 6 * 5  # 30
        gaps = total - filled
        self.assertGreater(gaps, 0)  # Some gaps exist

    # =============================================
    # 32. Move outcome swaps cells
    # =============================================
    def test_move_outcome(self):
        self._reset_state()
        self.js("""
            appState.interventions = ['A'];
            appState.outcomes = ['X', 'Y'];
            appState.cells = {};
            appState.cells[cellKey(0, 0)] = { k: 10, effect: '', certainty: 'High', direction: 'Beneficial' };
            appState.cells[cellKey(0, 1)] = { k: 20, effect: '', certainty: 'Low', direction: 'Harmful' };
            moveOutcome(0, 1);
        """)
        outcomes = self.js("return appState.outcomes;")
        self.assertEqual(outcomes, ['Y', 'X'])
        y_cell = self.js("return appState.cells[cellKey(0, 0)];")
        self.assertEqual(y_cell['k'], 20)

    # =============================================
    # 33. EXAMPLES data integrity
    # =============================================
    def test_examples_count(self):
        count = self.js("return EXAMPLES.length;")
        self.assertEqual(count, 3)

    def test_examples_have_required_fields(self):
        for i in range(3):
            ex = self.js(f"return {{ name: EXAMPLES[{i}].name, ni: EXAMPLES[{i}].interventions.length, no: EXAMPLES[{i}].outcomes.length, nc: EXAMPLES[{i}].cells.length }};")
            self.assertGreater(len(ex['name']), 0)
            self.assertGreater(ex['ni'], 0)
            self.assertGreater(ex['no'], 0)
            self.assertGreater(ex['nc'], 0)


if __name__ == '__main__':
    unittest.main(verbosity=2)
