import pytest,secrets
from psb.db import transaction,execute,one
from psb.domain import documents_complete,create_payment,approve_payment,participant,sync_completion
from test_system import paid_participant,passed,accepted_files


@pytest.mark.parametrize('level',['MTS','MA'])
def test_diploma_missing_allows_payment_but_not_completion(ctx,level):
    with transaction():
        pid,aid,_=paid_participant(level)
        passed(pid)
        accepted_files(pid,level)
        # Model ijazah menyusul tanpa menghapus riwayat.
        execute("UPDATE uploads SET status='Perlu diperbaiki' WHERE participant_id=? AND category='ijazah'",(pid,))
        assert not documents_complete(pid)
        payment=create_payment(aid,'daftar_ulang','tunai',1000000,secrets.token_hex(20))
        approve_payment(payment)
        assert not participant(pid)['completed']
        execute("UPDATE uploads SET status='Diterima' WHERE participant_id=? AND category='ijazah'",(pid,))
        sync_completion(pid)
        assert participant(pid)['completed']


def test_photo_must_be_accepted_to_complete(ctx):
    with transaction():
        pid,_,_=paid_participant()
        accepted_files(pid)
        execute("UPDATE uploads SET status='Menunggu pemeriksaan' WHERE participant_id=? AND category='foto'",(pid,))
        assert not documents_complete(pid)
        execute("UPDATE uploads SET status='Diterima' WHERE participant_id=? AND category='foto'",(pid,))
        assert documents_complete(pid)
