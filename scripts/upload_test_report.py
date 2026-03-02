#!/usr/bin/env python3
"""Upload integration test report to GCS.

Usage:
    python scripts/upload_test_report.py <report_dir> <run_id>

Uploads all files from <report_dir> to:
    gs://everything-hephae/test-reports/<run_id>/

Prints the public URL for the HTML report.
"""

import os
import sys

BUCKET_NAME = "everything-hephae"
GCS_PREFIX = "test-reports"

CONTENT_TYPES = {
    ".html": "text/html",
    ".xml": "application/xml",
    ".json": "application/json",
    ".css": "text/css",
    ".js": "application/javascript",
    ".png": "image/png",
}


def main():
    if len(sys.argv) < 3:
        print(f"Usage: {sys.argv[0]} <report_dir> <run_id>", file=sys.stderr)
        sys.exit(1)

    report_dir = sys.argv[1]
    run_id = sys.argv[2]

    if not os.path.isdir(report_dir):
        print(f"Report directory not found: {report_dir}", file=sys.stderr)
        sys.exit(1)

    try:
        from google.cloud import storage
    except ImportError:
        print("google-cloud-storage not installed, skipping upload", file=sys.stderr)
        sys.exit(1)

    client = storage.Client()
    bucket = client.bucket(BUCKET_NAME)
    prefix = f"{GCS_PREFIX}/{run_id}"
    uploaded = 0

    for filename in sorted(os.listdir(report_dir)):
        filepath = os.path.join(report_dir, filename)
        if not os.path.isfile(filepath):
            continue

        ext = os.path.splitext(filename)[1].lower()
        content_type = CONTENT_TYPES.get(ext, "application/octet-stream")

        blob = bucket.blob(f"{prefix}/{filename}")
        blob.upload_from_filename(filepath, content_type=content_type)
        uploaded += 1
        print(f"  Uploaded: {filename} ({content_type})")

    report_url = f"https://storage.googleapis.com/{BUCKET_NAME}/{prefix}/report.html"
    junit_url = f"https://storage.googleapis.com/{BUCKET_NAME}/{prefix}/junit.xml"

    print(f"\nUploaded {uploaded} file(s) to gs://{BUCKET_NAME}/{prefix}/")
    print(f"\nTEST REPORT: {report_url}")

    if os.path.isfile(os.path.join(report_dir, "junit.xml")):
        print(f"JUnit XML:   {junit_url}")


if __name__ == "__main__":
    main()
