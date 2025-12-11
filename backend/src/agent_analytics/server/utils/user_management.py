import json
import secrets
import string
from pathlib import Path
# from passlib.context import CryptContext
import bcrypt

# Initialize password hashing
# pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

class UserManager:
    def __init__(self, file_path="users.json"):
        self.file_path = Path(file_path)
        self.ensure_file_exists()

    def ensure_file_exists(self):
        if not self.file_path.exists():
            self.file_path.write_text(json.dumps({}))

    def read_users(self):
        with open(self.file_path, 'r') as f:
            return json.load(f)

    def write_users(self, users):
        with open(self.file_path, 'w') as f:
            json.dump(users, f, indent=2)

    def generate_password(self, length=12):
        alphabet = string.ascii_letters + string.digits
        return ''.join(secrets.choice(alphabet) for i in range(length))

    def add_user(self, username, email=None, full_name=None, password=None):
        users = self.read_users()
        
        if username in users:
            return {"error": "User already exists"}

        # Generate password if not provided
        if password is None:
            password = self.generate_password()
            pwd_bytes = password.encode('utf-8')

        salt = bcrypt.gensalt()
        # Create user entry
        users[username] = {
            "username": username,
            "email": email,
            "full_name": full_name,
            "hashed_password": bcrypt.hashpw(password=pwd_bytes, salt=salt).decode("utf-8"),
            "disabled": False
        }

        self.write_users(users)
        return {"username": username, "password": password}

    def list_users(self):
        users = self.read_users()
        return [
            {
                "username": username,
                "email": data["email"],
                "full_name": data["full_name"],
                "disabled": data["disabled"]
            }
            for username, data in users.items()
        ]

    def disable_user(self, username):
        users = self.read_users()
        if username not in users:
            return {"error": "User not found"}
        
        users[username]["disabled"] = True
        self.write_users(users)
        return {"message": f"User {username} disabled"}

    def enable_user(self, username):
        users = self.read_users()
        if username not in users:
            return {"error": "User not found"}
        
        users[username]["disabled"] = False
        self.write_users(users)
        return {"message": f"User {username} enabled"}

def main():
    manager = UserManager()
    
    while True:
        print("\nUser Management System")
        print("1. Add User")
        print("2. List Users")
        print("3. Disable User")
        print("4. Enable User")
        print("5. Exit")
        
        choice = input("\nEnter your choice (1-5): ")
        
        if choice == "1":
            username = input("Enter username: ")
            email = input("Enter email (optional): ")
            full_name = input("Enter full name (optional): ")
            
            result = manager.add_user(username, email, full_name)
            if "error" in result:
                print(f"Error: {result['error']}")
            else:
                print(f"\nUser created successfully!")
                print(f"Username: {result['username']}")
                print(f"Generated password: {result['password']}")
                print("\nPlease save this password as it won't be shown again.")
        
        elif choice == "2":
            users = manager.list_users()
            print("\nRegistered Users:")
            for user in users:
                status = "disabled" if user["disabled"] else "active"
                print(f"- {user['username']} ({status})")
                if user["email"]:
                    print(f"  Email: {user['email']}")
                if user["full_name"]:
                    print(f"  Name: {user['full_name']}")
        
        elif choice == "3":
            username = input("Enter username to disable: ")
            result = manager.disable_user(username)
            print(result.get("message", result.get("error")))
        
        elif choice == "4":
            username = input("Enter username to enable: ")
            result = manager.enable_user(username)
            print(result.get("message", result.get("error")))
        
        elif choice == "5":
            break
        
        else:
            print("Invalid choice. Please try again.")

if __name__ == "__main__":
    main()