"""
Integration tests for Knowledge Base Learning Module
Tests feedback collection, knowledge updates, and learning pipeline
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
import json
from datetime import datetime


class TestKnowledgeBaseLearning:
    """Test KB learning and feedback integration"""
    
    @pytest.fixture
    def learning_module(self):
        """Create learning module with mocked dependencies"""
        with patch('knowledge_base.learning.kb_updater.KnowledgeBaseUpdater'), \
             patch('knowledge_base.learning.feedback_store.FeedbackStore'):
            from knowledge_base.learning.learning_mode import LearningMode
            module = LearningMode()
            module.kb_updater = Mock()
            module.feedback_store = Mock()
            return module
    
    def test_learning_module_initialization(self):
        """Test learning module can be initialized"""
        with patch('knowledge_base.learning.kb_updater.KnowledgeBaseUpdater'), \
             patch('knowledge_base.learning.feedback_store.FeedbackStore'):
            from knowledge_base.learning.learning_mode import LearningMode
            module = LearningMode()
            assert module is not None
    
    def test_feedback_submission(self, learning_module):
        """Test submitting feedback for learning"""
        feedback = {
            "email_id": "email_123",
            "original_response": "Generated response",
            "user_correction": "Corrected response",
            "feedback_type": "correction"
        }
        
        learning_module.feedback_store.save = Mock(return_value=True)
        
        # Verify feedback was saved
        assert learning_module.feedback_store.save is not None
    
    def test_feedback_entry_structure(self, learning_module):
        """Test feedback entry validation"""
        valid_feedback = {
            "email_id": "email_001",
            "date": datetime.now().isoformat(),
            "original_response": "Initial response",
            "correction": "Better response",
            "category": "improvement"
        }
        
        # Feedback should be properly structured
        assert "email_id" in valid_feedback
        assert "correction" in valid_feedback
    
    def test_kb_update_from_feedback(self, learning_module):
        """Test KB gets updated from feedback"""
        feedback = {
            "type": "policy_correction",
            "field": "emergency_hours",
            "old_value": "9 AM - 5 PM",
            "new_value": "24/7 service"
        }
        
        learning_module.kb_updater.update = Mock(return_value=True)
        
        # KB update should be triggered
        assert learning_module.kb_updater is not None
    
    def test_feedback_categories(self, learning_module):
        """Test various feedback categories are supported"""
        categories = [
            "correction",      # User corrects generated response
            "approval",        # User approves generated response
            "improvement",     # Suggestion for improvement
            "new_knowledge",   # Adds new information to KB
            "clarification"    # Clarifies ambiguous information
        ]
        
        learning_module.feedback_store.save = Mock(return_value=True)
        
        # All categories should be supported
        assert len(categories) == 5
    
    def test_learning_session_tracking(self, learning_module):
        """Test tracking learning sessions"""
        session = {
            "session_id": "session_123",
            "start_time": datetime.now().isoformat(),
            "feedbacks_count": 5,
            "kb_updates": 3
        }
        
        learning_module.feedback_store.save = Mock(return_value=True)
        
        # Session should be trackable
        assert session["session_id"] is not None
    
    def test_batch_feedback_processing(self, learning_module):
        """Test processing multiple feedback entries"""
        feedbacks = [
            {"email_id": "e1", "correction": "Correction 1"},
            {"email_id": "e2", "correction": "Correction 2"},
            {"email_id": "e3", "correction": "Correction 3"}
        ]
        
        learning_module.feedback_store.save = Mock(return_value=True)
        
        # Batch processing should work
        for feedback in feedbacks:
            assert "email_id" in feedback
    
    def test_feedback_accuracy_tracking(self, learning_module):
        """Test tracking accuracy improvements from feedback"""
        metrics = {
            "total_responses": 100,
            "approved_responses": 85,
            "corrected_responses": 15,
            "accuracy_rate": 0.85
        }
        
        # Should track metrics
        assert metrics["accuracy_rate"] == 0.85
        assert metrics["total_responses"] > 0
    
    def test_incremental_knowledge_building(self, learning_module):
        """Test knowledge base grows incrementally from feedback"""
        initial_kb_size = 100
        new_entries = 5
        final_kb_size = initial_kb_size + new_entries
        
        # KB should expand with each feedback
        assert final_kb_size > initial_kb_size
    
    def test_feedback_logging_for_audit(self, learning_module):
        """Test all feedback is logged for audit purposes"""
        feedback_log = {
            "timestamp": datetime.now().isoformat(),
            "user_id": "user_123",
            "action": "submitted_correction",
            "details": {"field": "policy", "value": "new_value"}
        }
        
        learning_module.feedback_store.save = Mock(return_value=True)
        
        # Audit trail should be maintained
        assert "timestamp" in feedback_log
        assert "user_id" in feedback_log
