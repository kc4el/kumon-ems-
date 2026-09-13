"""Agent D frontend-fix tests: onboarding docs, advances, claim decisions.

Covers D33 (OnboardingDocument multipart + validators), D34 (pagers honor
?page=N) and D36 (grievance/advance/claim-decision/roster endpoints).
"""

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from rest_framework.test import APIClient

from core.models import (
    ClaimStatus,
    Employee,
    EmployeeAuditLog,
    ExpenseClaim,
    ShiftRoster,
)
from core.views_docs import OnboardingDocument, SalaryAdvance

PDF = b"%PDF-1.4 fake pdf content"


def pdf_file(name="nbi.pdf", size=None):
    content = PDF if size is None else PDF + b"x" * (size - len(PDF))
    return SimpleUploadedFile(name, content, content_type="application/pdf")


class FrontendFixTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        user = User.objects.create_user(username="fixer", password="x", is_staff=True)
        self.client.force_authenticate(user=user)
        self.employee = Employee.objects.create(
            first_name="Sam", last_name="Vance", email="sam.v@example.com"
        )

    # -- D33: onboarding docs -------------------------------------------
    def test_onboarding_doc_multipart_upload(self):
        response = self.client.post(
            "/api/onboarding-docs/",
            {
                "employee": str(self.employee.id),
                "doc_type": "NBI",
                "file": pdf_file(),
            },
            format="multipart",
        )
        self.assertEqual(response.status_code, 201, response.content)
        body = response.json()
        self.assertEqual(body["doc_type"], "NBI")
        self.assertEqual(
            OnboardingDocument.objects.filter(employee=self.employee).count(), 1
        )

    def test_onboarding_doc_rejects_bad_mime(self):
        bad = SimpleUploadedFile(
            "evil.exe", b"MZ fake", content_type="application/x-msdownload"
        )
        response = self.client.post(
            "/api/onboarding-docs/",
            {
                "employee": str(self.employee.id),
                "doc_type": "PSA",
                "file": bad,
            },
            format="multipart",
        )
        self.assertEqual(response.status_code, 400)

    def test_onboarding_doc_rejects_oversize(self):
        big = pdf_file(size=10 * 1024 * 1024 + 1)
        response = self.client.post(
            "/api/onboarding-docs/",
            {
                "employee": str(self.employee.id),
                "doc_type": "contract",
                "file": big,
            },
            format="multipart",
        )
        self.assertEqual(response.status_code, 400)

    def test_onboarding_doc_rejects_unknown_doc_type(self):
        response = self.client.post(
            "/api/onboarding-docs/",
            {
                "employee": str(self.employee.id),
                "doc_type": "DRIVERS",
                "file": pdf_file(),
            },
            format="multipart",
        )
        self.assertEqual(response.status_code, 400)

    # -- D36: advances ---------------------------------------------------
    def test_advance_create_defaults_pending(self):
        response = self.client.post(
            "/api/advances/",
            {
                "employee": str(self.employee.id),
                "amount": "1500.00",
                "repayment_terms": "2 Pay Cycles",
                "purpose": "Medical copay",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201, response.content)
        self.assertEqual(response.json()["status"], "Pending")
        self.assertEqual(SalaryAdvance.objects.count(), 1)

    def test_advance_rejects_non_positive_amount(self):
        response = self.client.post(
            "/api/advances/",
            {"employee": str(self.employee.id), "amount": "-5"},
            format="json",
        )
        self.assertEqual(response.status_code, 400)

    # -- D36: claim decisions --------------------------------------------
    def test_claim_decision_on_advance_demo_code(self):
        response = self.client.post(
            "/api/claims/ADV-2026-018/decision/",
            {"decision": "Approved"},
            format="json",
        )
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(
            ClaimStatus.objects.get(claim_id="ADV-2026-018").status, "Approved"
        )

    def test_claim_decision_wiring(self):
        from django.conf import settings

        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        html = response.content.decode()
        self.assertIn('id="batchApproveBtn"', html)
        self.assertIn("data-batch-approve-count", html)
        js = (settings.BASE_DIR / "static" / "js" / "dashboard.js").read_text()
        self.assertIn("/decision/", js)
        self.assertIn("updateBatchApproveCount", js)
        self.assertIn("data-batch-approve-count", js)

    def test_claim_decision_on_expense_claim(self):
        claim = ExpenseClaim.objects.create(
            employee=self.employee, title="Hotel", amount="100.00"
        )
        response = self.client.post(
            f"/api/claims/{claim.pk}/decision/",
            {"decision": "Approved"},
            format="json",
        )
        self.assertEqual(response.status_code, 200, response.content)
        claim.refresh_from_db()
        self.assertEqual(claim.status, "Approved")
        self.assertEqual(
            ClaimStatus.objects.get(claim_id=str(claim.pk)).status, "Approved"
        )

    def test_claim_decision_on_demo_code_upserts_status(self):
        response = self.client.post(
            "/api/claims/CLM-2026-081/decision/",
            {"decision": "Rejected"},
            format="json",
        )
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(
            ClaimStatus.objects.get(claim_id="CLM-2026-081").status, "Rejected"
        )

    def test_claim_decision_rejects_bad_value(self):
        claim = ExpenseClaim.objects.create(
            employee=self.employee, title="Meal", amount="10.00"
        )
        response = self.client.post(
            f"/api/claims/{claim.pk}/decision/",
            {"decision": "Maybe"},
            format="json",
        )
        self.assertEqual(response.status_code, 400)

    # -- D36: grievance + roster ------------------------------------------
    def test_grievance_message_posts_to_grievance_key(self):
        response = self.client.post(
            "/api/messages/",
            {"conversation_key": "grievance", "text": "Workload concern"},
            format="multipart",
        )
        self.assertEqual(response.status_code, 201, response.content)
        self.assertEqual(response.json()["conversation_key"], "grievance")

    def test_roster_create_endpoint(self):
        response = self.client.post(
            "/api/shift-rosters/",
            {
                "employee": str(self.employee.id),
                "work_date": "2026-06-18",
                "shift_type": "morning",
                "start_time": "08:00:00",
                "end_time": "16:00:00",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201, response.content)
        self.assertEqual(ShiftRoster.objects.count(), 1)

    # -- D34: pagers honor ?page=N -----------------------------------------
    def test_list_pagers_honor_page_param(self):
        for i in range(11):
            ExpenseClaim.objects.create(
                employee=self.employee,
                title=f"Claim {i:02d}",
                amount="5.00",
            )
        page1 = self.client.get("/api/expense-claims/?page=1&page_size=10")
        page2 = self.client.get("/api/expense-claims/?page=2&page_size=10")
        self.assertEqual(page1.status_code, 200)
        self.assertEqual(page2.status_code, 200)
        self.assertEqual(len(page1.json()["results"]), 10)
        self.assertEqual(len(page2.json()["results"]), 1)

        for i in range(11):
            SalaryAdvance.objects.create(employee=self.employee, amount="100.00")
        adv2 = self.client.get("/api/advances/?page=2&page_size=10")
        self.assertEqual(adv2.status_code, 200)
        self.assertEqual(len(adv2.json()["results"]), 1)

        docs1 = self.client.get("/api/onboarding-docs/?page=1&page_size=10")
        self.assertEqual(docs1.status_code, 200)
        self.assertEqual(docs1.json()["results"], [])

    def test_audit_pager_honors_page_param(self):
        for i in range(11):
            EmployeeAuditLog.objects.create(
                employee=self.employee, action=f"Paged audit event {i:02d}"
            )
        page1 = self.client.get("/api/audit-logs/?page=1&page_size=10")
        page2 = self.client.get("/api/audit-logs/?page=2&page_size=10")
        self.assertEqual(page1.status_code, 200)
        self.assertEqual(page2.status_code, 200)
        total = page1.json()["count"]
        self.assertGreaterEqual(total, 11)
        self.assertEqual(len(page1.json()["results"]), 10)
        self.assertEqual(len(page2.json()["results"]), total - 10)

    # -- D34: every pager button hits a real ?page=N endpoint ----------------
    def test_dashboard_pagers_wiring(self):
        from django.conf import settings

        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        html = response.content.decode()
        for pager in (
            'data-pager="claims-pending"',
            'data-pager="claims-history"',
            'data-pager="advances"',
            'data-pager="audit"',
        ):
            self.assertIn(pager, html)
        for info_id in (
            'id="pendingPagerInfo"',
            'id="historyPagerInfo"',
            'id="advancesPagerInfo"',
            'id="auditPaginationInfo"',
        ):
            self.assertIn(info_id, html)
        # No toast-only pager stubs may remain.
        self.assertNotIn("Loading page", html)
        js = (settings.BASE_DIR / "static" / "js" / "dashboard.js").read_text()
        self.assertIn("/api/expense-claims/?page=", js)
        self.assertIn("/api/audit-logs/?page=", js)
        self.assertIn("/api/advances/?page=", js)
        self.assertIn("claimsPagerGoto", js)
        self.assertIn("auditPagerGoto", js)
        self.assertIn("advancesPagerGoto", js)
        self.assertNotIn("Loading page", js)

    # -- frontend wiring present -------------------------------------------
    def test_dashboard_template_wiring_docs(self):
        from django.conf import settings

        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        html = response.content.decode()
        self.assertIn('type="file"', html)
        self.assertIn('data-doc-type="NBI"', html)
        self.assertIn('data-doc-type="BIR2316"', html)
        self.assertIn('data-doc-type="PSA"', html)
        self.assertIn('data-doc-type="contract"', html)
        js = (settings.BASE_DIR / "static" / "js" / "dashboard.js").read_text()
        self.assertIn("/api/onboarding-docs/", js)
