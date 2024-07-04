import random
import string
import sys


def generate_random_strings(num_strings):
    # Function to generate a random string of length 10 with alphabetic characters
    def generate_random_string():
        return "".join(random.choices(string.ascii_letters, k=10))

    generated_strings = set()
    while len(generated_strings) < num_strings:
        generated_strings.add(generate_random_string())

    return generated_strings


def write_to_file(strings, filename):
    with open(filename, "w") as f:
        f.write("\n".join(strings))


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python generate_random_strings.py <number_of_strings>")
        sys.exit(1)

    num_strings = int(sys.argv[1])

    if num_strings <= 0:
        print("Number of strings must be a positive integer.")
        sys.exit(1)

    generated_strings = generate_random_strings(num_strings)
    write_to_file(generated_strings, "./data/input.txt")

    print(
        f"Generated {num_strings} unique random strings containing only alphabetic characters in input.txt"
    )
