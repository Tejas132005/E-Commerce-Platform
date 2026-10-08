"""Shared layout (logo header, design system) is present on every app page."""
import re
from pathlib import Path

from django.conf import settings
from django.test import TestCase

from store.tests.helpers import make_customer, make_owner, make_product, make_invoice
from datetime import date

TEMPLATES = Path(settings.BASE_DIR) / 'templates'
EXCLUDED = {'invoice_template.html'}  # printed GST invoice / PDF source stays as-is


class LayoutTemplateTests(TestCase):
    def test_every_non_empty_page_uses_shared_layout(self):
        for path in TEMPLATES.glob('*.html'):
            if path.name in EXCLUDED or path.stat().st_size == 0:
                continue
            text = path.read_text(encoding='utf-8')
            with self.subTest(page=path.name):
                self.assertIn("partials/app_header.html", text)
                self.assertIn("partials/head_end.html", text)
                self.assertRegex(text, r'<body[^>]*class="ix\b')
                self.assertIn("partials/body_end.html", text)

    def test_bootstrap_js_loaded_exactly_once_per_page(self):
        for path in TEMPLATES.glob('*.html'):
            if path.name in EXCLUDED or path.stat().st_size == 0:
                continue
            text = path.read_text(encoding='utf-8')
            own = len(re.findall(r'bootstrap(?:\.bundle)?(?:\.min)?\.js', text))
            shared = 'ix_load_bootstrap=True' in text
            with self.subTest(page=path.name):
                self.assertEqual(own + int(shared), 1)


class LayoutRenderTests(TestCase):
    def setUp(self):
        self.owner = make_owner()
        make_customer(self.owner)
        make_customer(self.owner, phone='8000000002', name='Suresh')

    def test_header_shows_wordmark_and_no_image(self):
        resp = self.client.get('/')
        html = resp.content.decode()
        header = html[html.index('<header class="ix-header">'):html.index('</header>')]
        self.assertIn('InvoxiaGST', re.sub(r'<[^>]+>', '', header))
        self.assertNotIn('<img', header)

    def test_no_logo_image_referenced_anywhere(self):
        for path in TEMPLATES.rglob('*.html'):
            with self.subTest(file=path.name):
                self.assertNotIn('InvoxiaGST_Logo', path.read_text(encoding='utf-8'))

    def test_owner_pages_show_menu_with_customer_count(self):
        self.client.force_login(self.owner)
        for url in ['/', '/store/sales-dashboard/', '/store/manage/products/', '/bank/']:
            with self.subTest(url=url):
                resp = self.client.get(url)
                self.assertEqual(resp.status_code, 200)
                self.assertContains(resp, 'id="ixOwnerMenu"')
                self.assertContains(resp, 'class="count js-customer-count">2</span>', html=False)
                self.assertContains(resp, '<style id="ix-styles">')
                self.assertNotContains(resp, '/static/css/')

    def test_public_pages_render_with_header(self):
        for url in ['/accounts/login/', '/accounts/register/', '/core/about/', f'/store/{self.owner.username}/login/']:
            with self.subTest(url=url):
                resp = self.client.get(url)
                self.assertEqual(resp.status_code, 200)
                self.assertContains(resp, 'class="ix-header"')
                self.assertNotContains(resp, 'id="ixOwnerMenu"')

    def test_printed_invoice_unchanged(self):
        self.client.force_login(self.owner)
        inv = make_invoice(self.owner, make_customer(self.owner, phone='8000000003'), date(2026, 5, 1))
        resp = self.client.get(f'/store/{self.owner.username}/invoice/{inv.id}/')
        self.assertEqual(resp.status_code, 200)
        self.assertNotContains(resp, 'ix-header')


class StylesWithoutStaticServingTests(TestCase):
    """Pages must be fully styled even when Django does not serve /static/ (DEBUG=False, missing folder)."""

    def test_styles_inline_on_public_and_owner_pages(self):
        owner = make_owner(phone='9000000009', username='shop9')
        for url in ['/', '/accounts/login/']:
            resp = self.client.get(url)
            self.assertContains(resp, '--brand: #1D4ED8')
        self.client.force_login(owner)
        for url in ['/', '/store/sales-dashboard/', '/store/shop9/analytics/', '/bank/']:
            with self.subTest(url=url):
                resp = self.client.get(url)
                self.assertContains(resp, '<style id="ix-styles">')
                self.assertContains(resp, 'body.ix header.ix-header')
