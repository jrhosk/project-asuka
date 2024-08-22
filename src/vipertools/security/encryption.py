import os
import pathlib
import shutil
import getpass
import paramiko
import configparser

from scp import SCPClient
from graphviper.utils import logger


def write_to_config(file: str, credential: str, value: str) -> None:
    logger.debug(f"Writing credential to file: {file}")

    if pathlib.Path(file).exists():
        config = configparser.ConfigParser()
        config.read(file)

        section, entry = credential.split(".")

        config[section][entry] = value

        with open(file, 'w') as configfile:
            config.write(configfile)

    logger.warning("Caution: By writing credentials to file, you are creating a persistent version of the security "
                   "information do not make this file public!")


def get_credentials(persistent=False):
    logger.info("Getting credentials")

    local_path = str(pathlib.Path(__file__).parent.resolve())

    username = input("Username: ")
    password = getpass.getpass()

    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    ssh.connect(
        hostname="ssh.cv.nrao.edu",
        port=22,
        username=username,
        password=password
    )

    with SCPClient(ssh.get_transport()) as scp:
        scp.get(remote_path="/.lustre/cv/users/jhoskins/drive/.keys/", local_path=local_path, recursive=True)

    certificate_path = "/".join((local_path, ".keys"))
    client_id = decrypt(certificate_path=certificate_path)[1]

    if persistent:
        config_path = str(pathlib.Path(__file__).parent.parent.resolve())
        config_file = "/".join((config_path, "graph/.graph/config.cfg"))
        write_to_config(file=config_file, credential="azure.client_id", value=client_id)

    logger.debug(f"Credential directory: {certificate_path}")
    shutil.rmtree(path=certificate_path, ignore_errors=True)

    logger.info(f"Successfully retrieved credentials.")

    ssh.close()

    return client_id


def decrypt(certificate_path=None):
    from Crypto.PublicKey import RSA
    from Crypto.Cipher import AES, PKCS1_OAEP

    if certificate_path is not None:
        pass

    try:
        private_key = RSA.import_key(open(f"{certificate_path}/private.pem").read())

        with open(f"{certificate_path}/encrypted_data.bin", "rb") as f:
            enc_session_key = f.read(private_key.size_in_bytes())
            nonce = f.read(16)
            tag = f.read(16)
            ciphertext = f.read()

        # Decrypt the session key with the private RSA key
        cipher_rsa = PKCS1_OAEP.new(private_key)
        session_key = cipher_rsa.decrypt(enc_session_key)

        # Decrypt the data with the AES session key
        cipher_aes = AES.new(session_key, AES.MODE_EAX, nonce)
        data = cipher_aes.decrypt_and_verify(ciphertext, tag)

        token = data.decode("utf-8")
        key, secret = token.split(":")

        return key, secret

    except Exception as error:
        logger.exception(f"Error: {error}")
        raise Exception(error)


def generate_rsa_key():
    from Crypto.PublicKey import RSA

    if not pathlib.Path(".keys").exists():
        pathlib.Path(".keys").mkdir(parents=True, exist_ok=True)

    key = RSA.generate(2048)
    private_key = key.export_key()
    with open(".keys/private.pem", "wb") as f:
        f.write(private_key)

    public_key = key.publickey().export_key()
    with open(".keys/receiver.pem", "wb") as f:
        f.write(public_key)


def encrypt(key: str, secret: str = ""):
    from Crypto.PublicKey import RSA
    from Crypto.Random import get_random_bytes
    from Crypto.Cipher import AES, PKCS1_OAEP

    generate_rsa_key()
    data = ":".join((key, secret)).encode("utf-8")

    recipient_key = RSA.import_key(open(".keys/receiver.pem").read())
    session_key = get_random_bytes(16)

    # Encrypt the session key with the public RSA key

    cipher_rsa = PKCS1_OAEP.new(recipient_key)
    enc_session_key = cipher_rsa.encrypt(session_key)

    # Encrypt the data with the AES session key

    cipher_aes = AES.new(session_key, AES.MODE_EAX)
    ciphertext, tag = cipher_aes.encrypt_and_digest(data)

    with open(".keys/encrypted_data.bin", "wb") as f:
        f.write(enc_session_key)
        f.write(cipher_aes.nonce)
        f.write(tag)
        f.write(ciphertext)
