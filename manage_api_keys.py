# -*- coding: utf-8 -*-
"""
API Keys Manager CLI - Interface de linha de comando para gerir API keys
"""

import sys
from pathlib import Path

# Adicionar root ao path
root_dir = Path(__file__).parent
sys.path.insert(0, str(root_dir))

import argparse
import logging
from services.api_auth import get_api_key_manager, AccessLevel

logging.basicConfig(
    level=logging.INFO,
    format="%(message)s"
)
logger = logging.getLogger(__name__)


def cmd_generate(args):
    """Gera nova API key"""
    manager = get_api_key_manager()

    # Parse access level
    try:
        access_level = AccessLevel(args.level)
    except ValueError:
        logger.error(f"❌ Nivel de acesso invalido: {args.level}")
        logger.error(f"   Valores validos: {', '.join([l.value for l in AccessLevel])}")
        return 1

    # Gerar key
    key = manager.generate_key(
        name=args.name,
        access_level=access_level,
        expires_in_days=args.expires_days,
        description=args.description or ""
    )

    logger.info(f"\n✅ Nova API key gerada com sucesso!")
    logger.info(f"")
    logger.info(f"Nome: {args.name}")
    logger.info(f"Nivel: {access_level.value}")
    logger.info(f"Key: {key}")
    logger.info(f"")
    logger.info(f"⚠️  IMPORTANTE: Guarde esta key num local seguro!")
    logger.info(f"   Esta e a unica vez que sera mostrada.")
    logger.info(f"")
    logger.info(f"💡 Para usar:")
    logger.info(f"   curl -H 'Authorization: Bearer {key}' http://localhost:5678/predict")
    logger.info(f"")

    return 0


def cmd_list(args):
    """Lista API keys"""
    manager = get_api_key_manager()

    keys = manager.list_keys(include_disabled=args.all)

    if not keys:
        logger.info("Nenhuma API key encontrada.")
        return 0

    logger.info(f"\n📋 API Keys ({len(keys)} total):")
    logger.info(f"{'='*80}")

    for key_info in keys:
        status = "✅" if key_info['enabled'] else "❌"
        logger.info(f"\n{status} {key_info['name']}")
        logger.info(f"   Prefix: {key_info['key_prefix']}")
        logger.info(f"   Nivel: {key_info['access_level']}")
        logger.info(f"   Criada: {key_info['created_at']}")
        if key_info['expires_at']:
            logger.info(f"   Expira: {key_info['expires_at']}")
        logger.info(f"   Usos: {key_info['usage_count']}")
        if key_info['last_used_at']:
            logger.info(f"   Ultimo uso: {key_info['last_used_at']}")
        if key_info['description']:
            logger.info(f"   Descricao: {key_info['description']}")

    logger.info(f"\n{'='*80}\n")

    return 0


def cmd_revoke(args):
    """Revoga (desativa) uma API key"""
    manager = get_api_key_manager()

    # Encontrar key por prefix
    full_key = None
    for key in manager.keys.keys():
        if key.startswith(args.key_prefix):
            full_key = key
            break

    if not full_key:
        logger.error(f"❌ API key nao encontrada com prefix: {args.key_prefix}")
        return 1

    # Revogar
    success = manager.revoke_key(full_key)

    if success:
        logger.info(f"✅ API key revogada com sucesso!")
        logger.info(f"   A key nao podera mais ser usada.")
    else:
        logger.error(f"❌ Falha ao revogar key")
        return 1

    return 0


def cmd_delete(args):
    """Remove completamente uma API key"""
    manager = get_api_key_manager()

    # Encontrar key por prefix
    full_key = None
    for key in manager.keys.keys():
        if key.startswith(args.key_prefix):
            full_key = key
            break

    if not full_key:
        logger.error(f"❌ API key nao encontrada com prefix: {args.key_prefix}")
        return 1

    # Confirmar
    if not args.force:
        logger.info(f"⚠️  Tem certeza que quer REMOVER permanentemente esta key?")
        logger.info(f"   Prefix: {args.key_prefix}")
        response = input("   Digite 'sim' para confirmar: ")

        if response.lower() != 'sim':
            logger.info("Operacao cancelada.")
            return 0

    # Remover
    success = manager.delete_key(full_key)

    if success:
        logger.info(f"✅ API key removida permanentemente!")
    else:
        logger.error(f"❌ Falha ao remover key")
        return 1

    return 0


def main():
    parser = argparse.ArgumentParser(
        description="NSP Plugin - API Keys Manager",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemplos:
  # Gerar nova key standard
  python manage_api_keys.py generate "Plugin Lightroom" --level standard

  # Gerar key admin com expiracao
  python manage_api_keys.py generate "Admin Tool" --level admin --expires-days 90

  # Listar todas as keys
  python manage_api_keys.py list

  # Revogar key (desativar)
  python manage_api_keys.py revoke nsp_abc123

  # Remover key permanentemente
  python manage_api_keys.py delete nsp_abc123 --force
        """
    )

    subparsers = parser.add_subparsers(dest='command', help='Comando')

    # Comando: generate
    parser_gen = subparsers.add_parser('generate', help='Gerar nova API key')
    parser_gen.add_argument('name', help='Nome descritivo da key')
    parser_gen.add_argument('--level', default='standard',
                            choices=[l.value for l in AccessLevel],
                            help='Nivel de acesso (default: standard)')
    parser_gen.add_argument('--expires-days', type=int,
                            help='Dias ate expirar (omitir = sem expiracao)')
    parser_gen.add_argument('--description', help='Descricao opcional')
    parser_gen.set_defaults(func=cmd_generate)

    # Comando: list
    parser_list = subparsers.add_parser('list', help='Listar API keys')
    parser_list.add_argument('--all', action='store_true',
                             help='Incluir keys desativadas')
    parser_list.set_defaults(func=cmd_list)

    # Comando: revoke
    parser_revoke = subparsers.add_parser('revoke', help='Revogar (desativar) API key')
    parser_revoke.add_argument('key_prefix', help='Prefix da key (ex: nsp_abc123...)')
    parser_revoke.set_defaults(func=cmd_revoke)

    # Comando: delete
    parser_delete = subparsers.add_parser('delete', help='Remover API key permanentemente')
    parser_delete.add_argument('key_prefix', help='Prefix da key (ex: nsp_abc123...)')
    parser_delete.add_argument('--force', action='store_true',
                               help='Nao pedir confirmacao')
    parser_delete.set_defaults(func=cmd_delete)

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
