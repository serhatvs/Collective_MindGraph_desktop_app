from __future__ import annotations

import sys
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import pytest

from collective_mindgraph.application.security import (
    DeviceEnrollmentRequest,
    DeviceRevokedError,
    KeyManagementError,
    WorkspaceKeyService,
    WorkspaceLockedError,
)
from collective_mindgraph.domain import (
    ContentBinding,
    DeviceKey,
    DeviceTrust,
    EncryptedObject,
    KeyEnvelope,
    RecoveryBundle,
    WorkspaceKey,
)
from collective_mindgraph.domain.identifiers import DeviceId, EnvelopeId, SyncId, WorkspaceId
from collective_mindgraph.infrastructure.persistence import (
    SqliteDatabase,
    SqliteKeyEnvelopeStore,
    initialize_schema,
)
from collective_mindgraph.infrastructure.security import (
    AesGcmContentCipher,
    ChecksummedRecoveryCodeFactory,
    ContentAuthenticationError,
    InvalidRecoveryCodeError,
    KeyUnwrapError,
    ProtectedFileSecretStore,
    X25519DeviceKeyFactory,
    X25519KeyWrapper,
    create_device_secret_store,
)
from collective_mindgraph.infrastructure.security.device_secrets import (
    DeviceSecretUnavailableError,
)

NOW = datetime(2026, 1, 5, 9, 30, tzinfo=UTC)


# RFC 7748 section 6.1 X25519 Diffie-Hellman test vector.
RFC_7748_ALICE_PRIVATE = bytes.fromhex(
    "77076d0a7318a57d3c16c17251b26645df4c2f87ebc0992ab177fba51db92c2a"
)
RFC_7748_ALICE_PUBLIC = bytes.fromhex(
    "8520f0098930a754748b7ddcb43ef75a0dbf3a0d26381af4eba4a98eaa9b4e6a"
)
RFC_7748_BOB_PRIVATE = bytes.fromhex(
    "5dab087e624a8a4b79e17f8b83800ee66f3bb1292618b6fd1c2f8b27ff88e0eb"
)
RFC_7748_SHARED = bytes.fromhex("4a5d9d5ba4ce2de1728e3bf480350f25e07e21c947d19e3376f09b3c1e161742")

# GCM specification (McGrew and Viega) AES-256 test case 14.
GCM_CASE_14_KEY = bytes(32)
GCM_CASE_14_NONCE = bytes(12)
GCM_CASE_14_PLAINTEXT = bytes(16)
GCM_CASE_14_CIPHERTEXT = bytes.fromhex("cea7403d4d606b6e074ec5d3baf39d18")
GCM_CASE_14_TAG = bytes.fromhex("d0d1c8a799996bf0265b98b5d48ab919")

# GCM specification AES-256 test case 16, which authenticates associated data.
GCM_CASE_16_KEY = bytes.fromhex("feffe9928665731c6d6a8f9467308308feffe9928665731c6d6a8f9467308308")
GCM_CASE_16_NONCE = bytes.fromhex("cafebabefacedbaddecaf888")
GCM_CASE_16_PLAINTEXT = bytes.fromhex(
    "d9313225f88406e5a55909c5aff5269a86a7a9531534f7da2e4c303d8a318a72"
    "1c3c0c95956809532fcf0e2449a6b525b16aedf5aa0de657ba637b39"
)
GCM_CASE_16_AAD = bytes.fromhex("feedfacedeadbeeffeedfacedeadbeefabaddad2")
GCM_CASE_16_CIPHERTEXT = bytes.fromhex(
    "522dc1f099567d07f47f37a32a84427d643a8cdcbfe5c0c97598a2bd2555d1aa"
    "8cb08e48590dbb3da7b08b1056828838c5f61e6393ba7a0abcc9f662"
)
GCM_CASE_16_TAG = bytes.fromhex("76fc6ece0f4e1768cddf8853bb2d551b")

# RFC 5869 appendix A.1 HKDF-SHA256 test vector.
RFC_5869_IKM = bytes.fromhex("0b" * 22)
RFC_5869_SALT = bytes.fromhex("000102030405060708090a0b0c")
RFC_5869_INFO = bytes.fromhex("f0f1f2f3f4f5f6f7f8f9")
RFC_5869_OKM = bytes.fromhex(
    "3cb25f25faacd57a90434f64d0362f2a2d2d0a90cf1a5a4c5db02d56ecc4c5bf34007208d5b887185865"
)


def _workspace_id() -> WorkspaceId:
    return WorkspaceId(str(uuid4()))


def _device_id() -> DeviceId:
    return DeviceId(str(uuid4()))


def _key(workspace_id: WorkspaceId, version: int = 1) -> WorkspaceKey:
    return WorkspaceKey(
        workspace_id=workspace_id,
        version=version,
        material=bytes(range(32)),
        created_at=NOW,
    )


def _device(workspace_id: WorkspaceId, private_key: bytes, *, name: str = "Laptop") -> DeviceKey:
    return DeviceKey(
        device_id=_device_id(),
        workspace_id=workspace_id,
        name=name,
        public_key=X25519DeviceKeyFactory().public_key(private_key),
        trust=DeviceTrust.TRUSTED,
        created_at=NOW,
    )


def _binding(workspace_id: WorkspaceId, *, revision: int = 1, key_version: int = 1):
    return ContentBinding(
        workspace_id=workspace_id,
        object_type="transcript",
        object_id=SyncId(str(uuid4())),
        revision=revision,
        key_version=key_version,
    )


# Primitives -------------------------------------------------------------


def test_x25519_matches_the_rfc_7748_shared_secret():
    from cryptography.hazmat.primitives.asymmetric.x25519 import (
        X25519PrivateKey,
        X25519PublicKey,
    )

    factory = X25519DeviceKeyFactory()
    assert factory.public_key(RFC_7748_ALICE_PRIVATE) == RFC_7748_ALICE_PUBLIC
    shared = X25519PrivateKey.from_private_bytes(RFC_7748_BOB_PRIVATE).exchange(
        X25519PublicKey.from_public_bytes(RFC_7748_ALICE_PUBLIC)
    )
    assert shared == RFC_7748_SHARED


def test_aes_gcm_matches_the_published_specification_vectors():
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    assert (
        AESGCM(GCM_CASE_14_KEY).encrypt(GCM_CASE_14_NONCE, GCM_CASE_14_PLAINTEXT, None)
        == GCM_CASE_14_CIPHERTEXT + GCM_CASE_14_TAG
    )
    assert (
        AESGCM(GCM_CASE_16_KEY).encrypt(
            GCM_CASE_16_NONCE,
            GCM_CASE_16_PLAINTEXT,
            GCM_CASE_16_AAD,
        )
        == GCM_CASE_16_CIPHERTEXT + GCM_CASE_16_TAG
    )


def test_hkdf_matches_the_rfc_5869_vector():
    from cryptography.hazmat.primitives.hashes import SHA256
    from cryptography.hazmat.primitives.kdf.hkdf import HKDF

    derived = HKDF(
        algorithm=SHA256(),
        length=len(RFC_5869_OKM),
        salt=RFC_5869_SALT,
        info=RFC_5869_INFO,
    ).derive(RFC_5869_IKM)
    assert derived == RFC_5869_OKM


# Domain -----------------------------------------------------------------


def test_associated_data_separates_fields_unambiguously():
    workspace_id = _workspace_id()
    object_id = SyncId(str(uuid4()))
    first = ContentBinding(
        workspace_id=workspace_id,
        object_type="ab",
        object_id=object_id,
        revision=1,
        key_version=1,
    )
    second = ContentBinding(
        workspace_id=workspace_id,
        object_type="a",
        object_id=object_id,
        revision=1,
        key_version=1,
    )
    assert first.associated_data() != second.associated_data()
    assert first.associated_data() == first.associated_data()


def test_domain_rejects_malformed_key_material():
    workspace_id = _workspace_id()
    with pytest.raises(ValueError):
        WorkspaceKey(workspace_id=workspace_id, version=1, material=b"short", created_at=NOW)
    with pytest.raises(ValueError):
        WorkspaceKey(
            workspace_id=workspace_id,
            version=0,
            material=bytes(32),
            created_at=NOW,
        )
    with pytest.raises(ValueError):
        DeviceKey(
            device_id=_device_id(),
            workspace_id=workspace_id,
            name="Laptop",
            public_key=bytes(31),
            trust=DeviceTrust.TRUSTED,
            created_at=NOW,
        )
    with pytest.raises(ValueError):
        DeviceKey(
            device_id=_device_id(),
            workspace_id=workspace_id,
            name="Laptop",
            public_key=bytes(32),
            trust=DeviceTrust.REVOKED,
            created_at=NOW,
        )
    with pytest.raises(ValueError):
        ContentBinding(
            workspace_id=workspace_id,
            object_type=" ",
            object_id=SyncId(str(uuid4())),
            revision=1,
            key_version=1,
        )
    with pytest.raises(ValueError):
        EncryptedObject(binding=_binding(workspace_id), nonce=bytes(11), ciphertext=bytes(32))
    with pytest.raises(ValueError):
        EncryptedObject(binding=_binding(workspace_id), nonce=bytes(12), ciphertext=bytes(16))


def test_domain_rejects_malformed_identity_and_timestamps():
    workspace_id = _workspace_id()
    naive = datetime(2026, 1, 5, 9, 30)
    public_key = X25519DeviceKeyFactory().public_key(
        X25519DeviceKeyFactory().generate_private_key()
    )
    with pytest.raises(ValueError):
        DeviceKey(
            device_id=_device_id(),
            workspace_id=workspace_id,
            name="  ",
            public_key=public_key,
            trust=DeviceTrust.TRUSTED,
            created_at=NOW,
        )
    with pytest.raises(ValueError):
        DeviceKey(
            device_id=DeviceId("not-a-uuid"),
            workspace_id=workspace_id,
            name="Laptop",
            public_key=public_key,
            trust=DeviceTrust.TRUSTED,
            created_at=NOW,
        )
    with pytest.raises(ValueError):
        DeviceKey(
            device_id=_device_id(),
            workspace_id=workspace_id,
            name="Laptop",
            public_key=public_key,
            trust=DeviceTrust.TRUSTED,
            created_at=naive,
        )
    with pytest.raises(ValueError):
        DeviceKey(
            device_id=_device_id(),
            workspace_id=workspace_id,
            name="Laptop",
            public_key=public_key,
            trust=DeviceTrust.REVOKED,
            created_at=NOW,
            revoked_at=naive,
        )
    with pytest.raises(ValueError):
        ContentBinding(
            workspace_id=workspace_id,
            object_type="transcript",
            object_id=SyncId(str(uuid4())),
            revision=0,
            key_version=1,
        )
    with pytest.raises(ValueError):
        WorkspaceKey(
            workspace_id=workspace_id,
            version=1,
            material=bytes(32),
            created_at=naive,
        )


def test_envelope_and_recovery_bundle_invariants():
    workspace_id = _workspace_id()
    wrapper = X25519KeyWrapper()
    recovery = wrapper.wrap_for_recovery(_key(workspace_id), "CODE")
    assert recovery.is_active is True

    revoked = KeyEnvelope(
        id=recovery.id,
        workspace_id=recovery.workspace_id,
        key_version=recovery.key_version,
        wrapped_key=recovery.wrapped_key,
        created_at=recovery.created_at,
        salt=recovery.salt,
        revoked_at=NOW,
    )
    assert revoked.is_active is False

    with pytest.raises(ValueError):
        KeyEnvelope(
            id=EnvelopeId(str(uuid4())),
            workspace_id=workspace_id,
            key_version=1,
            wrapped_key=b"",
            created_at=NOW,
            salt=bytes(16),
        )
    with pytest.raises(ValueError):
        KeyEnvelope(
            id=EnvelopeId(str(uuid4())),
            workspace_id=workspace_id,
            key_version=1,
            wrapped_key=b"wrapped",
            created_at=NOW,
            recipient_device_id=_device_id(),
            ephemeral_public_key=bytes(31),
            salt=bytes(16),
        )
    with pytest.raises(ValueError):
        KeyEnvelope(
            id=EnvelopeId(str(uuid4())),
            workspace_id=workspace_id,
            key_version=1,
            wrapped_key=b"wrapped",
            created_at=NOW,
            salt=bytes(16),
            revoked_at=datetime(2026, 1, 5, 9, 30),
        )

    device_envelope = wrapper.wrap_for_device(
        _key(workspace_id),
        _device(workspace_id, X25519DeviceKeyFactory().generate_private_key()),
    )
    with pytest.raises(ValueError):
        RecoveryBundle(envelope=device_envelope, recovery_code="CODE")
    with pytest.raises(ValueError):
        RecoveryBundle(envelope=recovery, recovery_code="   ")


def test_secret_material_is_not_exposed_by_repr():
    workspace_id = _workspace_id()
    key = _key(workspace_id)
    assert "material" in repr(key)
    assert "redacted" in repr(key)
    assert key.material.hex() not in repr(key)
    envelope = X25519KeyWrapper().wrap_for_recovery(key, "CODE")
    bundle = RecoveryBundle(envelope=envelope, recovery_code="SECRET-CODE")
    assert "SECRET-CODE" not in repr(bundle)


def test_envelope_invariants_require_matching_recipient_metadata():
    workspace_id = _workspace_id()
    with pytest.raises(ValueError):
        KeyEnvelope(
            id=EnvelopeId(str(uuid4())),
            workspace_id=workspace_id,
            key_version=1,
            wrapped_key=b"wrapped",
            created_at=NOW,
            recipient_device_id=None,
            salt=None,
        )
    with pytest.raises(ValueError):
        KeyEnvelope(
            id=EnvelopeId(str(uuid4())),
            workspace_id=workspace_id,
            key_version=1,
            wrapped_key=b"wrapped",
            created_at=NOW,
            recipient_device_id=_device_id(),
            ephemeral_public_key=None,
            salt=bytes(16),
        )


# Content cipher ---------------------------------------------------------


def test_content_round_trip_and_binding_enforcement():
    workspace_id = _workspace_id()
    key = _key(workspace_id)
    cipher = AesGcmContentCipher()
    binding = _binding(workspace_id)
    encrypted = cipher.encrypt(key, binding, b"meeting transcript")
    assert cipher.decrypt(key, encrypted) == b"meeting transcript"
    assert encrypted.ciphertext != b"meeting transcript"

    rebound = EncryptedObject(
        binding=ContentBinding(
            workspace_id=binding.workspace_id,
            object_type=binding.object_type,
            object_id=binding.object_id,
            revision=binding.revision + 1,
            key_version=binding.key_version,
        ),
        nonce=encrypted.nonce,
        ciphertext=encrypted.ciphertext,
    )
    with pytest.raises(ContentAuthenticationError):
        cipher.decrypt(key, rebound)

    tampered = EncryptedObject(
        binding=binding,
        nonce=encrypted.nonce,
        ciphertext=bytes([encrypted.ciphertext[0] ^ 0x01]) + encrypted.ciphertext[1:],
    )
    with pytest.raises(ContentAuthenticationError):
        cipher.decrypt(key, tampered)


def test_content_cipher_rejects_mismatched_keys():
    workspace_id = _workspace_id()
    cipher = AesGcmContentCipher()
    key = _key(workspace_id)
    with pytest.raises(ValueError):
        cipher.encrypt(key, _binding(_workspace_id()), b"payload")
    with pytest.raises(ValueError):
        cipher.encrypt(key, _binding(workspace_id, key_version=2), b"payload")
    encrypted = cipher.encrypt(key, _binding(workspace_id), b"payload")
    with pytest.raises(ContentAuthenticationError):
        cipher.decrypt(_key(workspace_id, version=2), encrypted)


def test_content_nonces_are_unique_per_encryption():
    workspace_id = _workspace_id()
    key = _key(workspace_id)
    cipher = AesGcmContentCipher()
    binding = _binding(workspace_id)
    nonces = {cipher.encrypt(key, binding, b"payload").nonce for _ in range(32)}
    assert len(nonces) == 32


# Key wrapping -----------------------------------------------------------


def test_device_wrapping_round_trip_and_rejections():
    workspace_id = _workspace_id()
    factory = X25519DeviceKeyFactory()
    wrapper = X25519KeyWrapper()
    private_key = factory.generate_private_key()
    device = _device(workspace_id, private_key)
    key = _key(workspace_id)

    envelope = wrapper.wrap_for_device(key, device)
    assert envelope.wrapped_key != key.material
    assert wrapper.unwrap_for_device(envelope, private_key).material == key.material

    other_private = factory.generate_private_key()
    with pytest.raises(KeyUnwrapError):
        wrapper.unwrap_for_device(envelope, other_private)

    truncated = KeyEnvelope(
        id=envelope.id,
        workspace_id=envelope.workspace_id,
        key_version=envelope.key_version,
        wrapped_key=envelope.wrapped_key[:8],
        created_at=envelope.created_at,
        recipient_device_id=envelope.recipient_device_id,
        ephemeral_public_key=envelope.ephemeral_public_key,
        salt=envelope.salt,
    )
    with pytest.raises(KeyUnwrapError):
        wrapper.unwrap_for_device(truncated, private_key)
    with pytest.raises(KeyUnwrapError):
        wrapper.unwrap_for_device(envelope, b"not-a-key")

    without_salt = KeyEnvelope(
        id=envelope.id,
        workspace_id=envelope.workspace_id,
        key_version=envelope.key_version,
        wrapped_key=envelope.wrapped_key,
        created_at=envelope.created_at,
        recipient_device_id=envelope.recipient_device_id,
        ephemeral_public_key=envelope.ephemeral_public_key,
        salt=None,
    )
    with pytest.raises(KeyUnwrapError):
        wrapper.unwrap_for_device(without_salt, private_key)


def test_device_wrapping_refuses_foreign_and_revoked_recipients():
    workspace_id = _workspace_id()
    factory = X25519DeviceKeyFactory()
    wrapper = X25519KeyWrapper()
    private_key = factory.generate_private_key()
    key = _key(workspace_id)

    foreign = _device(_workspace_id(), private_key)
    with pytest.raises(ValueError):
        wrapper.wrap_for_device(key, foreign)

    revoked = DeviceKey(
        device_id=_device_id(),
        workspace_id=workspace_id,
        name="Old laptop",
        public_key=factory.public_key(private_key),
        trust=DeviceTrust.REVOKED,
        created_at=NOW,
        revoked_at=NOW,
    )
    with pytest.raises(ValueError):
        wrapper.wrap_for_device(key, revoked)


def test_recovery_wrapping_round_trip_and_wrong_code():
    workspace_id = _workspace_id()
    wrapper = X25519KeyWrapper()
    key = _key(workspace_id)
    envelope = wrapper.wrap_for_recovery(key, "CORRECT-CODE")
    assert envelope.is_recovery
    assert wrapper.unwrap_for_recovery(envelope, "CORRECT-CODE").material == key.material
    with pytest.raises(KeyUnwrapError):
        wrapper.unwrap_for_recovery(envelope, "WRONG-CODE")


def test_envelope_kinds_cannot_be_crossed():
    workspace_id = _workspace_id()
    wrapper = X25519KeyWrapper()
    factory = X25519DeviceKeyFactory()
    private_key = factory.generate_private_key()
    key = _key(workspace_id)
    device_envelope = wrapper.wrap_for_device(key, _device(workspace_id, private_key))
    recovery_envelope = wrapper.wrap_for_recovery(key, "CODE")
    with pytest.raises(KeyUnwrapError):
        wrapper.unwrap_for_device(recovery_envelope, private_key)
    with pytest.raises(KeyUnwrapError):
        wrapper.unwrap_for_recovery(device_envelope, "CODE")


def test_unwrapping_rejects_unexpected_key_length():
    workspace_id = _workspace_id()
    wrapper = X25519KeyWrapper()
    short = WorkspaceKey(
        workspace_id=workspace_id,
        version=1,
        material=bytes(32),
        created_at=NOW,
    )
    envelope = wrapper.wrap_for_recovery(short, "CODE")
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    from collective_mindgraph.infrastructure.security.key_wrapping import (
        WRAP_NONCE_BYTES,
        _recovery_info,
        _scrypt,
    )

    assert envelope.salt is not None
    nonce = envelope.wrapped_key[:WRAP_NONCE_BYTES]
    info = _recovery_info(workspace_id, 1)
    resealed = AESGCM(_scrypt("CODE", envelope.salt)).encrypt(nonce, bytes(16), info)
    mismatched = KeyEnvelope(
        id=envelope.id,
        workspace_id=envelope.workspace_id,
        key_version=envelope.key_version,
        wrapped_key=nonce + resealed,
        created_at=envelope.created_at,
        salt=envelope.salt,
    )
    with pytest.raises(KeyUnwrapError):
        wrapper.unwrap_for_recovery(mismatched, "CODE")


# Recovery codes ---------------------------------------------------------


def test_recovery_codes_are_grouped_normalized_and_checksummed():
    factory = ChecksummedRecoveryCodeFactory()
    code = factory.generate()
    assert "-" in code
    normalized = factory.normalize(code)
    assert normalized == factory.normalize(code.lower().replace("-", " "))
    assert len(normalized) == 54
    assert factory.normalize(normalized) == normalized


def test_recovery_codes_reject_typos_and_malformed_input():
    factory = ChecksummedRecoveryCodeFactory()
    normalized = factory.normalize(factory.generate())
    with pytest.raises(InvalidRecoveryCodeError):
        factory.normalize(normalized[:-1])
    with pytest.raises(InvalidRecoveryCodeError):
        factory.normalize("!" * 54)
    flipped = "0" if normalized[0] != "0" else "1"
    with pytest.raises(InvalidRecoveryCodeError):
        factory.normalize(flipped + normalized[1:])


def test_recovery_code_aliases_follow_crockford_rules():
    factory = ChecksummedRecoveryCodeFactory(entropy_source=lambda size: bytes(size))
    code = factory.normalize(factory.generate())
    assert factory.normalize(code.replace("0", "O").replace("1", "I")) == code


def test_recovery_codes_carry_full_entropy():
    factory = ChecksummedRecoveryCodeFactory()
    codes = {factory.normalize(factory.generate()) for _ in range(64)}
    assert len(codes) == 64


# Device secret store ----------------------------------------------------


def test_protected_file_store_round_trip_and_deletion(tmp_path: Path):
    store = ProtectedFileSecretStore(tmp_path / "secrets")
    assert store.load("device-private-key/a") is None
    store.store("device-private-key/a", b"private-material")
    assert store.load("device-private-key/a") == b"private-material"
    store.store("device-private-key/a", b"rotated-material")
    assert store.load("device-private-key/a") == b"rotated-material"
    store.delete("device-private-key/a")
    assert store.load("device-private-key/a") is None
    store.delete("device-private-key/a")


def test_protected_file_store_applies_the_platform_seal(tmp_path: Path):
    seals: list[bytes] = []

    def seal(payload: bytes) -> bytes:
        seals.append(payload)
        return b"sealed:" + payload

    def unseal(payload: bytes) -> bytes:
        return payload.removeprefix(b"sealed:")

    store = ProtectedFileSecretStore(tmp_path, seal=seal, unseal=unseal, protected=True)
    store.store("name", b"secret")
    assert store.protected is True
    assert seals == [b"secret"]
    stored = next(tmp_path.glob("*.secret")).read_bytes()
    assert stored == b"sealed:secret"
    assert b"secret" != stored
    assert store.load("name") == b"secret"


def test_protected_file_store_validates_inputs(tmp_path: Path):
    store = ProtectedFileSecretStore(tmp_path)
    with pytest.raises(ValueError):
        store.store("name", b"")
    with pytest.raises(ValueError):
        store.store("  ", b"secret")


def test_protected_file_store_reports_unreadable_material(tmp_path: Path):
    def unseal(payload: bytes) -> bytes:
        raise OSError("sealed material is unreadable")

    store = ProtectedFileSecretStore(tmp_path, unseal=unseal)
    store.store("name", b"secret")
    with pytest.raises(DeviceSecretUnavailableError):
        store.load("name")


def test_device_secret_store_factory_reports_platform_protection(tmp_path: Path):
    store = create_device_secret_store(tmp_path / "device_secrets")
    assert store.protected is (sys.platform == "win32")
    assert create_device_secret_store(tmp_path, platform="win32").protected is True
    assert create_device_secret_store(tmp_path, platform="linux").protected is False


@pytest.mark.skipif(sys.platform != "win32", reason="Windows DPAPI is not available.")
def test_windows_dpapi_round_trip(tmp_path: Path):
    store = create_device_secret_store(tmp_path / "device_secrets")
    store.store("device-private-key/win", b"private-material")
    sealed = next((tmp_path / "device_secrets").glob("*.secret")).read_bytes()
    assert b"private-material" not in sealed
    assert store.load("device-private-key/win") == b"private-material"


# Envelope persistence ---------------------------------------------------


@pytest.fixture()
def database(tmp_path: Path) -> SqliteDatabase:
    database = SqliteDatabase(tmp_path / "canonical.sqlite3")
    initialize_schema(database)
    return database


def _local_workspace_id(database: SqliteDatabase) -> WorkspaceId:
    with database.connect() as connection:
        row = connection.execute("SELECT id FROM workspaces WHERE is_local = 1").fetchone()
    return WorkspaceId(str(row[0]))


def test_store_persists_devices_without_disturbing_current_device(database: SqliteDatabase):
    store = SqliteKeyEnvelopeStore(database)
    workspace_id = _local_workspace_id(database)
    current = store.current_device_id()
    assert current is not None
    assert store.get_device(current) is None

    factory = X25519DeviceKeyFactory()
    device = DeviceKey(
        device_id=current,
        workspace_id=workspace_id,
        name="This device",
        public_key=factory.public_key(factory.generate_private_key()),
        trust=DeviceTrust.LOCAL,
        created_at=NOW,
    )
    store.register_device(device)
    assert store.current_device_id() == current
    stored = store.get_device(current)
    assert stored is not None
    assert stored.public_key == device.public_key
    assert stored.trust is DeviceTrust.LOCAL
    assert store.list_devices(workspace_id) == (stored,)

    store.register_device(
        DeviceKey(
            device_id=current,
            workspace_id=workspace_id,
            name="Renamed device",
            public_key=device.public_key,
            trust=DeviceTrust.TRUSTED,
            created_at=NOW,
        )
    )
    renamed = store.get_device(current)
    assert renamed is not None
    assert renamed.name == "Renamed device"
    assert store.current_device_id() == current


def test_store_replaces_envelopes_and_tracks_revocation(database: SqliteDatabase):
    store = SqliteKeyEnvelopeStore(database)
    workspace_id = _local_workspace_id(database)
    wrapper = X25519KeyWrapper()
    factory = X25519DeviceKeyFactory()
    private_key = factory.generate_private_key()
    device = _device(workspace_id, private_key)
    store.register_device(device)

    assert store.latest_key_version(workspace_id) == 0
    assert store.active_envelope_for_device(workspace_id, device.device_id) is None
    assert store.active_recovery_envelope(workspace_id) is None

    key = _key(workspace_id)
    store.save_envelope(wrapper.wrap_for_device(key, device))
    store.save_envelope(wrapper.wrap_for_recovery(key, "CODE"))
    replacement = wrapper.wrap_for_device(key, device)
    store.save_envelope(replacement)

    assert store.latest_key_version(workspace_id) == 1
    active = store.active_envelope_for_device(workspace_id, device.device_id)
    assert active is not None
    assert active.id == replacement.id
    recovery = store.active_recovery_envelope(workspace_id, 1)
    assert recovery is not None
    assert recovery.is_recovery

    rotated = _key(workspace_id, version=2)
    store.save_envelope(wrapper.wrap_for_device(rotated, device))
    newest = store.active_envelope_for_device(workspace_id, device.device_id)
    assert newest is not None
    assert newest.key_version == 2
    pinned = store.active_envelope_for_device(workspace_id, device.device_id, 1)
    assert pinned is not None
    assert pinned.key_version == 1

    assert store.revoke_envelopes_for_device(workspace_id, device.device_id, NOW) == 2
    assert store.active_envelope_for_device(workspace_id, device.device_id) is None
    assert store.active_recovery_envelope(workspace_id) is not None

    store.revoke_device(device.device_id, NOW)
    revoked = store.get_device(device.device_id)
    assert revoked is not None
    assert revoked.trust is DeviceTrust.REVOKED
    assert revoked.revoked_at == NOW
    assert revoked.can_receive_keys is False


# Service ----------------------------------------------------------------


def _service(database: SqliteDatabase, directory: Path) -> WorkspaceKeyService:
    return WorkspaceKeyService(
        envelopes=SqliteKeyEnvelopeStore(database),
        device_secrets=ProtectedFileSecretStore(directory),
        wrapper=X25519KeyWrapper(),
        cipher=AesGcmContentCipher(),
        device_keys=X25519DeviceKeyFactory(),
        recovery_codes=ChecksummedRecoveryCodeFactory(),
        clock=lambda: NOW,
    )


def test_initialize_unlock_and_encrypt_round_trip(database: SqliteDatabase, tmp_path: Path):
    service = _service(database, tmp_path / "secrets")
    workspace_id = _local_workspace_id(database)

    bundle = service.initialize_workspace(workspace_id, "This device")
    assert bundle.recovery_code
    assert bundle.envelope.key_version == 1

    key = service.unlock(workspace_id)
    assert key.version == 1

    encrypted = service.encrypt(
        workspace_id,
        object_type="transcript",
        object_id=SyncId(str(uuid4())),
        revision=3,
        plaintext=b"corrected transcript",
    )
    assert encrypted.binding.revision == 3
    service.lock(workspace_id)
    assert service.decrypt(encrypted) == b"corrected transcript"

    with pytest.raises(KeyManagementError):
        service.initialize_workspace(workspace_id, "This device")


def test_unlock_fails_before_initialization_and_without_private_key(
    database: SqliteDatabase,
    tmp_path: Path,
):
    secrets_directory = tmp_path / "secrets"
    service = _service(database, secrets_directory)
    workspace_id = _local_workspace_id(database)
    with pytest.raises(WorkspaceLockedError):
        service.unlock(workspace_id)
    with pytest.raises(WorkspaceLockedError):
        service.unlock_with_recovery_code(workspace_id, "CODE")

    service.initialize_workspace(workspace_id, "This device")
    service.lock()
    for secret in secrets_directory.glob("*.secret"):
        secret.unlink()
    with pytest.raises(WorkspaceLockedError):
        service.unlock(workspace_id)

    store = SqliteKeyEnvelopeStore(database)
    current = store.current_device_id()
    assert current is not None
    store.revoke_envelopes_for_device(workspace_id, current, NOW)
    with pytest.raises(WorkspaceLockedError):
        service.unlock(workspace_id)

    with database.connect() as connection:
        connection.execute("DELETE FROM key_envelopes WHERE recipient_device_id IS NULL")
    with pytest.raises(WorkspaceLockedError):
        service.unlock_with_recovery_code(workspace_id, "CODE")


def test_recovery_code_restores_access_on_a_new_device(
    database: SqliteDatabase,
    tmp_path: Path,
):
    original = _service(database, tmp_path / "original")
    workspace_id = _local_workspace_id(database)
    bundle = original.initialize_workspace(workspace_id, "This device")
    encrypted = original.encrypt(
        workspace_id,
        object_type="insight",
        object_id=SyncId(str(uuid4())),
        revision=1,
        plaintext=b"decision",
    )

    replacement = _service(database, tmp_path / "replacement")
    with pytest.raises(WorkspaceLockedError):
        replacement.unlock(workspace_id)

    recovered = replacement.unlock_with_recovery_code(workspace_id, bundle.recovery_code)
    assert recovered.version == 1
    assert replacement.decrypt(encrypted) == b"decision"

    replacement.lock()
    assert replacement.unlock(workspace_id).material == recovered.material

    with pytest.raises(InvalidRecoveryCodeError):
        replacement.unlock_with_recovery_code(workspace_id, "not-a-code")


def test_approved_device_receives_the_current_key(database: SqliteDatabase, tmp_path: Path):
    service = _service(database, tmp_path / "secrets")
    workspace_id = _local_workspace_id(database)
    service.initialize_workspace(workspace_id, "This device")
    key = service.unlock(workspace_id)

    factory = X25519DeviceKeyFactory()
    joining_private = factory.generate_private_key()
    joining_id = _device_id()
    envelope = service.approve_device(
        DeviceEnrollmentRequest(
            device_id=joining_id,
            workspace_id=workspace_id,
            name="Desktop",
            public_key=factory.public_key(joining_private),
        )
    )
    assert envelope.recipient_device_id == joining_id
    unwrapped = X25519KeyWrapper().unwrap_for_device(envelope, joining_private)
    assert unwrapped.material == key.material

    store = SqliteKeyEnvelopeStore(database)
    joined = store.get_device(joining_id)
    assert joined is not None
    assert joined.trust is DeviceTrust.TRUSTED


def test_revocation_rotates_the_key_and_locks_out_the_removed_device(
    database: SqliteDatabase,
    tmp_path: Path,
):
    service = _service(database, tmp_path / "secrets")
    workspace_id = _local_workspace_id(database)
    service.initialize_workspace(workspace_id, "This device")
    first_key = service.unlock(workspace_id)

    factory = X25519DeviceKeyFactory()
    removed_private = factory.generate_private_key()
    removed_id = _device_id()
    removed_envelope = service.approve_device(
        DeviceEnrollmentRequest(
            device_id=removed_id,
            workspace_id=workspace_id,
            name="Shared laptop",
            public_key=factory.public_key(removed_private),
        )
    )
    old_content = service.encrypt(
        workspace_id,
        object_type="transcript",
        object_id=SyncId(str(uuid4())),
        revision=1,
        plaintext=b"before removal",
    )

    rotated = service.revoke_device(workspace_id, removed_id)
    assert rotated.envelope.key_version == 2

    store = SqliteKeyEnvelopeStore(database)
    assert store.active_envelope_for_device(workspace_id, removed_id) is None
    assert store.latest_key_version(workspace_id) == 2

    service.lock()
    new_key = service.unlock(workspace_id)
    assert new_key.version == 2
    assert new_key.material != first_key.material

    new_content = service.encrypt(
        workspace_id,
        object_type="transcript",
        object_id=SyncId(str(uuid4())),
        revision=1,
        plaintext=b"after removal",
    )
    assert new_content.binding.key_version == 2
    wrapper = X25519KeyWrapper()
    cipher = AesGcmContentCipher()
    stale_key = wrapper.unwrap_for_device(removed_envelope, removed_private)
    with pytest.raises(ContentAuthenticationError):
        cipher.decrypt(stale_key, new_content)
    # Rotation cannot recall content the removed device already decrypted.
    assert cipher.decrypt(stale_key, old_content) == b"before removal"
    assert service.decrypt(old_content) == b"before removal"


def test_revoked_device_cannot_unlock_or_re_enroll(database: SqliteDatabase, tmp_path: Path):
    service = _service(database, tmp_path / "secrets")
    workspace_id = _local_workspace_id(database)
    service.initialize_workspace(workspace_id, "This device")

    store = SqliteKeyEnvelopeStore(database)
    current = store.current_device_id()
    assert current is not None
    with pytest.raises(KeyManagementError):
        service.revoke_device(workspace_id, current)

    factory = X25519DeviceKeyFactory()
    other_id = _device_id()
    other_public = factory.public_key(factory.generate_private_key())
    service.approve_device(
        DeviceEnrollmentRequest(
            device_id=other_id,
            workspace_id=workspace_id,
            name="Other",
            public_key=other_public,
        )
    )
    service.revoke_device(workspace_id, other_id)
    with pytest.raises(DeviceRevokedError):
        service.approve_device(
            DeviceEnrollmentRequest(
                device_id=other_id,
                workspace_id=workspace_id,
                name="Other",
                public_key=other_public,
            )
        )

    store.revoke_device(current, NOW)
    service.lock()
    with pytest.raises(DeviceRevokedError):
        service.unlock(workspace_id)
    with pytest.raises(DeviceRevokedError):
        service.ensure_device_identity(workspace_id, "This device")


def test_rotation_requires_a_recipient_and_an_initialized_device(
    database: SqliteDatabase,
    tmp_path: Path,
):
    service = _service(database, tmp_path / "secrets")
    workspace_id = _local_workspace_id(database)
    service.initialize_workspace(workspace_id, "This device")
    key = service.unlock(workspace_id)

    with database.connect() as connection:
        connection.execute(
            "UPDATE devices SET trust = 'revoked', revoked_at = ?",
            (NOW.isoformat(),),
        )
    service.lock()
    with pytest.raises(DeviceRevokedError):
        service.rotate(workspace_id)
    with pytest.raises(KeyManagementError):
        service.rotate(workspace_id, previous=key)

    with database.connect() as connection:
        connection.execute("DELETE FROM devices")
    empty = _service(database, tmp_path / "secrets")
    with pytest.raises(KeyManagementError):
        empty.ensure_device_identity(workspace_id, "This device")


def test_engine_context_exposes_workspace_key_service(tmp_path: Path):
    from collective_mindgraph.engine.context import build_engine_context
    from collective_mindgraph.engine.settings import EngineSettings

    settings = EngineSettings(
        data_dir=tmp_path / "data",
        temp_dir=tmp_path / "temp",
        database_path=tmp_path / "collective_mindgraph.sqlite3",
        asr_provider="mock",
        vad_provider="energy",
        diarizer_provider="fallback",
        embedding_provider="mock",
    )
    context = build_engine_context(settings)
    workspace_id = context.workspaces.local_workspace().id
    bundle = context.workspace_keys.initialize_workspace(workspace_id, "This device")
    assert bundle.envelope.key_version == 1
    assert context.workspace_keys.unlock(workspace_id).version == 1
    # The private key is sealed outside SQLite, under the engine data directory.
    assert list((tmp_path / "data" / "device_secrets").glob("*.secret"))
    with context.database.connect() as connection:
        stored = connection.execute("SELECT wrapped_key FROM key_envelopes").fetchall()
    assert stored and all(bytes(row[0]) for row in stored)
