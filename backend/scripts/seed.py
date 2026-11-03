"""Fill the LOCAL database with clearly fictional sample data.

    python -m scripts.seed

Safe to run twice (it skips what already exists). Refuses to run in production.
Sample accounts use the password from SEED_USER_PASSWORD in your .env.
There is no built-in default password and no admin account."""
import sys
from decimal import Decimal

from sqlalchemy import select

from app.config import get_settings
from app.database import SessionLocal
from app.models import MenuItem, Restaurant, RestaurantStaff, User
from app.security import hash_password

# Each restaurant gets a fictional sample menu item.
_RESTAURANT_DETAILS = [
    ("Saffron & Smoke", "Indian", "Charcoal-grilled kebabs, curries and fresh naan.", True, ("Chicken Tikka Wrap", "Smoky chicken, mint chutney and pickled onion", "8.50", True)),
    ("Noodle Lantern", "Pan-Asian", "Hand-pulled noodles and dumplings.", True, ("Dan Dan Noodles", "Sesame, chili oil and crushed peanuts", "11.00", True)),
    ("Basil & Brick", "Pizza", "Wood-fired pizza and simple salads.", True, ("Margherita", "Tomato, mozzarella and basil", "10.50", True)),
    ("Greenbowl Kitchen", "Healthy", "Grain bowls and juices. Closed for renovation.", False, ("Falafel Bowl", "Quinoa, falafel and tahini", "10.00", True)),
    ("Copper Kettle", "British", "Comforting pies, roasts and seasonal sides.", True, ("Mushroom Pie", "Flaky pastry with herbs and gravy", "9.25", True)),
    ("Cedar & Stone", "Lebanese", "Mezze, grilled plates and warm flatbread.", True, ("Falafel Plate", "Hummus, pickles and fresh flatbread", "10.50", True)),
    ("Bluebird Brunch", "Cafe", "All-day breakfast, pastries and coffee.", True, ("Avocado Toast", "Sourdough, avocado and chili flakes", "8.00", True)),
    ("Tamarind Table", "Thai", "Thai curries, noodles and fragrant rice.", True, ("Green Curry", "Vegetables, coconut milk and jasmine rice", "12.00", True)),
    ("Harbor Fish Co.", "Seafood", "Fish suppers and coastal-inspired sides.", True, ("Crispy Fish Plate", "Battered white fish with lemon slaw", "13.50", True)),
    ("Little Seoul", "Korean", "Korean bowls, barbecue and street snacks.", True, ("Bibimbap", "Rice, vegetables, egg and gochujang", "11.75", True)),
    ("Cactus Moon", "Mexican", "Tacos, burritos and house-made salsa.", True, ("Roasted Veg Tacos", "Three tacos with salsa verde", "9.50", True)),
    ("Olive Grove", "Mediterranean", "Simple Mediterranean plates and fresh salads.", True, ("Halloumi Salad", "Grilled halloumi, greens and citrus dressing", "10.25", True)),
    ("The Dumpling Yard", "Chinese", "Dumplings, rice bowls and warming soups.", True, ("Vegetable Dumplings", "Steamed dumplings with ginger soy dip", "7.75", True)),
    ("Maple & Rye", "Deli", "Sandwiches, soups and baked treats.", True, ("Roast Veg Sandwich", "Roasted vegetables on seeded rye", "8.25", True)),
    ("Spice Route Kitchen", "Pakistani", "Slow-cooked karahi, biryani and fresh roti.", True, ("Chicken Biryani", "Basmati rice with aromatic spices", "12.50", True)),
    ("Pasta Post", "Italian", "Fresh pasta and classic Italian sauces.", True, ("Penne Arrabbiata", "Tomato, garlic and red chili", "10.75", True)),
    ("Sunrise Poke", "Hawaiian", "Poke bowls with bright, fresh toppings.", True, ("Tofu Poke Bowl", "Rice, tofu, cucumber and sesame", "11.25", True)),
    ("Juniper Roastery", "Cafe", "Coffee, light lunches and house-made cakes.", True, ("Tomato Toastie", "Cheddar, tomato and basil on sourdough", "7.50", True)),
    ("Bricklane Burgers", "Burgers", "Smash burgers, fries and thick shakes.", True, ("Classic Smash Burger", "Beef patty, cheddar and house sauce", "12.00", True)),
    ("Coconut Garden", "Sri Lankan", "Rice, curry and coconut-rich island dishes.", True, ("Dhal Curry Bowl", "Red lentils, rice and coconut sambol", "10.00", True)),
]

RESTAURANTS = [
    (name, cuisine, desc, is_open, [menu_item])
    for name, cuisine, desc, is_open, menu_item in _RESTAURANT_DETAILS
]

# Ten fictional customers and one staff account per restaurant.
USERS = [
    (f"customer{number:02d}@gmail.com", f"Customer {number:02d} Sample", "customer", [])
    for number in range(1, 50)
] + [
    (
        f"staff{number:02d}@gmail.com",
        f"Staff {number:02d} Sample",
        "staff",
        [name],
    )
    for number, (name, *_rest) in enumerate(_RESTAURANT_DETAILS, start=1)
]


def main() -> None:
    s = get_settings()
    if s.is_production:
        sys.exit("Refusing to seed sample data when ENVIRONMENT=production.")
    pw = s.seed_user_password
    if not pw or len(pw) < 10 or pw.startswith("change-me"):
        sys.exit("Set SEED_USER_PASSWORD in backend/.env to your own value (10+ characters).")

    with SessionLocal() as db:
        by_name: dict[str, Restaurant] = {}
        for name, cuisine, desc, is_open, items in RESTAURANTS:
            r = db.scalar(select(Restaurant).where(Restaurant.name == name))
            if r is None:
                r = Restaurant(name=name, cuisine=cuisine, description=desc, is_open=is_open)
                db.add(r)
                db.flush()
                for n, d, price, avail in items:
                    db.add(MenuItem(restaurant_id=r.id, name=n, description=d,
                                    price=Decimal(price), is_available=avail))
            by_name[name] = r

        pw_hash = hash_password(pw)
        for email, full_name, role, managed in USERS:
            u = db.scalar(select(User).where(User.email == email))
            if u is None:
                u = User(email=email, full_name=full_name, role=role, password_hash=pw_hash)
                db.add(u)
                db.flush()
                for rname in managed:
                    db.add(RestaurantStaff(user_id=u.id, restaurant_id=by_name[rname].id))
        db.commit()
    print("Seeded sample data. Accounts (password = your SEED_USER_PASSWORD):")
    for email, _, role, managed in USERS:
        print(f"  {role:8} {email}  {', '.join(managed)}")


if __name__ == "__main__":
    main()
