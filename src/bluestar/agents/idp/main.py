"""IDP Agent entrypoint — SQS consumer for steps 0100-0500."""

from __future__ import annotations

# TODO: Implement main entrypoint
# - Consume messages from IDP SQS queue
# - Run SchemaMatcherService → FileParserService → DestringService
# - Write parsed records to Redis session cache: session:{batchId}:records / 4 hr
# - Move S3 file: dropzone/ → inprogress/ → validated/ or failed/
