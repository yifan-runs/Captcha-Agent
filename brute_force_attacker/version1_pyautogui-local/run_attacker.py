import time
from brute_force_attacker import BruteForceAttacker


def simple_attack():
    """The simplest attack method"""
    print("=== Brute Force Attacker ===")
    print("Please make sure the captcha system is already running!")
    print("The attack will start in 5 seconds, please quickly switch to the captcha window...")

    for i in range(5, 0, -1):
        print(f"{i}...")
        time.sleep(1)

    attacker = BruteForceAttacker()

    # Directly run the sequential attack
    print("Starting sequential grid attack...")
    attacker.set_grid_size(6, 6)  # 6x6 grid
    attacker.run_attack("sequential")

    print("Attack completed!")


def choose_attack():
    """Choose attack method"""
    print("=== Brute Force Attacker ===")
    print("Please choose an attack method:")
    print("1. Sequential grid attack (6x6 grid)")
    print("2. Random attack (8x8 grid)")
    print("3. Spiral attack (starting from the center)")
    print("4. Try all methods")

    choice = input("Please enter your choice (1–4):").strip()

    print("\nAttack will start in 5 seconds, please quickly switch to the captcha window....")
    for i in range(5, 0, -1):
        print(f"{i}...")
        time.sleep(1)

    attacker = BruteForceAttacker()

    if choice == "1":
        print("Start sequential grid attack...")
        attacker.set_grid_size(6, 6)
        attacker.run_attack("sequential")

    elif choice == "2":
        print("Start random attack...")
        attacker.set_grid_size(8, 8)
        attacker.run_attack("random", max_attempts=80)

    elif choice == "3":
        print("Start spiral attack...")
        attacker.run_attack("spiral", center_x=960, center_y=540, radius=300, step=20)

    elif choice == "4":
        print("=== Try all attack methods ===")

        print("\n1. Sequential attack...")
        attacker.set_grid_size(6, 6)
        if attacker.run_attack("sequential"):
            print("Sequential attack succeeded!")
            return

        print("\n2. Random attack...")
        attacker.set_grid_size(8, 8)
        if attacker.run_attack("random", max_attempts=80):
            print("Random attack succeeded")
            return

        print("\n3. Spiral attack...")
        if attacker.run_attack("spiral", center_x=960, center_y=540, radius=300, step=20):
            print("Spiral attack succeeded!")
            return

        print("\nAll attack methods have failed!")

    else:
        print("Invalid choice, using default sequential attack.")
        attacker.set_grid_size(6, 6)
        attacker.run_attack("sequential")


if __name__ == "__main__":
    # Use the simple version (uncomment the line below)
    # simple_attack()

    # Or use the version with selection (uncomment the line below)
    choose_attack()
