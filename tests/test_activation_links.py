import json
from datetime import datetime,timedelta,timezone
from flask import g
from conftest import login_as,post
from psb.db import one,execute,transaction
from psb.domain import digest,notify
from test_system import paid_participant


def test_activity_links_only_current_account_token(app):
    with app.app_context():
        g.user=one("SELECT * FROM users WHERE username='rangkap'")
        with transaction():
            pid,aid,_=paid_participant(account=True)
            user=one('SELECT * FROM users WHERE participant_id=?',(pid,))
            for raw,used in [('old-token','2026-01-01'),('new-token',None)]:
                execute("INSERT INTO account_tokens(token_hash,user_id,kind,expires_at,used_at) VALUES(?,?,'aktivasi',?,?)",(digest(raw),user['id'],(datetime.now(timezone.utc)+timedelta(days=1)).isoformat(),used))
                notify(aid,'aktivasi:'+digest(raw),'Aktifkan akun: http://localhost/aktivasi/'+raw+'. Tautan sekali pakai.',channels=('email',),payload={'link':'http://localhost/aktivasi/'+raw})
    c=app.test_client()
    login_as(app,c,'admin')
    page=c.get('/aktivitas').get_data(as_text=True)
    assert 'href="/aktivasi/new-token"' in page
    assert 'href="/aktivasi/old-token"' not in page
    assert 'Buka aktivasi akun' in page and 'Masih berlaku' in page
    assert c.get('/aktivasi/new-token').status_code==200
    assert c.get('/aktivasi/new-token.').status_code==400
    assert post(c,'/aktivasi/new-token').status_code==302
    assert 'href="/aktivasi/new-token"' not in c.get('/aktivitas').get_data(as_text=True)
