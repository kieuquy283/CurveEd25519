from app.services.crypto_service import CryptoService
from tests.run_system_validation import build_profiles

alice, bob = build_profiles()
plaintext = b"hello debug"
enc = CryptoService.encrypt_payload(receiver_x25519_public_b64=bob['x25519']['public_key'], plaintext=plaintext)
print('enc keys:', list(enc.keys()))
print('ephemeral_public:', enc['ephemeral_public_key_b64'])
print('salt_wrap:', enc['salt_wrap_b64'])
print('payload_nonce:', enc['payload_nonce_b64'])
from app.services.crypto_service import b64d
from app.services.crypto_service import CryptoService as CS
import base64

print('wrap_key_b64:', enc.get('wrap_key_b64'))
print('wrap_nonce_b64:', enc.get('wrap_nonce_b64'))

shared_secret_b64 = enc.get('shared_secret_b64')
shared_secret = b64d(shared_secret_b64) if shared_secret_b64 else None
salt_wrap = base64.b64decode(enc['salt_wrap_b64'])
if shared_secret is not None:
    wk, wn = CS.derive_wrap_material(shared_secret, salt_wrap)
    print('derived wrap_key matches:', base64.b64encode(wk).decode()==enc.get('wrap_key_b64'))
    print('derived wrap_nonce matches:', base64.b64encode(wn).decode()==enc.get('wrap_nonce_b64'))

envelope = {
    'header':{
        'message_id':'test',
        'sender':{'name':'alice','ed25519_public_key': alice['ed25519']['public_key']},
        'receiver':{'name':'bob'},
        'crypto':{
            'ephemeral_x25519_public_key': enc['ephemeral_public_key_b64'],
            'salt_wrap': enc['salt_wrap_b64'],
            'payload_nonce': enc['payload_nonce_b64'],
        },
    },
    'wrapped_key': enc['wrapped_key_b64'],
    'ciphertext': enc['ciphertext_b64'],
    'signature': {'algorithm':'Ed25519','value':''},
}

try:
    dec = CryptoService.decrypt_payload(receiver_x25519_private_b64=bob['x25519']['private_key'], envelope=envelope)
    print('decrypted OK:', dec)
except Exception as e:
    print('decrypt failed:', repr(e))
    # continue for manual diagnostics
from app.core.envelope import canonical_dumps
from app.core.envelope import b64d as env_b64d
from cryptography.hazmat.primitives.ciphers.aead import ChaCha20Poly1305

header_bytes = canonical_dumps(envelope['header'])
wrapped_key = env_b64d(envelope['wrapped_key'])
salt_wrap = env_b64d(envelope['header']['crypto']['salt_wrap'])
shared_secret = env_b64d(enc['shared_secret_b64'])
wk, wn = CS.derive_wrap_material(shared_secret, salt_wrap)
wrap_cipher = ChaCha20Poly1305(wk)
print('attempt unwrap with header AAD...')
try:
    pk = wrap_cipher.decrypt(wn, wrapped_key, header_bytes)
    print('unwrap with header succeeded, payload_key len', len(pk))
except Exception as ex:
    print('unwrap with header failed:', ex)

print('attempt unwrap with empty AAD...')
try:
    pk2 = wrap_cipher.decrypt(wn, wrapped_key, b'')
    print('unwrap with empty succeeded, payload_key len', len(pk2))
except Exception as ex:
    print('unwrap with empty failed:', ex)
