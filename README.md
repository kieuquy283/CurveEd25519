# Curve25519 Crypto App

Ứng dụng mã hóa, giải mã và ký số sử dụng **họ đường cong Elliptic Curve 25519**.

---

## Giới thiệu

Project này xây dựng một hệ thống mã hóa lai (Hybrid Cryptosystem) gồm:

- **Ed25519** → ký số (Digital Signature)
- **X25519** → trao đổi khóa (Key Exchange)
- **ChaCha20-Poly1305** → mã hóa dữ liệu (AEAD Encryption)
- **HKDF-SHA256** → dẫn xuất khóa (Key Derivation)

Đây là mô hình tương tự các hệ thống thực tế như:
- TLS (HTTPS)
- Signal Protocol
- WhatsApp Encryption

---

## Kiến trúc hệ thống

```text
Plaintext
   ↓
[Symmetric Encryption (ChaCha20)]
   ↓
[X25519 → Shared Secret]
   ↓
[HKDF → Wrap Key]
   ↓
[Encrypt Payload Key]
   ↓
[Ed25519 → Signature]
   ↓
→ JSON Message
```

---

## Công nghệ sử dụng
```text
Thành phần	Công nghệ
Ngôn ngữ	Python
Crypto library	cryptography
CLI framework	typer
```
---

## Cài đặt
1. Clone project
```bash
git clone https://github.com/<your-username>/CurveEd25519.git
cd CurveEd25519
```

2. Tạo virtual environment
```bash
python -m venv .venv
```

3. Activate

Windows:

```bash
.venv\Scripts\activate
```

4. Cài thư viện
```bash
pip install -r requirements.txt
```
---

## Demo sử dụng
1. Tạo khóa
```bash
python main.py keygen --profile alice
python main.py keygen --profile bob
```

2. Export public key
```bash
python main.py export-contact --profile alice
python main.py export-contact --profile bob
```

3. Import contact
```bash
python main.py import-contact --contact-file data/contacts/alice.contact.json
python main.py import-contact --contact-file data/contacts/bob.contact.json
```

4. Alice gửi message
```bash
python main.py encrypt --from alice --to bob --message "Hello Bob"
```

5. Bob giải mã
```bash
python main.py decrypt --profile bob --in data/messages/alice_to_bob.enc.json --trusted-sender alice
```

6. Ký file riêng
```bash
python main.py sign --profile alice --in main.py
```

7. Verify chữ ký
```bash
python main.py verify --contact alice --in main.py --sig main.py.sig.json
```