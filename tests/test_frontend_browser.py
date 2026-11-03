"""Verificacao opcional no Edge headless. Requer playwright e Edge instalado."""
import importlib.util
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time
import unittest
import urllib.request

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
EDGE = Path('C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe')


@unittest.skipUnless(importlib.util.find_spec('playwright') and EDGE.exists(), 'Playwright/Edge indisponivel')
class TestFrontendBrowser(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from playwright.sync_api import sync_playwright
        with socket.socket() as s:
            s.bind(('127.0.0.1', 0)); port = s.getsockname()[1]
        cls.base = f'http://127.0.0.1:{port}'
        env = os.environ.copy()
        env['TCC_MODEL_DIR'] = str(ROOT/'artifacts/rl_20261014T100407101829_b83773b9')
        cls.log = tempfile.TemporaryFile()
        cls.server = subprocess.Popen([sys.executable, '-B', '-m', 'uvicorn', 'api.main:app', '--host', '127.0.0.1', '--port', str(port)], cwd=ROOT, env=env, stdout=cls.log, stderr=cls.log)
        cls.addClassCleanup(cls.stop_server)
        for _ in range(80):
            try:
                urllib.request.urlopen(cls.base+'/health', timeout=1).close(); break
            except OSError:
                if cls.server.poll() is not None: raise RuntimeError('Servidor encerrou')
                time.sleep(.25)
        else: raise RuntimeError('Servidor nao iniciou')
        cls.playwright = sync_playwright().start()
        cls.addClassCleanup(cls.playwright.stop)
        cls.browser = cls.playwright.chromium.launch(executable_path=str(EDGE), headless=True)
        cls.addClassCleanup(cls.browser.close)

    @classmethod
    def stop_server(cls):
        cls.server.terminate(); cls.server.wait(timeout=10); cls.log.close()

    def setUp(self):
        self.context = self.browser.new_context(viewport={'width':1280, 'height':900})
        self.addCleanup(self.context.close)
        self.page = self.context.new_page()
        self.errors = []
        self.page.on('pageerror', lambda err: self.errors.append(str(err)))

    def test_search_pagination_navigation_real_calculation(self):
        from playwright.sync_api import expect
        page = self.page
        page.goto(self.base+'/frontend/')
        expect(page.locator('#patientsTableBody tr')).to_have_count(10)
        page.locator('#searchPatient').fill('DEMO0')
        page.locator('#patientFilters button[type=submit]').click()
        expect(page.locator('#patientsTableBody tr').first).to_contain_text('DEMO001')
        page.locator('#searchPatient').fill('DEMO01')
        page.locator('#patientFilters button[type=submit]').click()
        expect(page.locator('#patientsTableBody tr')).to_have_count(10)
        expect(page.locator('#patientsTableBody tr').first).to_contain_text('DEMO010')
        expect(page.locator('#pagination button[aria-current]')).to_have_text('1')
        expect(page.get_by_role('button', name='»', exact=True)).to_be_disabled()
        page.locator('#searchPatient').fill('DEMO001')
        page.locator('#patientFilters button[type=submit]').click()
        page.get_by_role('link', name='Realizar avaliação de DEMO001', exact=True).click()
        expect(page.locator('#patientIdentity')).to_contain_text('DEMO001')
        expect(page.locator('#parameters dt')).to_have_count(11)
        self.assertEqual(page.locator('input, textarea, select').count(), 0)
        with page.expect_response(lambda response: response.url.endswith('/predict')) as event:
            page.get_by_role('button', name='Calcular probabilidade', exact=True).click()
        response = event.value
        self.assertEqual(response.status, 200)
        body = response.request.post_data_json
        self.assertEqual(len(body), 11)
        self.assertNotIn('patient_id', body)
        self.assertNotIn('data_avaliacao', body)
        p = response.json()['probabilidade']
        expected = f'{100*p:.2f}'.replace('.', ',') + '%'
        expect(page.locator('#probability')).to_have_text(expected)
        expect(page.locator('#modelVersion')).to_have_text(response.json()['versao_modelo'])
        print('DEMO001 HTTP response:', json.dumps(response.json(), ensure_ascii=True))
        page.get_by_role('link', name='Voltar à listagem').click()
        expect(page.locator('#patientsTableBody tr')).to_have_count(10)
        expect(page.locator('#patientsTableBody tr').filter(has_text='DEMO001').locator('td').nth(2)).to_have_text(expected)
        expect(page.get_by_role('link', name='Ver resultado de DEMO001', exact=True)).to_be_visible()
        page.get_by_role('link', name='Ver resultado de DEMO001', exact=True).click()
        expect(page.locator('#probability')).to_have_text(expected)
        expect(page.get_by_role('button', name='Calcular novamente')).to_be_visible()
        self.assertFalse(self.errors)

    def test_failures_retry_unknown_patient_and_mobile(self):
        from playwright.sync_api import expect
        page = self.page
        page.route('**/demo/patients', lambda route: route.abort(), times=1)
        page.goto(self.base+'/frontend/')
        expect(page.locator('#retryLoad')).to_be_visible()
        page.locator('#retryLoad').click()
        expect(page.locator('#patientsTableBody tr')).to_have_count(10)
        page.goto(self.base+'/frontend/avaliacao.html?id=unknown')
        expect(page.locator('#evaluationStatus')).to_contain_text('não encontrado')
        page.set_viewport_size({'width':390, 'height':844})
        page.goto(self.base+'/frontend/avaliacao.html?id=DEMO001')
        expect(page.locator('#parameters dt')).to_have_count(11)
        self.assertEqual(page.locator('#parameters').evaluate('(el) => getComputedStyle(el).gridTemplateColumns.split(" ").length'), 2)
        self.assertTrue(page.evaluate('document.documentElement.scrollWidth <= window.innerWidth'))
        page.route('**/predict', lambda route: route.fulfill(status=503, content_type='application/json', body='{"detail":"unavailable"}'), times=1)
        page.locator('#calculate').click()
        expect(page.locator('#evaluationStatus')).to_contain_text('indisponível')
        expect(page.locator('#predictionResult')).to_be_hidden()
        page.get_by_role('button', name='Tentar novamente', exact=True).click()
        expect(page.locator('#predictionResult')).to_be_visible()
        self.assertTrue(page.evaluate('document.documentElement.scrollWidth <= window.innerWidth'))
        page.get_by_role('link', name='Voltar à listagem').click()
        expect(page.locator('#patientsTableBody tr')).to_have_count(10)
        self.assertTrue(page.evaluate('document.documentElement.scrollWidth <= window.innerWidth'))
        self.assertFalse(self.errors)


if __name__ == '__main__': unittest.main()
