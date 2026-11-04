"""Agent D frontend-fix tests: onboarding docs, advances, claim decisions.

Covers D33 (OnboardingDocument multipart + validators), D34 (pagers honor
?page=N) and D36 (grievance/advance/claim-decision/roster endpoints).
"""

from io import BytesIO
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from rest_framework.test import APIClient, APIRequestFactory, force_authenticate

from core.models import (
    ClaimStatus,
    Employee,
    EmployeeAuditLog,
    ExpenseClaim,
    ShiftRoster,
)
from core.views_docs import (
    OnboardingDocument,
    OnboardingDocumentDownloadView,
    SalaryAdvance,
)

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

    def test_onboarding_documents_can_be_replaced_and_deleted(self):
        create_response = self.client.post(
            "/api/onboarding-docs/",
            {
                "employee": str(self.employee.id),
                "doc_type": "NBI",
                "file": pdf_file("old-nbi.pdf"),
            },
            format="multipart",
        )
        self.assertEqual(create_response.status_code, 201, create_response.content)
        document = OnboardingDocument.objects.get(pk=create_response.json()["id"])
        old_file_name = document.file.name
        self.addCleanup(document.file.delete, save=False)

        with self.captureOnCommitCallbacks(execute=True):
            replace_response = self.client.patch(
                f"/api/onboarding-docs/{document.pk}/",
                {"doc_type": "PSA", "file": pdf_file("replacement.pdf")},
                format="multipart",
            )
        self.assertEqual(replace_response.status_code, 200, replace_response.content)
        document.refresh_from_db()
        self.assertEqual(document.doc_type, "PSA")
        self.assertTrue(
            document.file.name.rsplit("/", 1)[-1].startswith("replacement")
        )
        self.assertFalse(document.file.storage.exists(old_file_name))

        with self.captureOnCommitCallbacks(execute=True):
            delete_response = self.client.delete(f"/api/onboarding-docs/{document.pk}/")
        self.assertEqual(delete_response.status_code, 204)
        self.assertFalse(OnboardingDocument.objects.filter(pk=document.pk).exists())
        self.assertFalse(document.file.storage.exists(document.file.name))

    def test_employee_document_access_is_limited_to_own_read_only_documents(self):
        employee_user = User.objects.create_user(
            username="document-owner", password="document-test-password"
        )
        owner = Employee.objects.create(
            first_name="Document",
            last_name="Owner",
            email="document.owner@example.com",
            user=employee_user,
        )
        own_document = OnboardingDocument.objects.create(
            employee=owner,
            doc_type="PSA",
            file=pdf_file("owner-psa.pdf"),
        )
        self.addCleanup(own_document.file.delete, save=False)
        other_document = OnboardingDocument.objects.create(
            employee=self.employee,
            doc_type="NBI",
            file=pdf_file("private-nbi.pdf"),
        )
        self.addCleanup(other_document.file.delete, save=False)
        self.client.force_authenticate(user=employee_user)

        own_list = self.client.get(f"/api/onboarding-docs/?employee={owner.pk}")
        self.assertEqual(own_list.status_code, 200)
        self.assertEqual(own_list.json()["count"], 1)
        self.assertEqual(
            own_list.json()["results"][0]["file"],
            f"/api/onboarding-docs/{own_document.pk}/download/",
        )
        request = APIRequestFactory().get(
            f"/api/onboarding-docs/{own_document.pk}/download/"
        )
        force_authenticate(request, user=employee_user)
        with patch.object(
            own_document.file.storage, "open", return_value=BytesIO(b"private")
        ):
            download_response = OnboardingDocumentDownloadView.as_view()(
                request, pk=own_document.pk
            )
        self.assertEqual(download_response.status_code, 200)
        self.assertIn("attachment", download_response["Content-Disposition"])
        other_list = self.client.get(f"/api/onboarding-docs/?employee={self.employee.pk}")
        self.assertEqual(other_list.status_code, 200)
        self.assertEqual(other_list.json()["count"], 0)
        self.assertEqual(
            self.client.get(
                f"/api/onboarding-docs/{other_document.pk}/download/"
            ).status_code,
            403,
        )
        write_response = self.client.post(
            "/api/onboarding-docs/",
            {
                "employee": str(owner.pk),
                "doc_type": "NBI",
                "file": pdf_file(),
            },
            format="multipart",
        )
        self.assertEqual(write_response.status_code, 403)

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

    # -- D33: file size/MIME validation (backend + frontend mirror) ---------
    def test_onboarding_file_validation_wiring(self):
        from django.conf import settings

        from core.views_docs import ONBOARDING_ALLOWED_TYPES, ONBOARDING_MAX_BYTES

        self.assertEqual(ONBOARDING_MAX_BYTES, 10 * 1024 * 1024)
        self.assertEqual(
            ONBOARDING_ALLOWED_TYPES,
            {
                "application/pdf": {"pdf"},
                "image/jpeg": {"jpg", "jpeg"},
                "image/png": {"png"},
            },
        )
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        html = response.content.decode()
        self.assertIn('accept=".pdf,.jpg,.jpeg,.png"', html)
        js = (settings.BASE_DIR / "static" / "js" / "dashboard.js").read_text(encoding="utf-8")
        self.assertIn("validateOnboardingFile", js)
        self.assertIn("ONBOARDING_MAX_BYTES", js)
        self.assertIn("10 * 1024 * 1024", js)
        self.assertIn("application/pdf", js)
        self.assertIn("image/jpeg", js)
        self.assertIn("image/png", js)

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
        js = (settings.BASE_DIR / "static" / "js" / "dashboard.js").read_text(encoding="utf-8")
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

    # -- D36: advances/grievance/roster frontend wiring ----------------------
    def test_advance_grievance_roster_wiring(self):
        from django.conf import settings

        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        html = response.content.decode()
        for field_id in (
            'id="advanceApplicant"',
            'id="advanceAmount"',
            'id="advanceTerms"',
            'id="advancePurpose"',
            'id="grievComplainant"',
            'id="grievCategory"',
            'id="grievTitle"',
            'id="grievDetails"',
        ):
            self.assertIn(field_id, html)
        self.assertIn("confirmAddStaff(", html)
        js = (settings.BASE_DIR / "static" / "js" / "dashboard.js").read_text(encoding="utf-8")
        self.assertIn("handleRequestAdvance", js)
        self.assertIn("/api/advances/", js)
        self.assertIn("loadAdvancesView", js)
        self.assertIn("handleGrievanceSubmit", js)
        self.assertIn("conversation_key", js)
        self.assertIn("grievance", js)
        self.assertIn("/api/shift-rosters/", js)
        self.assertIn("persistShiftAssignment", js)
        self.assertIn("confirmAddStaff", js)

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
        js = (settings.BASE_DIR / "static" / "js" / "dashboard.js").read_text(encoding="utf-8")
        self.assertIn("/api/expense-claims/?status=", js)
        self.assertIn("&page=", js)
        self.assertIn("/api/audit-logs/?page=", js)
        self.assertIn("/api/advances/?page=", js)
        self.assertIn("claimsPagerGoto", js)
        self.assertIn("auditPagerGoto", js)
        self.assertIn("advancesPagerGoto", js)
        self.assertNotIn("Loading page", js)

    # -- frontend wiring present -------------------------------------------
    def test_hr_onboarding_form_supports_optional_document_uploads(self):
        from django.conf import settings

        html = (settings.BASE_DIR / "core" / "templates" / "core" / "hr_onboarding.html").read_text(
            encoding="utf-8"
        )
        self.assertIn('name="first_name"', html)
        self.assertIn('name="last_name"', html)
        self.assertIn('name="email"', html)
        self.assertIn('name="department"', html)
        self.assertIn('name="role"', html)
        self.assertIn('name="date_hired"', html)
        self.assertIn('id="submitNewHire"', html)
        self.assertIn("Optional onboarding documents", html)
        self.assertIn('data-doc-type="NBI"', html)
        self.assertIn('data-doc-type="BIR2316"', html)
        self.assertIn('data-doc-type="PSA"', html)
        self.assertIn('data-doc-type="contract"', html)
        self.assertIn('data-doc-type="government_records"', html)
        self.assertIn("validateDocument", html)
        self.assertIn("uploadDocuments", html)
        self.assertIn("FormData", html)
        self.assertIn("/api/onboarding-docs/", html)
        self.assertIn("maximum 10 MB per document", html)

    def test_employee_roster_exposes_document_management(self):
        from django.conf import settings

        html = (settings.BASE_DIR / "core" / "templates" / "core" / "index.html").read_text(
            encoding="utf-8"
        )
        js = (settings.BASE_DIR / "static" / "js" / "dashboard.js").read_text(
            encoding="utf-8"
        )
        self.assertIn('id="employeeDocumentsModal"', html)
        self.assertNotIn("Add a document", html)
        self.assertNotIn('id="employeeDocumentType"', html)
        self.assertIn('id="employeeDocumentFile"', html)
        self.assertIn("View documents", js)
        self.assertIn("openEmployeeDocumentsFromButton", js)
        for document_type, label in (
            ("NBI", "NBI Clearance"),
            ("BIR2316", "BIR Form 2316"),
            ("PSA", "PSA Birth Certificate"),
            ("contract", "Signed Employment Contract"),
            ("government_records", "Government Records"),
        ):
            self.assertIn(f"{document_type}: '{label}'", js)
        self.assertIn("pendingDocumentType = type", js)
        self.assertIn("fileInput.click()", js)
        self.assertIn("payload.append('doc_type', docType)", js)
        self.assertIn("Not uploaded", js)
        self.assertIn("Edit / replace", js)
        self.assertIn("Delete", js)
        self.assertIn("method: 'PATCH'", js)
        self.assertIn("method: 'DELETE'", js)
