# List all installed packages in current environment
# import pkg_resources

# installed = pkg_resources.working_set
# for package in sorted(installed, key=lambda x: x.project_name.lower()):
#     print(f"{package.project_name}=={package.version}")

import ast
import importlib
import pkg_resources

def list_imports_from_file(file_path):
    with open(file_path, "r", encoding="utf-8") as f:
        tree = ast.parse(f.read(), filename=file_path)

    modules = set()

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                modules.add(alias.name.split('.')[0])
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                modules.add(node.module.split('.')[0])

    return sorted(modules)

def check_installed_versions(modules):
    results = {}
    installed_packages = {pkg.key: pkg.version for pkg in pkg_resources.working_set}

    for module in modules:
        try:
            dist = pkg_resources.get_distribution(module)
            results[module] = dist.version
        except pkg_resources.DistributionNotFound:
            # Try converting module to package name, if needed
            results[module] = "❌ Not Installed"

    return results

# ==== MAIN ====
file_path = "screen_testTIDB.py"  # Change to your script path
imported_modules = list_imports_from_file(file_path)
installed_info = check_installed_versions(imported_modules)

print("\n📦 Imported Modules & Versions:")
for mod, version in installed_info.items():
    print(f"{mod:20} → {version}")


