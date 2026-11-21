import json
import pytest
from flask import g
from werkzeug.security import check_password_hash
from psb.db import one,transaction
from psb.domain import participant
from test_system import paid_participant,DATA
from conftest import login_as,post,PASSWORD


@pytest.mark.parametrize('length',[7,8])
@pytest.mark.parametrize('flow',['register','staff','account','reset'])
def test_password_boundary(app,length,flow):
    password='a'*length
    c=app.test_client()
    if flow in ('register','reset'):
        with app.app_context():
            g.user=one("SELECT * FROM users WHERE username='rangkap'")
            with transaction():
                pid,_,_=paid_participant(account=flow=='reset')
            number=participant(pid)['number']
    if flow=='register':
        path='/daftar-akun';data={**DATA,'number':number,'password':password,'confirm':password}
        username=number
    elif flow=='staff':
        login_as(app,c,'admin');path='/pengaturan/petugas'
        data={'action':'staff','username':'uji-batas','roles':'pemberkasan','password':password};username='uji-batas'
    elif flow=='account':
        login_as(app,c,'admin');path='/akun'
        data={'old_password':PASSWORD,'password':password,'confirm':password};username='admin'
    else:
        assert post(c,'/lupa-password',{'number':number,'email':DATA['email']}).status_code==302
        with app.app_context():
            path=json.loads(one("SELECT payload FROM outbox WHERE event_key LIKE 'reset:%'")['payload'])['link'].replace('http://localhost','')
        data={'password':password,'confirm':password};username=number
    result=post(c,path,data)
    assert result.status_code==(302 if length==8 else 400)
    with app.app_context():
        user=one('SELECT password_hash FROM users WHERE username=?',(username,))
        if length==8: assert check_password_hash(user['password_hash'],password)
        elif user: assert not check_password_hash(user['password_hash'],password)
