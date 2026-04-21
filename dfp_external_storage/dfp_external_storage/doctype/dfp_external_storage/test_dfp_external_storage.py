# Copyright (c) 2023, DFP and Contributors
# See license.txt

import unittest
from types import SimpleNamespace
from unittest.mock import patch

import frappe

from dfp_external_storage.dfp_external_storage.doctype.dfp_external_storage.dfp_external_storage import (
	DFPExternalStorageFile,
)


class TestDFPExternalStorage(unittest.TestCase):
	# TODO: create DFP External Storage
	# TODO: upload file to bucket
	# TODO: read bucket file
	# TODO: relocate bucket file
	# TODO: delete bucket file
	def test_upload_uses_in_memory_content_when_local_file_missing(self):
		captured = {}

		def put_object(*, bucket_name, object_name, data, length):
			captured["bucket_name"] = bucket_name
			captured["object_name"] = object_name
			captured["payload"] = data.read()
			captured["length"] = length

		fake = SimpleNamespace(
			name="TESTFILE",
			file_name="bonnie carpenter lease.pdf",
			file_url="/files/bonnie carpenter lease.pdf",
			is_private=0,
			is_folder=0,
			dfp_external_storage="DFP.TEST",
			dfp_external_storage_s3_key="",
			dfp_external_storage_doc=SimpleNamespace(
				name="DFP.TEST",
				enabled=1,
				bucket_name="bucket-test",
			),
			dfp_external_storage_client=SimpleNamespace(put_object=put_object),
			dfp_external_storage_ignored_doctypes=lambda: False,
			get_doc_before_save=lambda: None,
			get_content=lambda: b"lease-bytes",
		)

		with patch("os.path.exists", return_value=False), patch.object(frappe.local, "site", "v16.localhost", create=True):
			DFPExternalStorageFile.dfp_external_storage_upload_file(fake)

		self.assertEqual(captured["bucket_name"], "bucket-test")
		self.assertEqual(captured["length"], len(b"lease-bytes"))
		self.assertEqual(captured["payload"], b"lease-bytes")
		self.assertEqual(fake.dfp_external_storage, "DFP.TEST")
		self.assertTrue(fake.dfp_external_storage_s3_key.endswith("/bonnie carpenter lease-TESTFILE.pdf"))
		self.assertEqual(fake.file_url, "/file/TESTFILE/bonnie carpenter lease.pdf")
