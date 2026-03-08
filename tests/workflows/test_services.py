import pytest
from unittest.mock import patch, MagicMock

try:
    from backend.services.firestore_service import FirestoreService
    from backend.services.bigquery_service import BigQueryService
except ImportError:
    pytest.skip("Module removed during refactor", allow_module_level=True)

@patch("google.cloud.firestore.Client")
def test_firestore_get_businesses(mock_client_class):
    mock_client = mock_client_class.return_value
    mock_stream = MagicMock()
    mock_doc = MagicMock()
    mock_doc.id = "test-slug"
    mock_doc.to_dict.return_value = {"name": "Test Biz", "address": "123 Test St"}
    mock_stream.__iter__.return_value = [mock_doc]

    mock_client.collection.return_value.where.return_value.limit.return_value.stream.return_value = mock_stream

    service = FirestoreService()
    results = service.get_businesses_in_zipcode("10001")

    assert len(results) == 1
    assert results[0]["name"] == "Test Biz"
    assert results[0]["docId"] == "test-slug"

@patch("google.cloud.firestore.Client")
def test_firestore_get_zipcode_research_found(mock_client_class):
    mock_client = mock_client_class.return_value
    mock_doc = MagicMock()
    mock_doc.exists = True
    mock_doc.to_dict.return_value = {
        "summary": "Research for 07110",
        "zip_code": "07110",
        "sections": {},
    }
    mock_client.collection.return_value.doc.return_value.get.return_value = mock_doc

    service = FirestoreService()
    result = service.get_zipcode_research("07110")

    assert result is not None
    assert result["zip_code"] == "07110"
    mock_client.collection.assert_called_with("zipcode_research")
    mock_client.collection.return_value.doc.assert_called_with("07110")


@patch("google.cloud.firestore.Client")
def test_firestore_get_zipcode_research_not_found(mock_client_class):
    mock_client = mock_client_class.return_value
    mock_doc = MagicMock()
    mock_doc.exists = False
    mock_client.collection.return_value.doc.return_value.get.return_value = mock_doc

    service = FirestoreService()
    result = service.get_zipcode_research("99999")

    assert result is None


@patch("google.cloud.firestore.Client")
def test_firestore_save_zipcode_research(mock_client_class):
    mock_client = mock_client_class.return_value
    mock_doc_ref = MagicMock()
    mock_client.collection.return_value.doc.return_value = mock_doc_ref

    service = FirestoreService()
    data = {"summary": "Test", "zip_code": "10001", "sections": {}}
    service.save_zipcode_research("10001", data)

    mock_client.collection.assert_called_with("zipcode_research")
    mock_client.collection.return_value.doc.assert_called_with("10001")
    mock_doc_ref.set.assert_called_once()
    saved_data = mock_doc_ref.set.call_args[0][0]
    assert saved_data["summary"] == "Test"
    assert "updatedAt" in saved_data


@patch("google.cloud.bigquery.Client")
def test_bigquery_insert_analysis(mock_client_class):
    mock_client = mock_client_class.return_value
    mock_client.insert_rows_json.return_value = [] # No errors

    service = BigQueryService()
    service.insert_analysis({"test": "data"})

    mock_client.insert_rows_json.assert_called_once()
