"""End-to-end user workflows and scenarios"""

from datetime import date
from decimal import Decimal

import pytest
from httpx import AsyncClient


class TestCompleteExpenseWorkflow:
    """Test complete expense sharing workflow from start to finish"""

    @pytest.mark.asyncio
    async def test_create_share_and_settle_expense(self, client: AsyncClient):
        """
        Complete workflow: Register users, create expense, check balances, verify calculations

        Scenario:
        - Alice and Bob register
        - Alice creates a lunch expense of $100, split equally
        - Both users check their balances
        - Verify Alice is owed $50 by Bob
        - Verify Bob owes Alice $50
        """
        # Step 1: Register Alice
        alice_response = await client.post(
            "/api/v1/auth/register",
            json={
                "username": "alice",
                "email": "alice@example.com",
                "password": "SecurePass123!",
                "full_name": "Alice Smith",
            },
        )
        assert alice_response.status_code == 201
        alice_id = alice_response.json()["id"]

        # Step 2: Register Bob
        bob_response = await client.post(
            "/api/v1/auth/register",
            json={
                "username": "bob",
                "email": "bob@example.com",
                "password": "SecurePass123!",
                "full_name": "Bob Johnson",
            },
        )
        assert bob_response.status_code == 201
        bob_id = bob_response.json()["id"]

        # Step 3: Alice logs in
        alice_login = await client.post(
            "/api/v1/auth/login",
            data={"username": "alice", "password": "SecurePass123!"},
        )
        assert alice_login.status_code == 200
        alice_token = alice_login.json()["access_token"]
        alice_headers = {"Authorization": f"Bearer {alice_token}"}

        # Step 4: Bob logs in
        bob_login = await client.post(
            "/api/v1/auth/login",
            data={"username": "bob", "password": "SecurePass123!"},
        )
        assert bob_login.status_code == 200
        bob_token = bob_login.json()["access_token"]
        bob_headers = {"Authorization": f"Bearer {bob_token}"}

        # Step 5: Alice creates a lunch expense
        expense_response = await client.post(
            "/api/v1/expenses",
            json={
                "description": "Team Lunch",
                "total_amount": "100.00",
                "expense_date": str(date.today()),
                "group_name": "Friends",
                "split_type": "EQUAL",
                "participants": [
                    {"user_id": alice_id, "amount_paid": "100.00"},
                    {"user_id": bob_id, "amount_paid": "0.00"},
                ],
            },
            headers=alice_headers,
        )
        assert expense_response.status_code == 201
        expense_data = expense_response.json()
        expense_id = expense_data["id"]

        # Verify equal split: both owe $50
        assert len(expense_data["participants"]) == 2
        assert all(Decimal(p["amount_owed"]) == Decimal("50.00") for p in expense_data["participants"])

        # Step 6: Alice checks her balance summary
        alice_balance_summary = await client.get(
            "/api/v1/balances/summary",
            headers=alice_headers,
        )
        assert alice_balance_summary.status_code == 200
        alice_summary = alice_balance_summary.json()

        # Alice is owed $50 (she paid $100, owes $50)
        assert Decimal(alice_summary["overall_balance"]) == Decimal("50.00")
        assert Decimal(alice_summary["total_owed_to_you"]) == Decimal("50.00")
        assert Decimal(alice_summary["total_you_owe"]) == Decimal("0.00")
        assert alice_summary["num_people_owe_you"] == 1

        # Step 7: Bob checks his balance summary
        bob_balance_summary = await client.get(
            "/api/v1/balances/summary",
            headers=bob_headers,
        )
        assert bob_balance_summary.status_code == 200
        bob_summary = bob_balance_summary.json()

        # Bob owes $50 (he paid $0, owes $50)
        assert Decimal(bob_summary["overall_balance"]) == Decimal("-50.00")
        assert Decimal(bob_summary["total_owed_to_you"]) == Decimal("0.00")
        assert Decimal(bob_summary["total_you_owe"]) == Decimal("50.00")
        assert bob_summary["num_people_you_owe"] == 1

        # Step 8: Alice checks balance with Bob specifically
        alice_bob_balance = await client.get(
            f"/api/v1/balances/user/{bob_id}",
            headers=alice_headers,
        )
        assert alice_bob_balance.status_code == 200
        alice_bob_data = alice_bob_balance.json()
        assert alice_bob_data["type"] == "owes_you"
        assert Decimal(alice_bob_data["amount"]) == Decimal("50.00")
        assert len(alice_bob_data["shared_expenses"]) == 1

        # Step 9: Bob checks balance with Alice (should be symmetric)
        bob_alice_balance = await client.get(
            f"/api/v1/balances/user/{alice_id}",
            headers=bob_headers,
        )
        assert bob_alice_balance.status_code == 200
        bob_alice_data = bob_alice_balance.json()
        assert bob_alice_data["type"] == "you_owe"
        assert Decimal(bob_alice_data["amount"]) == Decimal("50.00")

        # Step 10: Alice retrieves the expense details
        get_expense = await client.get(
            f"/api/v1/expenses/{expense_id}",
            headers=alice_headers,
        )
        assert get_expense.status_code == 200
        assert get_expense.json()["description"] == "Team Lunch"


class TestMultiUserExpenseScenario:
    """Test expenses with multiple users and complex splits"""

    @pytest.mark.asyncio
    async def test_three_person_trip_expenses(self, client: AsyncClient):
        """
        Scenario: Three friends (Alice, Bob, Carol) go on a trip
        - Alice pays for hotel: $300 (split equally)
        - Bob pays for gas: $60 (split equally)
        - Carol pays for food: $90 (split equally)
        - Verify final balances
        """
        # Register users
        users = {}
        for name, email in [
            ("alice", "alice@trip.com"),
            ("bob", "bob@trip.com"),
            ("carol", "carol@trip.com"),
        ]:
            reg = await client.post(
                "/api/v1/auth/register",
                json={
                    "username": name,
                    "email": email,
                    "password": "TripPass123!",
                    "full_name": name.title(),
                },
            )
            assert reg.status_code == 201

            login = await client.post(
                "/api/v1/auth/login",
                data={"username": name, "password": "TripPass123!"},
            )
            assert login.status_code == 200

            users[name] = {
                "id": reg.json()["id"],
                "token": login.json()["access_token"],
                "headers": {"Authorization": f"Bearer {login.json()['access_token']}"},
            }

        # Alice pays for hotel ($300)
        hotel_expense = await client.post(
            "/api/v1/expenses",
            json={
                "description": "Hotel",
                "total_amount": "300.00",
                "expense_date": str(date.today()),
                "group_name": "Trip",
                "split_type": "EQUAL",
                "participants": [
                    {"user_id": users["alice"]["id"], "amount_paid": "300.00"},
                    {"user_id": users["bob"]["id"], "amount_paid": "0.00"},
                    {"user_id": users["carol"]["id"], "amount_paid": "0.00"},
                ],
            },
            headers=users["alice"]["headers"],
        )
        assert hotel_expense.status_code == 201

        # Bob pays for gas ($60)
        gas_expense = await client.post(
            "/api/v1/expenses",
            json={
                "description": "Gas",
                "total_amount": "60.00",
                "expense_date": str(date.today()),
                "group_name": "Trip",
                "split_type": "EQUAL",
                "participants": [
                    {"user_id": users["alice"]["id"], "amount_paid": "0.00"},
                    {"user_id": users["bob"]["id"], "amount_paid": "60.00"},
                    {"user_id": users["carol"]["id"], "amount_paid": "0.00"},
                ],
            },
            headers=users["bob"]["headers"],
        )
        assert gas_expense.status_code == 201

        # Carol pays for food ($90)
        food_expense = await client.post(
            "/api/v1/expenses",
            json={
                "description": "Food",
                "total_amount": "90.00",
                "expense_date": str(date.today()),
                "group_name": "Trip",
                "split_type": "EQUAL",
                "participants": [
                    {"user_id": users["alice"]["id"], "amount_paid": "0.00"},
                    {"user_id": users["bob"]["id"], "amount_paid": "0.00"},
                    {"user_id": users["carol"]["id"], "amount_paid": "90.00"},
                ],
            },
            headers=users["carol"]["headers"],
        )
        assert food_expense.status_code == 201

        # Calculate expected balances:
        # Total: $450, each person should pay $150
        # Alice: paid $300, owes $150 -> net +$150
        # Bob: paid $60, owes $150 -> net -$90
        # Carol: paid $90, owes $150 -> net -$60

        # Check Alice's balance
        alice_summary = await client.get(
            "/api/v1/balances/summary",
            headers=users["alice"]["headers"],
        )
        assert alice_summary.status_code == 200
        alice_data = alice_summary.json()
        assert Decimal(alice_data["overall_balance"]) == Decimal("150.00")
        assert alice_data["num_people_owe_you"] == 2

        # Check Bob's balance
        bob_summary = await client.get(
            "/api/v1/balances/summary",
            headers=users["bob"]["headers"],
        )
        assert bob_summary.status_code == 200
        bob_data = bob_summary.json()
        assert Decimal(bob_data["overall_balance"]) == Decimal("-90.00")

        # Check Carol's balance
        carol_summary = await client.get(
            "/api/v1/balances/summary",
            headers=users["carol"]["headers"],
        )
        assert carol_summary.status_code == 200
        carol_data = carol_summary.json()
        assert Decimal(carol_data["overall_balance"]) == Decimal("-60.00")


class TestPercentageSplitScenario:
    """Test percentage-based split scenarios"""

    @pytest.mark.asyncio
    async def test_business_dinner_percentage_split(self, client: AsyncClient):
        """
        Scenario: Business dinner where senior pays more
        - Alice (senior): pays 70% of $200 = $140
        - Bob (junior): pays 30% of $200 = $60
        - Alice covers the full bill upfront
        """
        # Register users
        alice_reg = await client.post(
            "/api/v1/auth/register",
            json={
                "username": "alice_senior",
                "email": "alice.senior@company.com",
                "password": "SecurePass123!",
                "full_name": "Alice Senior",
            },
        )
        alice_id = alice_reg.json()["id"]

        bob_reg = await client.post(
            "/api/v1/auth/register",
            json={
                "username": "bob_junior",
                "email": "bob.junior@company.com",
                "password": "SecurePass123!",
                "full_name": "Bob Junior",
            },
        )
        bob_id = bob_reg.json()["id"]

        # Alice logs in
        alice_login = await client.post(
            "/api/v1/auth/login",
            data={"username": "alice_senior", "password": "SecurePass123!"},
        )
        alice_headers = {"Authorization": f"Bearer {alice_login.json()['access_token']}"}

        # Bob logs in
        bob_login = await client.post(
            "/api/v1/auth/login",
            data={"username": "bob_junior", "password": "SecurePass123!"},
        )
        bob_headers = {"Authorization": f"Bearer {bob_login.json()['access_token']}"}

        # Create expense with percentage split
        expense = await client.post(
            "/api/v1/expenses",
            json={
                "description": "Business Dinner",
                "total_amount": "200.00",
                "expense_date": str(date.today()),
                "group_name": "Work",
                "split_type": "PERCENTAGE",
                "participants": [
                    {
                        "user_id": alice_id,
                        "amount_paid": "200.00",
                        "percentage": "70.00",
                    },
                    {
                        "user_id": bob_id,
                        "amount_paid": "0.00",
                        "percentage": "30.00",
                    },
                ],
            },
            headers=alice_headers,
        )
        assert expense.status_code == 201
        expense_data = expense.json()

        # Verify splits
        participants = sorted(expense_data["participants"], key=lambda p: Decimal(p["amount_owed"]))
        assert Decimal(participants[0]["amount_owed"]) == Decimal("60.00")  # Bob: 30%
        assert Decimal(participants[1]["amount_owed"]) == Decimal("140.00")  # Alice: 70%

        # Check balances
        # Alice paid $200, owes $140 -> net +$60
        alice_summary = await client.get(
            "/api/v1/balances/summary",
            headers=alice_headers,
        )
        alice_data = alice_summary.json()
        assert Decimal(alice_data["overall_balance"]) == Decimal("60.00")

        # Bob paid $0, owes $60 -> net -$60
        bob_summary = await client.get(
            "/api/v1/balances/summary",
            headers=bob_headers,
        )
        bob_data = bob_summary.json()
        assert Decimal(bob_data["overall_balance"]) == Decimal("-60.00")


class TestManualSplitScenario:
    """Test manual split scenarios"""

    @pytest.mark.asyncio
    async def test_shared_apartment_expenses(self, client: AsyncClient):
        """
        Scenario: Roommates with different room sizes pay different amounts
        - Alice (large room): pays $600 rent
        - Bob (small room): pays $400 rent
        - Total rent: $1000, split manually
        - Carol pays the full rent upfront
        """
        # Register users
        users_data = [
            ("alice_roommate", "alice@apartment.com", "Alice"),
            ("bob_roommate", "bob@apartment.com", "Bob"),
            ("carol_roommate", "carol@apartment.com", "Carol"),
        ]

        users = {}
        for username, email, full_name in users_data:
            reg = await client.post(
                "/api/v1/auth/register",
                json={
                    "username": username,
                    "email": email,
                    "password": "ApartmentPass123!",
                    "full_name": full_name,
                },
            )
            login = await client.post(
                "/api/v1/auth/login",
                data={"username": username, "password": "ApartmentPass123!"},
            )
            users[username] = {
                "id": reg.json()["id"],
                "headers": {"Authorization": f"Bearer {login.json()['access_token']}"},
            }

        # Carol pays the full rent, manual split
        rent_expense = await client.post(
            "/api/v1/expenses",
            json={
                "description": "Monthly Rent",
                "total_amount": "1000.00",
                "expense_date": str(date.today()),
                "group_name": "Apartment",
                "split_type": "MANUAL",
                "participants": [
                    {
                        "user_id": users["alice_roommate"]["id"],
                        "amount_paid": "0.00",
                        "amount_owed": "600.00",
                    },
                    {
                        "user_id": users["bob_roommate"]["id"],
                        "amount_paid": "0.00",
                        "amount_owed": "400.00",
                    },
                    {
                        "user_id": users["carol_roommate"]["id"],
                        "amount_paid": "1000.00",
                        "amount_owed": "0.00",
                    },
                ],
            },
            headers=users["carol_roommate"]["headers"],
        )
        assert rent_expense.status_code == 201

        # Verify Carol is owed $1000
        carol_summary = await client.get(
            "/api/v1/balances/summary",
            headers=users["carol_roommate"]["headers"],
        )
        carol_data = carol_summary.json()
        assert Decimal(carol_data["overall_balance"]) == Decimal("1000.00")
        assert Decimal(carol_data["total_owed_to_you"]) == Decimal("1000.00")

        # Verify Alice owes $600
        alice_summary = await client.get(
            "/api/v1/balances/summary",
            headers=users["alice_roommate"]["headers"],
        )
        alice_data = alice_summary.json()
        assert Decimal(alice_data["overall_balance"]) == Decimal("-600.00")

        # Verify Bob owes $400
        bob_summary = await client.get(
            "/api/v1/balances/summary",
            headers=users["bob_roommate"]["headers"],
        )
        bob_data = bob_summary.json()
        assert Decimal(bob_data["overall_balance"]) == Decimal("-400.00")


class TestExpenseUpdateAndDelete:
    """Test updating and deleting expenses"""

    @pytest.mark.asyncio
    async def test_update_expense_and_recheck_balances(self, client: AsyncClient):
        """
        Scenario: Create expense, check balances, update expense, verify balances change
        """
        # Register users
        alice_reg = await client.post(
            "/api/v1/auth/register",
            json={
                "username": "alice_update",
                "email": "alice.update@example.com",
                "password": "SecurePass123!",
                "full_name": "Alice",
            },
        )
        alice_id = alice_reg.json()["id"]

        bob_reg = await client.post(
            "/api/v1/auth/register",
            json={
                "username": "bob_update",
                "email": "bob.update@example.com",
                "password": "SecurePass123!",
                "full_name": "Bob",
            },
        )
        bob_id = bob_reg.json()["id"]

        # Login
        alice_login = await client.post(
            "/api/v1/auth/login",
            data={"username": "alice_update", "password": "SecurePass123!"},
        )
        alice_headers = {"Authorization": f"Bearer {alice_login.json()['access_token']}"}

        # Create initial expense: $100
        expense = await client.post(
            "/api/v1/expenses",
            json={
                "description": "Lunch",
                "total_amount": "100.00",
                "expense_date": str(date.today()),
                "group_name": "Friends",
                "split_type": "EQUAL",
                "participants": [
                    {"user_id": alice_id, "amount_paid": "100.00"},
                    {"user_id": bob_id, "amount_paid": "0.00"},
                ],
            },
            headers=alice_headers,
        )
        expense_id = expense.json()["id"]

        # Check initial balance
        initial_summary = await client.get(
            "/api/v1/balances/summary",
            headers=alice_headers,
        )
        assert Decimal(initial_summary.json()["overall_balance"]) == Decimal("50.00")

        # Update expense to $200
        update = await client.put(
            f"/api/v1/expenses/{expense_id}",
            json={
                "description": "Expensive Lunch",
                "total_amount": "200.00",
                "expense_date": str(date.today()),
                "group_name": "Friends",
                "split_type": "EQUAL",
                "participants": [
                    {"user_id": alice_id, "amount_paid": "200.00"},
                    {"user_id": bob_id, "amount_paid": "0.00"},
                ],
            },
            headers=alice_headers,
        )
        assert update.status_code == 200

        # Check updated balance (should be $100 now)
        updated_summary = await client.get(
            "/api/v1/balances/summary",
            headers=alice_headers,
        )
        assert Decimal(updated_summary.json()["overall_balance"]) == Decimal("100.00")

        # Delete expense
        delete = await client.delete(
            f"/api/v1/expenses/{expense_id}",
            headers=alice_headers,
        )
        assert delete.status_code == 204

        # Check balance is now zero
        final_summary = await client.get(
            "/api/v1/balances/summary",
            headers=alice_headers,
        )
        assert Decimal(final_summary.json()["overall_balance"]) == Decimal("0.00")


class TestUserSearchAndListing:
    """Test user search and listing functionality"""

    @pytest.mark.asyncio
    async def test_search_users_for_expense_participants(self, client: AsyncClient):
        """
        Scenario: User wants to add friends to an expense and searches for them
        """
        # Register several users
        users = ["alice_search", "bob_search", "charlie_search", "dave_search"]
        for username in users:
            await client.post(
                "/api/v1/auth/register",
                json={
                    "username": username,
                    "email": f"{username}@example.com",
                    "password": "SecurePass123!",
                    "full_name": username.replace("_", " ").title(),
                },
            )

        # Login as alice
        alice_login = await client.post(
            "/api/v1/auth/login",
            data={"username": "alice_search", "password": "SecurePass123!"},
        )
        alice_headers = {"Authorization": f"Bearer {alice_login.json()['access_token']}"}

        # Search for "bob"
        search_bob = await client.get(
            "/api/v1/users?search=bob_search",
            headers=alice_headers,
        )
        assert search_bob.status_code == 200
        search_results = search_bob.json()
        assert len(search_results["items"]) >= 1
        assert any(user["username"] == "bob_search" for user in search_results["items"])

        # List all users with pagination
        all_users = await client.get(
            "/api/v1/users?page=1&page_size=10",
            headers=alice_headers,
        )
        assert all_users.status_code == 200
        assert all_users.json()["pagination"]["page"] == 1
        assert len(all_users.json()["items"]) >= 4
