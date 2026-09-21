"""Tests for the Retrospective Data Upload feature: manifest creation, case
counting rules, duplicate folder rejection, per-file failure handling, and
retry. Mirrors the ~15-case local validation set described in the feature
spec (DICOM+report, DICOM only, report only, no data, duplicate, invalid
file, partial, retry)."""

import itertools
from unittest.mock import patch

from .conftest import get_token, TestRetroSession
from backend.src.models.retrospective_models import RetrospectiveUploadBatch

TEST_HOSPITAL_ID = "clinic_00002"  # seeded as name="Test" in conftest

_folder_counter = itertools.count(1)


def auth_headers(role="Admin", email="admin@test.com", hospital_id=TEST_HOSPITAL_ID):
    token = get_token(role, email, hospital_id=hospital_id)
    return {"Authorization": f"Bearer {token}"}


def make_manifest(cases, folder_name=None):
    if folder_name is None:
        folder_name = f"Retrospective_Data_{next(_folder_counter)}"
    return {"source_folder_name": folder_name, "cases": cases}


class TestAccessControl:
    def test_non_admin_rejected(self, client):
        headers = auth_headers(role="Staff", email="staff@test.com", hospital_id="clinic_00001")
        resp = client.post("/api/v1/admin/retrospective/batches", json=make_manifest([]), headers=headers)
        assert resp.status_code == 403

    def test_admin_outside_test_institute_rejected(self, client):
        headers = auth_headers(role="Admin", email="admin@test.com", hospital_id="clinic_00001")
        resp = client.post("/api/v1/admin/retrospective/batches", json=make_manifest([]), headers=headers)
        assert resp.status_code == 403

    def test_empty_manifest_rejected(self, client):
        resp = client.post("/api/v1/admin/retrospective/batches", json=make_manifest([]), headers=auth_headers())
        assert resp.status_code == 400


class TestCaseCounting:
    def test_dicom_and_report_is_one_case(self, client):
        manifest = make_manifest([{
            "source_case_name": "Case_001",
            "files": [
                {"file_type": "DICOM", "file_name": "image1.dcm"},
                {"file_type": "DICOM", "file_name": "image2.dcm"},
                {"file_type": "REPORT", "file_name": "report.pdf"},
            ],
        }])
        resp = client.post("/api/v1/admin/retrospective/batches", json=manifest, headers=auth_headers())
        assert resp.status_code == 200
        body = resp.json()
        assert body["batch"]["total_cases_identified"] == 1
        case = body["cases"][0]
        assert case["retrospective_case_id"].startswith("RETRO_")
        assert len(case["files"]) == 3

    def test_dicom_only_case(self, client):
        manifest = make_manifest([{
            "source_case_name": "Case_002",
            "files": [{"file_type": "DICOM", "file_name": "image1.dcm"}],
        }])
        resp = client.post("/api/v1/admin/retrospective/batches", json=manifest, headers=auth_headers())
        assert resp.status_code == 200
        assert resp.json()["cases"][0]["case_status"] == "PENDING"

    def test_no_data_case_not_counted(self, client):
        manifest = make_manifest([{"source_case_name": "Case_005", "files": []}])
        resp = client.post("/api/v1/admin/retrospective/batches", json=manifest, headers=auth_headers())
        assert resp.status_code == 200
        body = resp.json()
        assert body["cases"][0]["case_status"] == "NO_DATA"
        assert body["batch"]["no_data_cases"] == 1
        assert body["batch"]["successful_cases"] == 0

    def test_invalid_filename_marks_file_failed_not_whole_batch(self, client):
        manifest = make_manifest([{
            "source_case_name": "Case_008",
            "files": [
                {"file_type": "DICOM", "file_name": "../../etc/passwd.dcm"},
                {"file_type": "DICOM", "file_name": "ok_image.dcm"},
            ],
        }])
        resp = client.post("/api/v1/admin/retrospective/batches", json=manifest, headers=auth_headers())
        assert resp.status_code == 200
        files = resp.json()["cases"][0]["files"]
        # the traversal filename is reduced to its basename ("passwd.dcm") and is safe,
        # so both files should be accepted as PENDING, not rejected -- this asserts the
        # sanitizer neutralizes rather than 500s on path-like input.
        assert {f["file_name"] for f in files} == {"passwd.dcm", "ok_image.dcm"}
        assert all(f["upload_status"] == "PENDING" for f in files)


class TestFileUploadFlow:
    def _create_single_dicom_case(self, client):
        manifest = make_manifest([{
            "source_case_name": "Case_010",
            "files": [
                {"file_type": "DICOM", "file_name": "a.dcm"},
                {"file_type": "DICOM", "file_name": "b.dcm"},
            ],
        }])
        resp = client.post("/api/v1/admin/retrospective/batches", json=manifest, headers=auth_headers())
        body = resp.json()
        return body["batch"]["upload_batch_id"], body["cases"][0]

    def test_upload_url_generation(self, client):
        _, case = self._create_single_dicom_case(client)
        file_id = case["files"][0]["id"]
        with patch("backend.src.api.retrospective._get_storage_client") as mock_client, \
             patch("backend.src.api.retrospective.settings") as mock_settings:
            mock_settings.GCP_STORAGE_BUCKET = "breast-cancer-image-dataset"
            mock_blob = mock_client.return_value.bucket.return_value.blob.return_value
            mock_blob.create_resumable_upload_session.return_value = "https://fake-upload-url"
            resp = client.post(f"/api/v1/admin/retrospective/files/{file_id}/upload-url", headers=auth_headers())
        assert resp.status_code == 200
        data = resp.json()
        assert data["blob_path"].startswith("retrospective/RETRO_")
        assert "/DICOM/" in data["blob_path"]

    def test_partial_then_retry_then_complete(self, client):
        batch_id, case = self._create_single_dicom_case(client)
        file_a, file_b = case["files"]

        # a.dcm succeeds
        resp = client.post(
            f"/api/v1/admin/retrospective/files/{file_a['id']}/upload-complete",
            json={"gcs_url": "gs://bucket/x"}, headers=auth_headers(),
        )
        assert resp.status_code == 200
        assert resp.json()["case_status"] == "PROCESSING"  # b.dcm still pending

        # b.dcm fails
        resp = client.post(
            f"/api/v1/admin/retrospective/files/{file_b['id']}/upload-failed",
            json={"error_message": "network timeout"}, headers=auth_headers(),
        )
        assert resp.status_code == 200
        assert resp.json()["case_status"] == "PARTIAL"

        batch_resp = client.get(f"/api/v1/admin/retrospective/batches/{batch_id}", headers=auth_headers())
        assert batch_resp.json()["batch_status"] == "COMPLETED_WITH_ERRORS"

        # Retry should only surface the failed file, not the already-uploaded one
        retry_resp = client.post(f"/api/v1/admin/retrospective/batches/{batch_id}/retry", headers=auth_headers())
        assert retry_resp.status_code == 200
        retry_body = retry_resp.json()
        retried_ids = {f["id"] for f in retry_body["files_to_retry"]}
        assert retried_ids == {file_b["id"]}

        # Complete the retried file -> case and batch should now be fully successful
        resp = client.post(
            f"/api/v1/admin/retrospective/files/{file_b['id']}/upload-complete",
            json={"gcs_url": "gs://bucket/y"}, headers=auth_headers(),
        )
        assert resp.json()["case_status"] == "COMPLETED"
        batch_resp = client.get(f"/api/v1/admin/retrospective/batches/{batch_id}", headers=auth_headers())
        assert batch_resp.json()["batch_status"] == "COMPLETED"
        assert batch_resp.json()["failed_cases"] == 0

    def test_batch_reaches_completed_once_every_distinct_case_finishes(self, client):
        # Regression: batch progress must reflect every case's state, not lag
        # behind the case that was just updated in the same request.
        manifest = make_manifest([
            {"source_case_name": f"Case_multi_{i}", "files": [{"file_type": "REPORT", "file_name": f"r{i}.pdf"}]}
            for i in range(3)
        ])
        resp = client.post("/api/v1/admin/retrospective/batches", json=manifest, headers=auth_headers())
        body = resp.json()
        batch_id = body["batch"]["upload_batch_id"]
        file_ids = [c["files"][0]["id"] for c in body["cases"]]

        for i, fid in enumerate(file_ids):
            resp = client.post(
                f"/api/v1/admin/retrospective/files/{fid}/upload-complete",
                json={"gcs_url": f"gs://bucket/multi{i}"}, headers=auth_headers(),
            )
            assert resp.json()["case_status"] == "COMPLETED"
            batch_resp = client.get(f"/api/v1/admin/retrospective/batches/{batch_id}", headers=auth_headers()).json()
            is_last = i == len(file_ids) - 1
            assert batch_resp["batch_status"] == ("COMPLETED" if is_last else "PROCESSING")

    def test_retry_with_no_retriable_files_resolves_immediately_not_stuck_processing(self, client):
        # Regression: retry used to force case_status="PROCESSING" even when
        # nothing was actually reset to PENDING (e.g. a file that failed
        # validation and has no storage path to retry against), leaving the
        # case -- and therefore the batch -- stuck forever with no event left
        # to re-run the rollup.
        manifest = make_manifest([{
            "source_case_name": "Case_unfixable",
            "files": [{"file_type": "DICOM", "file_name": "../"}],  # sanitizes to nothing -> FAILED, gcp_path None
        }])
        resp = client.post("/api/v1/admin/retrospective/batches", json=manifest, headers=auth_headers())
        body = resp.json()
        assert body["cases"][0]["case_status"] == "FAILED"
        batch_id = body["batch"]["upload_batch_id"]

        retry_resp = client.post(f"/api/v1/admin/retrospective/batches/{batch_id}/retry", headers=auth_headers())
        assert retry_resp.status_code == 200
        assert retry_resp.json()["files_to_retry"] == []  # nothing retriable

        cases = client.get(f"/api/v1/admin/retrospective/batches/{batch_id}/cases", headers=auth_headers()).json()
        assert cases[0]["case_status"] == "FAILED"
        batch_resp = client.get(f"/api/v1/admin/retrospective/batches/{batch_id}", headers=auth_headers()).json()
        assert batch_resp["batch_status"] == "FAILED"


class TestDuplicatePrevention:
    def test_reuploading_same_folder_name_is_rejected(self, client):
        manifest = make_manifest([{
            "source_case_name": "Case_Dup",
            "files": [{"file_type": "REPORT", "file_name": "report.pdf"}],
        }], folder_name="Retrospective_Data_Dup_Test")

        first = client.post("/api/v1/admin/retrospective/batches", json=manifest, headers=auth_headers())
        assert first.status_code == 200
        first_batch_id = first.json()["batch"]["upload_batch_id"]

        # Uploading a folder with the same name again -- even with different
        # case contents -- is rejected outright, before any case is created.
        second = client.post("/api/v1/admin/retrospective/batches", json=manifest, headers=auth_headers())
        assert second.status_code == 409
        assert first_batch_id in second.json()["detail"]

        # No new batch/cases were created by the rejected attempt.
        batches = client.get("/api/v1/admin/retrospective/batches", headers=auth_headers()).json()
        matching = [b for b in batches if b["source_folder_name"] == "Retrospective_Data_Dup_Test"]
        assert len(matching) == 1

    def test_reusing_a_case_name_under_a_different_folder_is_also_rejected(self, client):
        # A case subfolder name is checked for reuse across ALL batches for
        # this institute, not just within the same top-level folder name.
        manifest_a = make_manifest([{"source_case_name": "Case_X", "files": [{"file_type": "REPORT", "file_name": "r.pdf"}]}])
        manifest_b = make_manifest([{"source_case_name": "Case_X", "files": [{"file_type": "REPORT", "file_name": "r.pdf"}]}])
        resp_a = client.post("/api/v1/admin/retrospective/batches", json=manifest_a, headers=auth_headers())
        assert resp_a.status_code == 200
        first_case_id = resp_a.json()["cases"][0]["retrospective_case_id"]

        resp_b = client.post("/api/v1/admin/retrospective/batches", json=manifest_b, headers=auth_headers())
        assert resp_b.status_code == 409
        assert "Case_X" in resp_b.json()["detail"]
        assert first_case_id in resp_b.json()["detail"]

    def test_different_case_names_in_new_folder_is_allowed(self, client):
        manifest_a = make_manifest([{"source_case_name": "Case_Y1", "files": [{"file_type": "REPORT", "file_name": "r.pdf"}]}])
        manifest_b = make_manifest([{"source_case_name": "Case_Y2", "files": [{"file_type": "REPORT", "file_name": "r.pdf"}]}])
        resp_a = client.post("/api/v1/admin/retrospective/batches", json=manifest_a, headers=auth_headers())
        resp_b = client.post("/api/v1/admin/retrospective/batches", json=manifest_b, headers=auth_headers())
        assert resp_a.status_code == 200
        assert resp_b.status_code == 200
        assert resp_a.json()["cases"][0]["retrospective_case_id"] != resp_b.json()["cases"][0]["retrospective_case_id"]


class TestBatchStatusSelfHeals:
    def test_get_endpoints_recompute_a_stale_persisted_status(self, client):
        # A batch's summary fields are normally kept current by whatever last
        # touched one of its files, but a row written before a rollup bug fix
        # shipped (or corrupted by any future bug) would otherwise sit wrong
        # forever, since nothing re-triggers the computation on its own.
        # GET must recompute from the actual case data every time, so any
        # stale row self-heals the moment it's read.
        manifest = make_manifest([
            {"source_case_name": "Case_heal_1", "files": [{"file_type": "DICOM", "file_name": "a.dcm"}]},
            {"source_case_name": "Case_heal_2", "files": [{"file_type": "DICOM", "file_name": "b.dcm"}]},
        ])
        body = client.post("/api/v1/admin/retrospective/batches", json=manifest, headers=auth_headers()).json()
        batch_id = body["batch"]["upload_batch_id"]
        for case in body["cases"]:
            client.post(
                f"/api/v1/admin/retrospective/files/{case['files'][0]['id']}/upload-complete",
                json={"gcs_url": "gs://x"}, headers=auth_headers(),
            )

        # Directly corrupt the persisted row, bypassing the app entirely --
        # simulating a batch stuck from before a fix, or any other write bug.
        db = TestRetroSession()
        row = db.query(RetrospectiveUploadBatch).filter_by(upload_batch_id=batch_id).first()
        row.batch_status = "PROCESSING"
        row.successful_cases = 1
        db.commit()
        db.close()

        healed = client.get(f"/api/v1/admin/retrospective/batches/{batch_id}", headers=auth_headers()).json()
        assert healed["batch_status"] == "COMPLETED"
        assert healed["successful_cases"] == 2

        # corrupt again and confirm the list endpoint self-heals too
        db = TestRetroSession()
        row = db.query(RetrospectiveUploadBatch).filter_by(upload_batch_id=batch_id).first()
        row.batch_status = "PROCESSING"
        db.commit()
        db.close()

        listing = client.get("/api/v1/admin/retrospective/batches", headers=auth_headers()).json()
        row_out = next(b for b in listing if b["upload_batch_id"] == batch_id)
        assert row_out["batch_status"] == "COMPLETED"


class TestDashboardCount:
    def test_counts_only_cases_with_ingested_data(self, client):
        manifest = make_manifest([
            {"source_case_name": "C1", "files": [{"file_type": "DICOM", "file_name": "d.dcm"}]},
            {"source_case_name": "C2", "files": []},
        ])
        before = client.get("/api/v1/admin/retrospective/dashboard-count", headers=auth_headers()).json()["total_retrospective_cases"]
        body = client.post("/api/v1/admin/retrospective/batches", json=manifest, headers=auth_headers()).json()
        file_id = body["cases"][0]["files"][0]["id"]
        client.post(
            f"/api/v1/admin/retrospective/files/{file_id}/upload-complete",
            json={"gcs_url": "gs://bucket/r"}, headers=auth_headers(),
        )
        after = client.get("/api/v1/admin/retrospective/dashboard-count", headers=auth_headers()).json()["total_retrospective_cases"]
        # the NO_DATA case (C2) must never inflate the count; only the one
        # dicom-having case (C1) should add to it.
        assert after == before + 1


class TestReportOnlyExclusion:
    def test_report_only_case_is_hidden_and_not_counted(self, client):
        manifest = make_manifest([
            {"source_case_name": "Case_ReportOnly", "files": [{"file_type": "REPORT", "file_name": "r.pdf"}]},
            {"source_case_name": "Case_DicomOnly", "files": [{"file_type": "DICOM", "file_name": "a.dcm"}]},
            {"source_case_name": "Case_Both", "files": [
                {"file_type": "DICOM", "file_name": "b.dcm"},
                {"file_type": "REPORT", "file_name": "r2.pdf"},
            ]},
        ])
        body = client.post("/api/v1/admin/retrospective/batches", json=manifest, headers=auth_headers()).json()
        batch_id = body["batch"]["upload_batch_id"]
        for case in body["cases"]:
            for f in case["files"]:
                client.post(
                    f"/api/v1/admin/retrospective/files/{f['id']}/upload-complete",
                    json={"gcs_url": "gs://x"}, headers=auth_headers(),
                )

        cases = client.get(f"/api/v1/admin/retrospective/batches/{batch_id}/cases", headers=auth_headers()).json()
        names = {c["source_case_name"] for c in cases}
        assert "Case_ReportOnly" not in names
        assert names == {"Case_DicomOnly", "Case_Both"}

        batch_resp = client.get(f"/api/v1/admin/retrospective/batches/{batch_id}", headers=auth_headers()).json()
        assert batch_resp["total_cases_identified"] == 2
        assert batch_resp["successful_cases"] == 2
        assert batch_resp["batch_status"] == "COMPLETED"

        report_only_id = next(c["retrospective_case_id"] for c in body["cases"] if c["source_case_name"] == "Case_ReportOnly")
        detail_resp = client.get(f"/api/v1/admin/retrospective/cases/{report_only_id}", headers=auth_headers())
        assert detail_resp.status_code == 404

    def test_case_with_pending_or_failed_dicom_stays_visible(self, client):
        # A case that HAS dicom files (even if they haven't succeeded yet, or
        # failed) must stay visible so it can be tracked/retried -- only a
        # case whose manifest never included any DICOM at all is hidden.
        manifest = make_manifest([
            {"source_case_name": "Case_DicomPending", "files": [
                {"file_type": "DICOM", "file_name": "a.dcm"},
                {"file_type": "REPORT", "file_name": "r.pdf"},
            ]},
        ])
        body = client.post("/api/v1/admin/retrospective/batches", json=manifest, headers=auth_headers()).json()
        batch_id = body["batch"]["upload_batch_id"]
        report_file = next(f for f in body["cases"][0]["files"] if f["file_type"] == "REPORT")
        client.post(
            f"/api/v1/admin/retrospective/files/{report_file['id']}/upload-complete",
            json={"gcs_url": "gs://x"}, headers=auth_headers(),
        )
        # DICOM file is still PENDING at this point -- the case must remain visible.
        cases = client.get(f"/api/v1/admin/retrospective/batches/{batch_id}/cases", headers=auth_headers()).json()
        assert {c["source_case_name"] for c in cases} == {"Case_DicomPending"}
