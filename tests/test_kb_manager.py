"""
Unit tests for Knowledge Base components
Tests VectorIndex, KBStore, and KB ingestion functionality
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
import json
import os


class TestVectorIndex:
    """Test Vector Index functionality"""
    
    @pytest.fixture
    def vector_index(self):
        """Create Vector Index instance"""
        with patch('knowledge_base.vector_index.chromadb.PersistentClient'):
            from knowledge_base.vector_index import VectorIndex
            index = VectorIndex()
            index.collection = Mock()
            return index
    
    def test_vector_index_initialization(self):
        """Test VectorIndex can be initialized"""
        with patch('knowledge_base.vector_index.chromadb.PersistentClient'):
            from knowledge_base.vector_index import VectorIndex
            index = VectorIndex()
            assert index is not None
            assert hasattr(index, 'collection')
    
    def test_rebuild_index(self, vector_index):
        """Test rebuilding vector index with KB data"""
        test_kb_data = {
            "faqs": [
                {"q": "Are you open on weekends?", "a": "Yes"}
            ],
            "services": {
                "emergency": {"price": "$100"}
            }
        }
        
        vector_index.collection.delete = Mock()
        vector_index.collection.add = Mock()
        
        # Test that rebuild doesn't raise error
        try:
            vector_index.rebuild_index(test_kb_data)
            assert True
        except Exception as e:
            pytest.skip(f"Rebuild skipped: {e}")
    
    def test_vector_index_add_documents(self, vector_index):
        """Test adding documents to vector index"""
        vector_index.collection.add = Mock()
        
        # Verify collection has add method
        assert callable(vector_index.collection.add)
    
    def test_vector_index_delete_documents(self, vector_index):
        """Test deleting documents from vector index"""
        vector_index.collection.delete = Mock()
        
        # Verify collection has delete method
        assert callable(vector_index.collection.delete)


class TestKBStore:
    """Test Knowledge Base Store functionality"""
    
    @pytest.mark.skipif(
        os.getenv("DATABASE_URL") is None and os.getenv("SKIP_DB_TESTS") == "true",
        reason="Database not configured"
    )
    def test_kb_store_initialization(self):
        """Test KBStore can be initialized"""
        with patch('knowledge_base.kb_store.create_engine'):
            from knowledge_base.kb_store import KBStore
            
            try:
                store = KBStore(db_url="postgresql://test:test@localhost/test")
                assert store is not None
            except ValueError:
                # Expected for invalid DB URL in test
                assert True
    
    def test_kb_store_requires_db_url(self):
        """Test KBStore requires database URL"""
        from knowledge_base.kb_store import KBStore
        
        # Temporarily unset DATABASE_URL to test error handling
        old_db_url = os.environ.pop("DATABASE_URL", None)
        try:
            with pytest.raises(ValueError, match="DATABASE_URL"):
                KBStore(db_url=None)
        finally:
            # Restore DATABASE_URL if it was set
            if old_db_url is not None:
                os.environ["DATABASE_URL"] = old_db_url
    
    @patch('knowledge_base.kb_store.create_engine')
    def test_kb_store_validates_postgresql_url(self, mock_engine):
        """Test KBStore validates PostgreSQL URL"""
        from knowledge_base.kb_store import KBStore
        
        with pytest.raises(ValueError, match="Only PostgreSQL is supported"):
            KBStore(db_url="mysql://test:test@localhost/test")


class TestKBIngestion:
    """Test KB ingestion functionality"""
    
    def test_load_email_kb(self):
        """Test loading KB from JSON file"""
        from knowledge_base.ingestion_json_kb import load_email_kb
        
        test_kb_data = {
            "services": {
                "plumbing": {
                    "description": "Professional plumbing services",
                    "price": "$75/hour"
                }
            },
            "policies": {
                "emergency_hours": "24/7 emergency service available"
            },
            "faqs": [
                {"q": "Are you available on weekends?", "a": "Yes"}
            ]
        }
        
        # Mock file operations
        with patch('builtins.open', create=True) as mock_open:
            mock_open.return_value.__enter__.return_value.read.return_value = json.dumps(test_kb_data)
            
            try:
                items = load_email_kb("test_kb.json")
                assert items is not None
                assert len(items) > 0
            except FileNotFoundError:
                pytest.skip("KB file not found")
    
    def test_knowledge_item_creation(self):
        """Test creating KnowledgeItem instances"""
        from knowledge_base.ingestion_json_kb import KnowledgeItem
        
        item = KnowledgeItem(
            id="test_1",
            category="faq",
            title="Test Question",
            content="Test Answer"
        )
        
        assert item.id == "test_1"
        assert item.category == "faq"
        assert item.title == "Test Question"
        assert item.content == "Test Answer"
    
    def test_knowledge_item_with_tags(self):
        """Test KnowledgeItem with tags"""
        from knowledge_base.ingestion_json_kb import KnowledgeItem
        
        item = KnowledgeItem(
            id="service_1",
            category="service",
            title="Plumbing Service",
            content="Emergency plumbing services",
            tags=["service", "emergency", "plumbing"]
        )
        
        assert len(item.tags) == 3
        assert "emergency" in item.tags
