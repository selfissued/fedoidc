import json
import os
import shutil
from urllib.parse import urlparse

from fedoidc import unfurl
from oic.utils.keyio import build_keyjar, KeyJar

from fedoidc.operator import Operator
from fedoidc.test_utils import make_fs_jwks_bundle, MetaDataStore, make_ms, \
    make_signed_metadata_statement_uri
from fedoidc.test_utils import make_jwks_bundle
from fedoidc.test_utils import make_signed_metadata_statement

TEST_ISS = "https://test.example.com"
KEYDEFS = [
    {"type": "RSA", "key": '', "use": ["sig"]},
    {"type": "EC", "crv": "P-256", "use": ["sig"]}
]

SIGN_KEYJAR = build_keyjar(KEYDEFS)[1]

FO = {'swamid': 'https://swamid.sunet.se', 'feide': 'https://www.feide.no',
      'edugain': 'https://edugain.com'}
OA = {'sunet': 'https://sunet.se', 'uninett': 'https://uninett.no'}

SMS_DEF = {
    OA['sunet']: {
        "discovery": {
            FO['swamid']: [
                {'request': {}, 'requester': OA['sunet'],
                 'signer_add': {'federation_usage': 'discovery'},
                 'signer': FO['swamid']}
            ],
            FO['feide']: [
                {'request': {}, 'requester': OA['sunet'],
                 'signer_add': {'federation_usage': 'discovery'},
                 'signer': FO['feide']}
            ],
            FO['edugain']: [
                {'request': {}, 'requester': FO['swamid'],
                 'signer_add': {'federation_usage': 'discovery'},
                 'signer': FO['edugain']},
                {'request': {}, 'requester': OA['sunet'],
                 'signer_add': {}, 'signer': FO['swamid']}
            ]
        }
    }
}


def test_make_jwks_bundle():
    """
    testing in-memory JWKS bundle
    """
    liss = ['https://foo.example.com', 'https://bar.example.com']
    jb = make_jwks_bundle(TEST_ISS, liss, SIGN_KEYJAR, KEYDEFS)
    assert set(jb.keys()) == set(liss)
    for iss in liss:
        _kj = jb[iss]
        assert isinstance(_kj, KeyJar)
        assert len(_kj.keys()) == 1  # Issuers
        assert list(_kj.keys())[0] == iss
        _keys = _kj.get_issuer_keys(iss)
        assert len(_keys) == 2
        assert _kj.keys_by_alg_and_usage(iss, 'RS256', 'sig')
        assert _kj.keys_by_alg_and_usage(iss, 'ES256', 'sig')


def test_make_fs_jwks_bundle():
    """
    testing on disc JWKS bundle
    """
    liss = ['https://foo.example.com', 'https://bar.example.com']
    if os.path.isdir('./fo_jwks'):
        shutil.rmtree('./fo_jwks')

    jb = make_fs_jwks_bundle(TEST_ISS, liss, SIGN_KEYJAR, KEYDEFS)
    assert set(jb.keys()) == set(liss)
    for iss in liss:
        _kj = jb[iss]
        assert isinstance(_kj, KeyJar)
        assert len(_kj.keys()) == 1  # Issuers
        assert list(_kj.keys())[0] == iss
        _keys = _kj.get_issuer_keys(iss)
        assert len(_keys) == 2
        assert _kj.keys_by_alg_and_usage(iss, 'RS256', 'sig')
        assert _kj.keys_by_alg_and_usage(iss, 'ES256', 'sig')


def test_make_signed_metadata_statements():
    liss = list(FO.values())
    liss.extend(list(OA.values()))

    key_bundle = make_fs_jwks_bundle(TEST_ISS, liss, SIGN_KEYJAR, KEYDEFS, './')

    operator = {}

    for entity, _keyjar in key_bundle.items():
        operator[entity] = Operator(iss=entity, keyjar=_keyjar)

    _spec = SMS_DEF[OA['sunet']]["discovery"][FO['swamid']]
    ms = make_signed_metadata_statement(_spec, operator)
    assert ms

    _spec = SMS_DEF[OA['sunet']]["discovery"][FO['edugain']]
    ms = make_signed_metadata_statement(_spec, operator)
    assert list(ms.keys()) == [FO['edugain']]


def test_metadatastore():
    mds = MetaDataStore('mds')
    desc = SMS_DEF[OA['sunet']]["discovery"][FO['swamid']][0]
    operator = {}

    liss = list(FO.values())
    liss.extend(list(OA.values()))

    key_bundle = make_fs_jwks_bundle(TEST_ISS, liss, SIGN_KEYJAR, KEYDEFS, './')
    for entity, _keyjar in key_bundle.items():
        operator[entity] = Operator(iss=entity, keyjar=_keyjar)

    _x = make_ms(desc, False, operator)
    _jws = list(_x.values())[0]
    mds[_jws] = _jws

    assert mds.key_conv['to'](_jws) in list(mds.keys())


def test_make_signed_metadata_statement_uris():
    liss = list(FO.values())
    liss.extend(list(OA.values()))

    key_bundle = make_fs_jwks_bundle(TEST_ISS, liss, SIGN_KEYJAR, KEYDEFS, './')

    operator = {}

    for entity, _keyjar in key_bundle.items():
        operator[entity] = Operator(iss=entity, keyjar=_keyjar)

    _spec = SMS_DEF[OA['sunet']]["discovery"][FO['swamid']]
    mds = MetaDataStore('mds')
    mds.reset()
    ms = make_signed_metadata_statement_uri(_spec, operator, mds,
                                            'https:/example.org/ms')
    assert ms

    _spec = SMS_DEF[OA['sunet']]["discovery"][FO['edugain']]
    mds.reset()
    ms = make_signed_metadata_statement_uri(_spec, operator, mds,
                                            'https:/example.org/ms')
    assert list(ms.keys()) == [FO['edugain']]

    # Now parse the result

    _url0 = ms[FO['edugain']]

    p = urlparse(_url0)
    _jws0 = mds[p.path.split('/')[-1]]
    _md0 = unfurl(_jws0)

    _mds = []
    for _fo, _url in _md0['metadata_statement_uris'].items():
        p = urlparse(_url)
        _jws = mds[p.path.split('/')[-1]]
        _mds.append(json.dumps(unfurl(_jws)))

    _md0['metadata_statements'] = _mds
    del _md0['metadata_statement_uris']

    assert True

    op = Operator()
    _res = op.evaluate_metadata_statement(_md0)
    assert _res[0].le == {'federation_usage': 'discovery'}
