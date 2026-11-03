"""Create a restaurant staff account on purpose (staff can never self-register).

    python -m scripts.create_staff --email owner@yourshop.com --name "Alex Owner" \
        --restaurant "Noodle Lantern"

The password is typed at a hidden prompt: it is never a command-line argument."""
import argparse
import getpass
import sys

from sqlalchemy import select

from app.database import SessionLocal
from app.models import Restaurant, RestaurantStaff, User
from app.security import hash_password


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--email", required=True)
    p.add_argument("--name", required=True)
    p.add_argument("--restaurant", action="append", required=True,
                   help="exact restaurant name (repeat for several)")
    args = p.parse_args()
    email = args.email.strip().lower()

    with SessionLocal() as db:
        restaurants = []
        for name in args.restaurant:
            r = db.scalar(select(Restaurant).where(Restaurant.name == name))
            if r is None:
                sys.exit(f"No restaurant named '{name}'.")
            restaurants.append(r)

        user = db.scalar(select(User).where(User.email == email))
        if user is None:
            pw = getpass.getpass("Password (10+ chars, letters and numbers): ")
            if pw != getpass.getpass("Repeat password: "):
                sys.exit("Passwords did not match.")
            if len(pw) < 10 or not any(c.isalpha() for c in pw) or not any(c.isdigit() for c in pw):
                sys.exit("Password must be 10+ characters with letters and numbers.")
            user = User(email=email, full_name=args.name.strip(), role="staff",
                        password_hash=hash_password(pw))
            db.add(user)
            db.flush()
        elif user.role != "staff":
            sys.exit("That email belongs to a customer account. Use a different email.")

        for r in restaurants:
            if db.get(RestaurantStaff, (user.id, r.id)) is None:
                db.add(RestaurantStaff(user_id=user.id, restaurant_id=r.id))
        db.commit()
    print(f"Staff account ready: {email} -> {', '.join(args.restaurant)}")


if __name__ == "__main__":
    main()
