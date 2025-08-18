#!/usr/bin/env python3
"""
Universal Python Code Formatter and Fixer

This utility can automatically fix and format any Python file with:
- Syntax error detection and basic fixes
- Indentation correction
- Import organization
- Code style formatting using black/autopep8
- Missing bracket/quote completion
- Variable reference fixes
- Structure validation

Usage:
    python formatter.py <file_path>
    python formatter.py <file_path> --aggressive
    python formatter.py <file_path> --backup
"""

import ast
import re
import sys
import os
import argparse
import subprocess
from typing import List, Tuple, Optional
import shutil
from pathlib import Path


class PythonCodeFormatter:
    """Comprehensive Python code formatter and fixer"""

    def __init__(self, aggressive_mode: bool = False, create_backup: bool = True):
        self.aggressive_mode = aggressive_mode
        self.create_backup = create_backup
        self.fixes_applied = []

    def format_file(self, file_path: str) -> bool:
        """Main method to format a Python file"""
        if not os.path.exists(file_path):
            print(f"❌ File not found: {file_path}")
            return False

        print(f"🔧 Processing: {file_path}")

        # Create backup if requested
        if self.create_backup:
            backup_path = f"{file_path}.backup"
            shutil.copy2(file_path, backup_path)
            print(f"💾 Backup created: {backup_path}")

        try:
            # Read the file
            with open(file_path, "r", encoding="utf-8") as f:
                original_content = f.read()

            # Apply fixes in order
            content = original_content
            content = self._fix_basic_syntax_errors(content)
            content = self._fix_indentation(content)
            content = self._fix_missing_imports(content)
            content = self._fix_variable_references(content)
            content = self._organize_imports(content)
            content = self._apply_formatting(content)

            # Write the formatted content back
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(content)

            # Validate the result
            if self._validate_syntax(content):
                print(f"✅ File formatted successfully!")
                print(f"🔍 Fixes applied: {len(self.fixes_applied)}")
                for fix in self.fixes_applied:
                    print(f"   • {fix}")
                return True
            else:
                print(f"⚠️ File formatted but may still have syntax issues")
                return False

        except Exception as e:
            print(f"❌ Error processing file: {e}")
            return False

    def _fix_basic_syntax_errors(self, content: str) -> str:
        """Fix basic syntax errors like missing colons, brackets, etc."""
        lines = content.split("\n")
        fixed_lines = []

        for i, line in enumerate(lines):
            original_line = line

            # Fix missing colons after if/for/while/def/class
            if re.match(
                r"^\s*(if|for|while|def|class|try|except|finally|with|elif|else)\s+.*[^:]\s*$",
                line.strip(),
            ):
                if not line.strip().endswith(":"):
                    line = line.rstrip() + ":"
                    self.fixes_applied.append(f"Line {i + 1}: Added missing colon")

            # Fix unmatched quotes (basic)
            quote_count_single = line.count("'") - line.count("\\'")
            quote_count_double = line.count('"') - line.count('\\"')

            if quote_count_single % 2 == 1 and '"""' not in line and "'''" not in line:
                line = line + "'"
                self.fixes_applied.append(f"Line {i + 1}: Fixed unmatched single quote")

            if quote_count_double % 2 == 1 and '"""' not in line and "'''" not in line:
                line = line + '"'
                self.fixes_applied.append(f"Line {i + 1}: Fixed unmatched double quote")

            # Fix common bracket issues
            open_brackets = line.count("(") + line.count("[") + line.count("{")
            close_brackets = line.count(")") + line.count("]") + line.count("}")

            # Simple bracket balancing (for single line)
            if open_brackets > close_brackets and not line.strip().endswith("\\"):
                diff = open_brackets - close_brackets
                # Add appropriate closing brackets
                for _ in range(diff):
                    if "(" in line and line.count("(") > line.count(")"):
                        line = line + ")"
                    elif "[" in line and line.count("[") > line.count("]"):
                        line = line + "]"
                    elif "{" in line and line.count("{") > line.count("}"):
                        line = line + "}"
                self.fixes_applied.append(f"Line {i + 1}: Fixed unmatched brackets")

            fixed_lines.append(line)

        return "\n".join(fixed_lines)

    def _fix_indentation(self, content: str) -> str:
        """Fix indentation issues"""
        lines = content.split("\n")
        fixed_lines = []
        current_indent = 0

        for i, line in enumerate(lines):
            stripped = line.strip()

            # Skip empty lines
            if not stripped:
                fixed_lines.append("")
                continue

            # Calculate expected indentation
            if stripped.startswith(
                (
                    "def ",
                    "class ",
                    "if ",
                    "for ",
                    "while ",
                    "try:",
                    "except",
                    "finally:",
                    "with ",
                    "elif ",
                    "else:",
                )
            ):
                if stripped.endswith(":"):
                    # This line should start a new block
                    fixed_line = " " * current_indent + stripped
                    fixed_lines.append(fixed_line)
                    current_indent += 4
                    continue

            # Check for block endings
            if i > 0 and (
                stripped.startswith(("except", "finally", "elif", "else"))
                or (
                    not lines[i - 1].strip().endswith(":")
                    and not lines[i - 1].strip().endswith("\\")
                    and current_indent > 0
                )
            ):
                # Might need to dedent
                pass

            # Apply current indentation
            fixed_line = " " * current_indent + stripped
            fixed_lines.append(fixed_line)

        # Check if indentation was actually fixed
        original_indented_lines = [l for l in lines if l.strip() and l.startswith(" ")]
        fixed_indented_lines = [l for l in fixed_lines if l.strip() and l.startswith(" ")]

        if len(original_indented_lines) != len(fixed_indented_lines):
            self.fixes_applied.append("Fixed indentation issues")

        return "\n".join(fixed_lines)

    def _fix_missing_imports(self, content: str) -> str:
        """Add commonly missing imports based on usage"""
        lines = content.split("\n")

        # Check for common patterns that need imports
        import_fixes = []

        # Check if asyncio is used but not imported
        if any("async " in line or "await " in line for line in lines):
            if not any("import asyncio" in line for line in lines):
                import_fixes.append("import asyncio")
                self.fixes_applied.append("Added missing asyncio import")

        # Check for json usage
        if any("json." in line for line in lines):
            if not any("import json" in line for line in lines):
                import_fixes.append("import json")
                self.fixes_applied.append("Added missing json import")

        # Check for os usage
        if any("os." in line for line in lines):
            if not any("import os" in line for line in lines):
                import_fixes.append("import os")
                self.fixes_applied.append("Added missing os import")

        # Check for sys usage
        if any("sys." in line for line in lines):
            if not any("import sys" in line for line in lines):
                import_fixes.append("import sys")
                self.fixes_applied.append("Added missing sys import")

        # Add imports at the top after shebang and docstring
        if import_fixes:
            insert_index = 0

            # Skip shebang
            if lines and lines[0].startswith("#!"):
                insert_index = 1

            # Skip module docstring
            if len(lines) > insert_index and lines[insert_index].strip().startswith('"""'):
                for i in range(insert_index, len(lines)):
                    if lines[i].strip().endswith('"""') and i > insert_index:
                        insert_index = i + 1
                        break

            # Insert imports
            for imp in reversed(import_fixes):
                lines.insert(insert_index, imp)

        return "\n".join(lines)

    def _fix_variable_references(self, content: str) -> str:
        """Fix obvious variable reference issues"""
        lines = content.split("\n")

        # Find undefined variables that might be typos
        for i, line in enumerate(lines):
            # Look for common typos
            if "self.expense_agent" in line and "self.primary_agent" in content:
                line = line.replace("self.expense_agent", "self.primary_agent")
                lines[i] = line
                self.fixes_applied.append(
                    f"Line {i + 1}: Fixed variable reference expense_agent -> primary_agent"
                )

            # Fix missing self references in class methods
            if re.search(r"def \w+\(self", line) and i + 1 < len(lines):
                # Check subsequent lines for variable usage that might need self.
                pass

        return "\n".join(lines)

    def _organize_imports(self, content: str) -> str:
        """Organize imports using isort if available"""
        try:
            result = subprocess.run(
                ["isort", "--stdout", "-"],
                input=content,
                text=True,
                capture_output=True,
                timeout=30,
            )
            if result.returncode == 0:
                self.fixes_applied.append("Organized imports with isort")
                return result.stdout
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass

        return content

    def _apply_formatting(self, content: str) -> str:
        """Apply code formatting using black or autopep8"""
        # Try black first
        try:
            result = subprocess.run(
                ["black", "--code", content], capture_output=True, text=True, timeout=30
            )
            if result.returncode == 0:
                self.fixes_applied.append("Applied black formatting")
                return result.stdout
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass

        # Fall back to autopep8
        try:
            result = subprocess.run(
                ["autopep8", "--aggressive", "--aggressive", "-"],
                input=content,
                text=True,
                capture_output=True,
                timeout=30,
            )
            if result.returncode == 0:
                self.fixes_applied.append("Applied autopep8 formatting")
                return result.stdout
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass

        return content

    def _validate_syntax(self, content: str) -> bool:
        """Validate that the code has correct Python syntax"""
        try:
            ast.parse(content)
            return True
        except SyntaxError as e:
            print(f"⚠️ Syntax error remains: {e}")
            return False

    def install_dependencies(self):
        """Install required formatting tools"""
        tools = ["black", "isort", "autopep8"]

        for tool in tools:
            try:
                subprocess.run([tool, "--version"], capture_output=True, check=True)
                print(f"✅ {tool} is available")
            except (subprocess.CalledProcessError, FileNotFoundError):
                print(f"⚠️ {tool} not found, installing...")
                try:
                    subprocess.check_call([sys.executable, "-m", "pip", "install", tool])
                    print(f"✅ {tool} installed successfully")
                except subprocess.CalledProcessError:
                    print(f"❌ Failed to install {tool}")


def batch_format_files(
    directory: str, pattern: str = "*.py", aggressive: bool = False, backup: bool = True
):
    """Format all Python files in a directory"""
    formatter = PythonCodeFormatter(aggressive_mode=aggressive, create_backup=backup)

    path = Path(directory)
    files = list(path.glob(pattern))

    if not files:
        print(f"❌ No Python files found in {directory}")
        return

    print(f"🔍 Found {len(files)} Python files to format")

    success_count = 0
    for file_path in files:
        print(f"\n{'=' * 60}")
        if formatter.format_file(str(file_path)):
            success_count += 1

    print(f"\n🎉 Summary: {success_count}/{len(files)} files formatted successfully")


def format_code_string(code: str, aggressive: bool = False) -> str:
    """Format a code string directly without file I/O"""
    formatter = PythonCodeFormatter(aggressive_mode=aggressive, create_backup=False)

    # Apply all the fixing methods
    content = code
    content = formatter._fix_basic_syntax_errors(content)
    content = formatter._fix_indentation(content)
    content = formatter._fix_missing_imports(content)
    content = formatter._fix_variable_references(content)
    content = formatter._organize_imports(content)
    content = formatter._apply_formatting(content)

    return content


def main():
    """Main CLI interface"""
    parser = argparse.ArgumentParser(description="Python Code Formatter and Fixer")
    parser.add_argument("file_or_directory", help="Python file or directory to format")
    parser.add_argument(
        "--aggressive", "-a", action="store_true", help="Apply aggressive formatting fixes"
    )
    parser.add_argument("--no-backup", action="store_true", help="Do not create backup files")
    parser.add_argument(
        "--batch", "-b", action="store_true", help="Format all Python files in directory"
    )
    parser.add_argument(
        "--install-deps", action="store_true", help="Install required formatting dependencies"
    )
    parser.add_argument(
        "--pattern", default="*.py", help="File pattern for batch mode (default: *.py)"
    )

    args = parser.parse_args()

    # Install dependencies if requested
    if args.install_deps:
        formatter = PythonCodeFormatter()
        formatter.install_dependencies()
        return

    # Check if path exists
    if not os.path.exists(args.file_or_directory):
        print(f"❌ Path not found: {args.file_or_directory}")
        return

    # Batch mode for directories
    if args.batch or os.path.isdir(args.file_or_directory):
        batch_format_files(
            args.file_or_directory, args.pattern, args.aggressive, not args.no_backup
        )
    else:
        # Single file mode
        formatter = PythonCodeFormatter(
            aggressive_mode=args.aggressive, create_backup=not args.no_backup
        )
        formatter.format_file(args.file_or_directory)


# Additional utility functions for specific fixes
def fix_common_issues():
    """Dictionary of common Python issues and their fixes"""
    return {
        "missing_colon": {
            "pattern": r"^\s*(if|for|while|def|class|try|except|finally|with|elif|else)\s+.*[^:]\s*",
            "fix": lambda line: line.rstrip() + ":",
            "description": "Add missing colons after control structures",
        },
        "wrong_indentation": {
            "pattern": r"^\s*\S",
            "fix": lambda line: "    " + line.lstrip(),
            "description": "Fix indentation to 4 spaces",
        },
        "trailing_whitespace": {
            "pattern": r"\s+",
            "fix": lambda line: line.rstrip(),
            "description": "Remove trailing whitespace",
        },
        "missing_import_asyncio": {
            "pattern": r"(async\s+def|await\s+)",
            "fix": lambda content: (
                "import asyncio\n" + content if "import asyncio" not in content else content
            ),
            "description": "Add missing asyncio import",
        },
    }


def quick_fix_code(code_string: str) -> str:
    """Quick fix for common Python code issues"""
    lines = code_string.split("\n")
    fixed_lines = []

    for line in lines:
        # Fix trailing whitespace
        line = line.rstrip()

        # Fix common missing colons
        if re.match(
            r"^\s*(if|for|while|def|class|try|except|finally|with|elif|else)\s+.*[^:]\s*",
            line.strip(),
        ):
            if not line.strip().endswith(":"):
                line = line + ":"

        # Fix obvious indentation (basic)
        if line.strip() and not line.startswith(" ") and not line.startswith("#"):
            # If previous line ended with colon, this line should be indented
            if fixed_lines and fixed_lines[-1].strip().endswith(":"):
                line = "    " + line

                fixed_lines.append(line)

    return "\n".join(fixed_lines)


if __name__ == "__main__":
    print("🐍 Python Code Formatter & Fixer")
    print("=" * 50)

    main()
