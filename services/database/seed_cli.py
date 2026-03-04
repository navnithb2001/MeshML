#!/usr/bin/env python3
"""
Command-line interface for database seeding operations.

Usage:
    python seed_cli.py seed          # Seed with default values
    python seed_cli.py seed --users 10 --groups 5 --workers 20
    python seed_cli.py clear         # Clear all data (DANGEROUS!)
    python seed_cli.py status        # Show database statistics
"""
import sys
import argparse
import logging
from pathlib import Path

# Add services directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from database.session import get_db_context
from database.seed import DatabaseSeeder

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def seed_command(args):
    """Execute database seeding."""
    logger.info("Starting database seeding...")
    logger.info(f"Parameters: users={args.users}, groups={args.groups}, workers={args.workers}")
    
    with get_db_context() as db:
        seeder = DatabaseSeeder(db)
        stats = seeder.seed_all(
            num_users=args.users,
            num_groups=args.groups,
            num_workers=args.workers
        )
    
    print("\n" + "=" * 60)
    print("✅ Database Seeding Complete!")
    print("=" * 60)
    print(f"Users created:       {stats['users']}")
    print(f"Groups created:      {stats['groups']}")
    print(f"Models created:      {stats['models']}")
    print(f"Workers created:     {stats['workers']}")
    print(f"Jobs created:        {stats['jobs']}")
    print(f"Data batches:        {stats['batches']}")
    print("=" * 60)
    
    return 0


def clear_command(args):
    """Clear all data from database."""
    if not args.force:
        print("⚠️  WARNING: This will DELETE ALL DATA from the database!")
        response = input("Are you sure you want to continue? (yes/no): ")
        if response.lower() != 'yes':
            print("Aborted.")
            return 1
    
    logger.info("Clearing database...")
    
    with get_db_context() as db:
        seeder = DatabaseSeeder(db)
        stats = seeder.clear_all()
    
    print("\n" + "=" * 60)
    print("✅ Database Cleared!")
    print("=" * 60)
    print(f"Users deleted:       {stats['users']}")
    print(f"Groups deleted:      {stats['groups']}")
    print(f"Models deleted:      {stats['models']}")
    print(f"Workers deleted:     {stats['workers']}")
    print(f"Jobs deleted:        {stats['jobs']}")
    print(f"Batches deleted:     {stats['batches']}")
    print("=" * 60)
    
    return 0


def status_command(args):
    """Show database statistics."""
    with get_db_context() as db:
        seeder = DatabaseSeeder(db)
        
        user_count = seeder.user_repo.count()
        group_count = seeder.group_repo.count()
        model_count = seeder.model_repo.count()
        worker_count = seeder.worker_repo.count()
        job_count = seeder.job_repo.count()
        batch_count = seeder.batch_repo.count()
    
    print("\n" + "=" * 60)
    print("📊 Database Status")
    print("=" * 60)
    print(f"Total users:         {user_count}")
    print(f"Total groups:        {group_count}")
    print(f"Total models:        {model_count}")
    print(f"Total workers:       {worker_count}")
    print(f"Total jobs:          {job_count}")
    print(f"Total batches:       {batch_count}")
    print("=" * 60)
    
    return 0


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description='Database seeding CLI for MeshML',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s seed                           # Seed with defaults
  %(prog)s seed --users 10 --workers 20   # Custom counts
  %(prog)s clear --force                  # Clear without confirmation
  %(prog)s status                         # Show database stats
        """
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Command to execute')
    
    # Seed command
    seed_parser = subparsers.add_parser('seed', help='Seed database with test data')
    seed_parser.add_argument(
        '--users',
        type=int,
        default=5,
        help='Number of users to create (default: 5)'
    )
    seed_parser.add_argument(
        '--groups',
        type=int,
        default=3,
        help='Number of groups to create (default: 3)'
    )
    seed_parser.add_argument(
        '--workers',
        type=int,
        default=10,
        help='Number of workers to create (default: 10)'
    )
    seed_parser.set_defaults(func=seed_command)
    
    # Clear command
    clear_parser = subparsers.add_parser('clear', help='Clear all data from database')
    clear_parser.add_argument(
        '--force',
        action='store_true',
        help='Skip confirmation prompt'
    )
    clear_parser.set_defaults(func=clear_command)
    
    # Status command
    status_parser = subparsers.add_parser('status', help='Show database statistics')
    status_parser.set_defaults(func=status_command)
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return 1
    
    try:
        return args.func(args)
    except Exception as e:
        logger.error(f"Error: {e}", exc_info=True)
        return 1


if __name__ == '__main__':
    sys.exit(main())
