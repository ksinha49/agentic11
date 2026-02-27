"""FileExportService — step 2100 EXPORT_FILES (subroutine-exportingfiles.do)."""

from __future__ import annotations

# TODO: Implement file export
# Split by planhold status: PayrollALL (not held), HOLD-PayrollALL (held)
# Always: BadSSN.csv, Loans.csv
# Drop old terms (step 1400) before export
# Multi-planId: per-planId files in files/ subdirectory
