"""
generar_hashes.py — Script de utilidad para generar los hashes bcrypt
que van en .streamlit/secrets.toml.

Uso:
    python generar_hashes.py

No forma parte de la aplicación principal. Ejecutar solo una vez
para configurar las contraseñas.
"""

import bcrypt
import getpass


USUARIOS = [
    ("admin_guayaquil", "Guayaquil — master"),
    ("user_manabi",     "Manabí — regional"),
    ("user_loja",       "Loja — regional"),
    ("user_cuenca",     "Cuenca — regional"),
]


def main() -> None:
    print("=" * 60)
    print("Generador de hashes bcrypt para secrets.toml")
    print("=" * 60)
    print()

    resultados = []
    for usuario, descripcion in USUARIOS:
        print(f"Usuario: {usuario} ({descripcion})")
        password = getpass.getpass("  Contraseña: ")
        hash_bytes = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt())
        hash_str = hash_bytes.decode("utf-8")
        resultados.append((usuario, hash_str))
        print(f"  Hash generado: {hash_str[:20]}...")
        print()

    print("\nCopie las siguientes líneas en .streamlit/secrets.toml:\n")
    print("-" * 60)
    for usuario, hash_str in resultados:
        print(f'[users.{usuario}]')
        print(f'password = "{hash_str}"')
        print()
    print("-" * 60)


if __name__ == "__main__":
    main()
