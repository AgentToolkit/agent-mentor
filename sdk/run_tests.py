# import unittest
import os
import sys
import subprocess
import glob
from dotenv import load_dotenv


def main():

    load_dotenv()

    # Directory where tests are located
    tests_dir = os.path.join(os.path.dirname(__file__), 'tests')

    # Dynamically find all test files matching 'test_*.py'
    test_files = glob.glob(os.path.join(tests_dir, 'test_*.py'))

    if not test_files:
        print("No test files found matching 'test_*.py' in the 'tests' directory.")
        sys.exit(1)

    overall_success = True
    passed_tests = 0
    failed_tests = 0
    total_tests = len(test_files)
    failed_test_files = []

    for test_file in test_files:
        # running in seprate process to prevent tracers from being overidden
        print("---------------------------------------------------------------------- \n")
        print(f"Running test: {test_file}")
        result = subprocess.run(
            [sys.executable, "-W", "ignore", "-m", "unittest", "-v", test_file],
            stdout=sys.stdout,
            stderr=sys.stderr
        )
        if result.returncode != 0:
            overall_success = False
            failed_tests += 1
            failed_test_files.append(test_file)
        else:
            passed_tests += 1

    # Print summary
    print("\n" + "="*50)
    print("TEST RUN SUMMARY")
    print("="*50)
    print(f"Total test files run: {total_tests}")
    print(f"Passed: {passed_tests}")
    print(f"Failed: {failed_tests}")

    if failed_test_files:
        print("\nFailed Test Files:")
        for failed_file in failed_test_files:
            print(f" - {failed_file}")

    print("="*50 + "\n")

    # Exit with 0 if all tests passed, otherwise 1
    exit_code = 0 if overall_success else 1
    sys.exit(exit_code)


if __name__ == '__main__':
    main()
