# Copyright (c) 2023, DFP and Contributors
# See license.txt

import unittest
from types import MethodType, SimpleNamespace
from unittest.mock import patch

import frappe
from frappe.core.doctype.file.file import File

from dfp_external_storage.dfp_external_storage.doctype.dfp_external_storage.dfp_external_storage import (
	DFPExternalStorageFile,
	file as render_file,
	hook_file_before_save,
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

	def test_force_local_file_never_resolves_or_calls_external_storage(self):
		def unexpected(*args, **kwargs):
			raise AssertionError("external storage must not be inspected or called")

		fake = SimpleNamespace(
			flags=SimpleNamespace(dfp_force_local_storage=True),
			is_private=1,
			dfp_external_storage="",
			dfp_external_storage_s3_key="",
			get_doc_before_save=lambda: None,
			dfp_external_storage_upload_file=unexpected,
		)

		hook_file_before_save(fake, "before_save")
		result = DFPExternalStorageFile.dfp_external_storage_upload_file(fake)

		self.assertFalse(result)
		self.assertEqual(fake.dfp_external_storage, "")
		self.assertEqual(fake.dfp_external_storage_s3_key, "")

	def test_force_local_flag_cannot_reclassify_existing_or_selected_storage(self):
		def raise_error(message, exc):
			raise exc(message)

		for previous, storage, key, is_private in (
			(SimpleNamespace(name="existing"), "", "", 1),
			(None, "DFP.TEST", "", 1),
			(None, "", "test/object.pdf", 1),
			(None, "", "", 0),
		):
			with self.subTest(previous=previous, storage=storage, key=key, is_private=is_private):
				fake = SimpleNamespace(
					flags=SimpleNamespace(dfp_force_local_storage=True),
					is_private=is_private,
					dfp_external_storage=storage,
					dfp_external_storage_s3_key=key,
					get_doc_before_save=lambda previous=previous: previous,
				)
				with patch.object(frappe, "throw", side_effect=raise_error), self.assertRaises(
					frappe.ValidationError
				):
					hook_file_before_save(fake, "before_save")

	def test_force_local_target_rollback_preserves_shared_source_blob(self):
		"""Exercise core File rollback with an exact same-hash source reference."""
		state = {"source_blob_exists": True, "target_thumbnail_exists": True}
		target = SimpleNamespace(
			name="TARGET-FILE",
			content_hash="same-content-hash",
			flags=frappe._dict(new_file=True, dfp_force_local_storage=True),
		)

		def delete_file_data_content(only_thumbnail=False):
			if only_thumbnail:
				state["target_thumbnail_exists"] = False
			else:
				state["source_blob_exists"] = False

		def shared_source_query(doctype, *, filters, limit):
			self.assertEqual(doctype, "File")
			self.assertEqual(filters["content_hash"], "same-content-hash")
			self.assertEqual(filters["name"], ["!=", "TARGET-FILE"])
			self.assertEqual(limit, 1)
			return [{"name": "SOURCE-FILE"}]

		target.delete_file_data_content = delete_file_data_content
		target._delete_file_on_disk = MethodType(File._delete_file_on_disk, target)
		with patch.object(frappe, "get_all", side_effect=shared_source_query):
			File.on_rollback(target)

		self.assertTrue(state["source_blob_exists"])
		self.assertFalse(state["target_thumbnail_exists"])
		self.assertNotIn("new_file", target.flags)

	def test_voice_archive_direct_route_denies_before_cache_or_provider_lookup(self):
		def unexpected(*_args, **_kwargs):
			raise AssertionError("cache, File, and provider paths must not be consulted")

		with (
			patch.object(
				frappe,
				"db",
				SimpleNamespace(
					table_exists=lambda _doctype: True,
					exists=lambda _doctype, _filters: "ARCH-1",
				),
			),
			patch.object(frappe, "cache", side_effect=unexpected),
			patch.object(frappe, "get_doc", side_effect=unexpected),
			self.assertRaises(frappe.PageDoesNotExistError),
		):
			render_file("FILE-VOICE-1", "call.mp3")

	def test_voice_archive_classification_error_fails_closed_before_cache(self):
		def unexpected(*_args, **_kwargs):
			raise AssertionError("public cache must not be consulted")

		with (
			patch.object(
				frappe,
				"db",
				SimpleNamespace(
					table_exists=lambda _doctype: (_ for _ in ()).throw(
						RuntimeError("database unavailable")
					)
				),
			),
			patch.object(frappe, "cache", side_effect=unexpected),
			self.assertRaises(frappe.PageDoesNotExistError),
		):
			render_file("FILE-VOICE-1", "call.mp3")
