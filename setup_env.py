import os
import subprocess
import sys
import venv
import platform

env_name = "registration"
requirements_file = "requirements.txt"

def env_exists(env_path):
    if platform.system() == "Windows":
        return os.path.exists(os.path.join(env_path, "Scripts", "python.exe"))
    else:
        return os.path.exists(os.path.join(env_path, "bin", "python"))

def create_env(env_path):
    print(f"⚙️ Creating virtual environment: {env_path}")
    builder = venv.EnvBuilder(with_pip=True)
    builder.create(env_path)

def install_requirements(env_path):
    pip_path = os.path.join(env_path, "Scripts", "pip") if platform.system() == "Windows" else os.path.join(env_path, "bin", "pip")
    
    if not os.path.exists(requirements_file):
        print("❌ requirements.txt not found in current directory.")
        return
    
    print(f"📦 Installing packages from {requirements_file}...")
    subprocess.check_call([pip_path, "install", "-r", requirements_file])
    print("✅ All dependencies installed.")

def main():
    env_path = os.path.join(os.getcwd(), env_name)

    if env_exists(env_path):
        print(f"✅ Environment '{env_name}' already exists.")
    else:
        create_env(env_path)

    install_requirements(env_path)

if __name__ == "__main__":
    main()
