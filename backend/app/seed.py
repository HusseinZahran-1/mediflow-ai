from app.core.database import SessionLocal
from app.utils.seed import seed_database


def main() -> None:
    with SessionLocal() as db:
        seed_database(db)
    print("MediFlow seed completed")


if __name__ == "__main__":
    main()
