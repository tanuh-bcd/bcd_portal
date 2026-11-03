from google.api_core.exceptions import NotFound

from backend.src.services import retrospective_storage as storage_service
from backend.src.services.retrospective_storage import delete_case_objects


class FakeBlob:
    def __init__(self, bucket, name):
        self.bucket, self.name = bucket, name

    def delete(self):
        if self.name in self.bucket.fail:
            raise RuntimeError("permission denied")
        if self.name not in self.bucket.objects:
            raise NotFound("gone")
        self.bucket.objects.discard(self.name)
        self.bucket.deleted.append(self.name)


class FakeBucket:
    def __init__(self, objects, fail=()):
        self.objects, self.fail, self.deleted = set(objects), set(fail), []

    def list_blobs(self, prefix):
        return [FakeBlob(self, n) for n in sorted(self.objects) if n.startswith(prefix)]

    def blob(self, name):
        return FakeBlob(self, name)


CASE = "RETRO_000001"


def test_deletes_every_object_in_the_case_folder_regardless_of_database_status():
    bucket = FakeBucket({
        f"retrospective/{CASE}/DICOM/a.dcm",   # database says PENDING, but the bytes are there
        f"retrospective/{CASE}/DICOM/b.dcm",
        f"retrospective/{CASE}/report.pdf",
        f"retrospective/{CASE}/",              # folder placeholder
    })
    deleted, failures = delete_case_objects(bucket, [CASE])
    assert (deleted, failures) == (4, [])
    assert bucket.objects == set()


def test_other_cases_with_a_similar_id_are_left_alone():
    bucket = FakeBucket({
        f"retrospective/{CASE}/DICOM/a.dcm",
        "retrospective/RETRO_0000010/DICOM/a.dcm",
        "retrospective/RETRO_000002/DICOM/a.dcm",
    })
    delete_case_objects(bucket, [CASE])
    assert bucket.objects == {"retrospective/RETRO_0000010/DICOM/a.dcm", "retrospective/RETRO_000002/DICOM/a.dcm"}


def test_known_paths_outside_the_retrospective_prefix_are_never_deleted():
    bucket = FakeBucket({"tanuh-data-capture/clinic_00001/subject_00001/file.dcm"})
    deleted, _ = delete_case_objects(bucket, [CASE], known_paths=["tanuh-data-capture/clinic_00001/subject_00001/file.dcm"])
    assert deleted == 0
    assert len(bucket.objects) == 1


def test_database_path_is_deleted_even_if_not_listed():
    bucket = FakeBucket({"retrospective/RETRO_999999/old/a.dcm"})
    deleted, _ = delete_case_objects(bucket, [CASE], known_paths=["retrospective/RETRO_999999/old/a.dcm"])
    assert deleted == 1


def test_object_already_gone_is_not_an_error():
    bucket = FakeBucket(set())
    assert delete_case_objects(bucket, [CASE], known_paths=[f"retrospective/{CASE}/DICOM/a.dcm"]) == (0, [])


def test_failures_are_reported_so_the_portal_keeps_the_record():
    bucket = FakeBucket({f"retrospective/{CASE}/a.dcm", f"retrospective/{CASE}/b.dcm"}, fail={f"retrospective/{CASE}/b.dcm"})
    deleted, failures = delete_case_objects(bucket, [CASE])
    assert deleted == 1
    assert failures == [f"retrospective/{CASE}/b.dcm"]


def test_large_batch_lists_the_retrospective_prefix_once():
    cases = [f"RETRO_{i:06d}" for i in range(1, 40)]
    bucket = FakeBucket({f"retrospective/{c}/DICOM/x.dcm" for c in cases} | {"retrospective/RETRO_900000/DICOM/x.dcm"})
    calls = []
    original = bucket.list_blobs
    bucket.list_blobs = lambda prefix: calls.append(prefix) or original(prefix)
    deleted, failures = delete_case_objects(bucket, cases)
    assert (deleted, failures) == (39, [])
    assert calls == ["retrospective/"]
    assert bucket.objects == {"retrospective/RETRO_900000/DICOM/x.dcm"}
