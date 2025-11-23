"""Database seeding script (5+ users)"""
import asyncio
import sys
from pathlib import Path

# Add parent directory to path to import app modules
sys.path.append(str(Path(__file__).parent.parent))

from sqlalchemy import select
from app.database import AsyncSessionLocal
from app.models.user import User
from app.core.security import hash_password


async def seed_users():
    """Seed the database with 5 test users"""

    users_data = [
        {
            "email": "user1@example.com",
            "username": "user1",
            "password": "password123",
            "full_name": "User One"
        },
        {
            "email": "user2@example.com",
            "username": "user2",
            "password": "password123",
            "full_name": "User Two"
        },
        {
            "email": "user3@example.com",
            "username": "user3",
            "password": "password123",
            "full_name": "User Three"
        },
        {
            "email": "user4@example.com",
            "username": "user4",
            "password": "password123",
            "full_name": "User Four"
        },
        {
            "email": "user5@example.com",
            "username": "user5",
            "password": "password123",
            "full_name": "User Five"
        }
    ]

    async with AsyncSessionLocal() as session:
        created_count = 0
        skipped_count = 0

        for user_data in users_data:
            # Check if user already exists
            result = await session.execute(
                select(User).where(User.email == user_data["email"])
            )
            existing_user = result.scalar_one_or_none()

            if existing_user:
                print(f"  ⏭️  User '{user_data['username']}' already exists, skipping...")
                skipped_count += 1
                continue

            # Create new user
            new_user = User(
                email=user_data["email"],
                username=user_data["username"],
                hashed_password=hash_password(user_data["password"]),
                full_name=user_data["full_name"],
                is_active=True
            )

            session.add(new_user)
            print(f"  ✅ Created user '{user_data['username']}' ({user_data['email']})")
            created_count += 1

        # Commit all changes
        await session.commit()

        print(f"\n📊 Summary:")
        print(f"  Created: {created_count} users")
        print(f"  Skipped: {skipped_count} users (already exist)")
        print(f"  Total: {len(users_data)} users")

        if created_count > 0:
            print(f"\n🔐 All users have password: password123")


async def main():
    """Main function to run seeding"""
    print("🌱 Seeding database with test users...\n")

    try:
        await seed_users()
        print("\n✨ Database seeding completed successfully!")
    except Exception as e:
        print(f"\n❌ Error seeding database: {str(e)}")
        raise


if __name__ == "__main__":
    asyncio.run(main())
