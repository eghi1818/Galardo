# HASIL-64 - RBAC inti (item 8 / Tier 1, bagian 1)

- Status : SELESAI
- Sifat  : kode backend + tes
- Isi    : backend/rbac.py (ROLE_RANK VIEWER<TEST_OPERATOR<APPROVER<ADMIN, rank, has_role,
           ensure fail-closed, public), tools/verify_rbac.py (18 tes offline),
           endpoint GET /me, GET /users, POST /users (min TEST_OPERATOR),
           POST /users/*/role (min ADMIN), 5 cek integrasi di tests_integration.py
- Prinsip: semantik D14 dipertahankan (header absen = usr-operator) agar 61 tes tetap hijau
- Verifikasi: verify_rbac 18/18, make test hijau, smoke OK
