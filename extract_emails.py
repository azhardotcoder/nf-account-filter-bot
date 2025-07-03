import argparse
import re
from pathlib import Path

# Regex used for quick scanning (fast & loose)
RAW_EMAIL_REGEX = re.compile(r'[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}')

# Stricter pattern for final validation (must start with alnum, no leading dot/hyphen)
STRICT_EMAIL_REGEX = re.compile(r'^[A-Za-z0-9][A-Za-z0-9._%+-]*@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$')

def extract_emails_from_file(file_path: Path, domain_filter: str | None = None) -> set[str]:
    """Read a text/mbox file and return a set of valid email addresses.

    domain_filter – if provided (e.g. "example.com") only keep emails that end with that domain.
    """
    emails: set[str] = set()
    with file_path.open('r', encoding='utf-8', errors='ignore') as f:
        for line in f:
            # quick scan first
            for raw in RAW_EMAIL_REGEX.findall(line):
                candidate = raw.strip('<>"\' ').lower()
                if domain_filter and not candidate.endswith('@' + domain_filter.lower()):
                    continue
                if STRICT_EMAIL_REGEX.fullmatch(candidate):
                    emails.add(candidate)
    return emails

def main():
    parser = argparse.ArgumentParser(description="Extract email addresses from text file(s).")
    parser.add_argument('files', nargs='+', help="Input text/mbox files (supports glob patterns, e.g., *.mbox)")
    parser.add_argument('-o', '--output', default='emails.txt', help="Output file to write unique emails (default: emails.txt)")
    parser.add_argument('-d', '--domain', help="Keep only emails ending with this domain (e.g., swppconstructions.in)")
    args = parser.parse_args()

    all_emails: set[str] = set()

    # Expand each provided pattern
    for pattern in args.files:
        for file in Path().glob(pattern):
            if file.is_file():
                extracted = extract_emails_from_file(file, domain_filter=args.domain)
                all_emails.update(extracted)
            else:
                print(f"⚠️  Skipping {file}, not a regular file.")

    if not all_emails:
        print("❌ No email addresses found in the provided file(s).")
        return

    # Write to output
    with open(args.output, 'w', encoding='utf-8') as outfile:
        for email in sorted(all_emails):
            outfile.write(email + '\n')

    print(f"✅ Extracted {len(all_emails)} unique email address(es). Saved to '{args.output}'.")

if __name__ == '__main__':
    main() 