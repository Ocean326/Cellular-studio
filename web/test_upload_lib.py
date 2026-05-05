from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from .upload_lib import (
	ActorIdentity,
	PUBLIC_VISIBILITY,
	OWNER_ONLY_VISIBILITY,
	can_actor_view_batch,
	generate_asset_id,
	generate_batch_name,
	generate_upload_id,
	is_deleted_status,
	is_hidden_status,
	parse_actor_identity_from_headers,
	read_batch_catalog_metadata,
	read_upload_metadata,
	resolve_asset_catalog_path,
	resolve_asset_dataset_root,
	resolve_batch_catalog_path,
	resolve_published_batch_root,
	resolve_upload_catalog_path,
	resolve_upload_storage_layout,
	resolve_upload_status_path,
	write_batch_catalog_metadata,
	write_upload_metadata,
)


class UploadLibTest(unittest.TestCase):
	def test_parse_actor_identity_prefers_forwarded_user_and_display_name(self) -> None:
		identity = parse_actor_identity_from_headers(
			{
				"X-Remote-User": "fallback_user",
				"X-Forwarded-User": "Ocean.Wu@example.com",
				"X-Display-Name": "Ocean Wu",
			}
		)

		self.assertEqual(
			identity,
			ActorIdentity(
				actor_id="ocean-wu",
				display_name="Ocean Wu",
				source_header="x-forwarded-user",
			),
		)

	def test_parse_actor_identity_can_derive_from_display_name_only(self) -> None:
		identity = parse_actor_identity_from_headers({"X-Display-Name": "Alice Demo"})

		self.assertEqual(identity.actor_id, "alice-demo")
		self.assertEqual(identity.display_name, "Alice Demo")
		self.assertEqual(identity.source_header, "derived-display-name")

	def test_parse_actor_identity_returns_empty_when_missing(self) -> None:
		identity = parse_actor_identity_from_headers({})

		self.assertEqual(identity.actor_id, "")
		self.assertEqual(identity.display_name, "")
		self.assertEqual(identity.source_header, "")

	def test_visibility_and_status_checks(self) -> None:
		self.assertTrue(
			can_actor_view_batch(
				{
					"visibility_scope": PUBLIC_VISIBILITY,
					"status": "published",
				},
				"",
			)
		)
		self.assertTrue(
			can_actor_view_batch(
				{
					"visibility_scope": OWNER_ONLY_VISIBILITY,
					"owner_actor_id": "alice-demo",
					"status": "published",
				},
				"Alice Demo",
			)
		)
		self.assertFalse(
			can_actor_view_batch(
				{
					"visibility_scope": OWNER_ONLY_VISIBILITY,
					"owner_actor_id": "alice-demo",
					"status": "published",
				},
				"bob",
			)
		)
		self.assertFalse(
			can_actor_view_batch(
				{
					"visibility_scope": PUBLIC_VISIBILITY,
					"status": "archived",
				},
				"alice-demo",
			)
		)
		self.assertFalse(
			can_actor_view_batch(
				{
					"visibility_scope": PUBLIC_VISIBILITY,
					"status": "deleted",
				},
				"alice-demo",
			)
		)
		self.assertTrue(is_hidden_status("retired"))
		self.assertTrue(is_deleted_status("deleted"))
		self.assertFalse(is_deleted_status("published"))

	def test_identifier_helpers_are_stable_with_fixed_inputs(self) -> None:
		now = datetime(2026, 4, 17, 10, 20, 30, tzinfo=timezone.utc)

		self.assertEqual(
			generate_upload_id("Alice Demo", now=now, token="ABCD-1234"),
			"20260417T102030Z_alice-demo_abcd1234",
		)
		self.assertEqual(
			generate_asset_id("trajectory4", "Alice Demo", now=now, token="ABCD-1234"),
			"asset_trajectory4_alice-demo_20260417T102030Z_abcd1234",
		)
		self.assertEqual(
			generate_batch_name("trajectory4", "Alice Demo", now=now, token="ABCD-1234"),
			"trajectory4_alice-demo_20260417t102030z_abcd1234",
		)

	def test_storage_layout_and_path_helpers(self) -> None:
		with tempfile.TemporaryDirectory() as temp_dir:
			layout = resolve_upload_storage_layout(temp_dir)
			root = Path(temp_dir).resolve()

			self.assertEqual(layout.catalog_uploads_root, root / "catalog" / "uploads")
			self.assertEqual(layout.catalog_assets_root, root / "catalog" / "assets")
			self.assertEqual(layout.catalog_batches_root, root / "catalog" / "batches")
			self.assertEqual(layout.user_assets_root, root / "datasets" / "user_assets")
			self.assertEqual(layout.published_private_root, root / "published" / "private")
			self.assertEqual(layout.published_public_root, root / "published" / "public")
			self.assertEqual(
				resolve_upload_catalog_path(layout, "upload-1"),
				root / "catalog" / "uploads" / "upload-1.json",
			)
			self.assertEqual(
				resolve_asset_catalog_path(layout, "asset-1"),
				root / "catalog" / "assets" / "asset-1.json",
			)
			self.assertEqual(
				resolve_batch_catalog_path(layout, "batch-1"),
				root / "catalog" / "batches" / "batch-1.json",
			)
			self.assertEqual(
				resolve_asset_dataset_root(layout, "Alice Demo", "asset-1"),
				root / "datasets" / "user_assets" / "alice-demo" / "asset-1",
			)
			self.assertEqual(
				resolve_published_batch_root(layout, "demo-batch", PUBLIC_VISIBILITY),
				root / "published" / "public" / "demo-batch",
			)
			self.assertEqual(
				resolve_published_batch_root(
					layout,
					"demo-batch",
					OWNER_ONLY_VISIBILITY,
					"Alice Demo",
				),
				root / "published" / "private" / "alice-demo" / "demo-batch",
			)

	def test_upload_metadata_round_trip(self) -> None:
		with tempfile.TemporaryDirectory() as temp_dir:
			upload_root = Path(temp_dir) / "incoming" / "upload-1"
			payload = {
				"upload_id": "upload-1",
				"owner_actor_id": "alice-demo",
				"status": "uploaded",
			}

			written_path = write_upload_metadata(upload_root, payload)

			self.assertEqual(written_path, resolve_upload_status_path(upload_root))
			self.assertEqual(read_upload_metadata(upload_root), payload)

	def test_batch_catalog_metadata_round_trip(self) -> None:
		with tempfile.TemporaryDirectory() as temp_dir:
			path = resolve_batch_catalog_path(temp_dir, "batch-1")
			payload = {
				"batch_name": "batch-1",
				"owner_actor_id": "alice-demo",
				"visibility_scope": PUBLIC_VISIBILITY,
			}

			written_path = write_batch_catalog_metadata(path, payload)

			self.assertEqual(written_path, path)
			self.assertEqual(read_batch_catalog_metadata(path), payload)

	def test_missing_metadata_reads_as_empty_dict(self) -> None:
		with tempfile.TemporaryDirectory() as temp_dir:
			self.assertEqual(read_upload_metadata(Path(temp_dir) / "incoming" / "missing"), {})
			self.assertEqual(
				read_batch_catalog_metadata(Path(temp_dir) / "catalog" / "batches" / "missing.json"),
				{},
			)


if __name__ == "__main__":
	unittest.main()
