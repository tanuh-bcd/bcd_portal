from .conftest import get_token

class TestMRMCStudies:
    def test_create_study(self, client, seed_hospital_and_user):
        token = get_token("Admin", "admin@test.com")
        # ... seed a couple of clinician users, then:
        res = client.post("/api/v1/admin/mrmc-studies",
            json={"name": "Test Study", "reader_user_ids": [2, 3], "arbiter_user_id": 4},
            headers={"Authorization": f"Bearer {token}"})
        assert res.status_code == 200

    def test_reject_same_user_as_reader_and_arbiter(self, client, seed_hospital_and_user):
        token = get_token("Admin", "admin@test.com")
        res = client.post("/api/v1/admin/mrmc-studies",
            json={"name": "Test Study", "reader_user_ids": [2], "arbiter_user_id": 2},
            headers={"Authorization": f"Bearer {token}"})
        assert res.status_code == 400