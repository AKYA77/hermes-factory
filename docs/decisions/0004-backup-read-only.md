# Read-only backup verification correction

A 1,000-experiment / 1,016-file backup reproduced a restore-copy race. Python's
SQLite connection context manager commits/rolls back but does not close the
connection. Verification opened the snapshot in WAL mode; sidecar files could
then disappear during copytree when garbage collection closed the connection.

Snapshots now explicitly close source/destination connections and use DELETE
journal mode for the independent backup file. Verification opens a read-only,
immutable connection after checksum validation and closes it explicitly. Restore
rehearsals report both job and experiment counts. Tests assert verification does
not add/remove/change files and exercise the CLI restore command. A restored
1,000-job, 1,000-experiment snapshot verifies all 1,016 file hashes.

This fixes a reproduced local recovery bug, not all VPS/reboot/migration acceptance.
