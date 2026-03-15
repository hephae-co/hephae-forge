"""
Schema Consistency — Tier 2 Logic Tests.

Validates that real Firestore data (sampled) conforms to 
the current Pydantic models in the codebase.
"""

from __future__ import annotations

import logging
import pytest
from pydantic import ValidationError

from hephae_common.firebase import get_db
from apps.api.src.types import BusinessWorkflowState # Unified model

logger = logging.getLogger(__name__)

@pytest.mark.integration
@pytest.mark.asyncio
async def test_firestore_businesses_conform_to_pydantic():
    """Sample real businesses from Firestore and validate against Pydantic."""
    db = get_db()
    
    # Sample up to 20 documents to keep it fast
    docs = db.collection("businesses").limit(20).stream()
    
    validation_errors = []
    processed_count = 0
    
    for doc in docs:
        processed_count += 1
        data = doc.to_dict()
        slug = doc.id
        
        try:
            # Attempt to validate the document
            BusinessWorkflowState.model_validate(data)
        except ValidationError as e:
            validation_errors.append(f"Business '{slug}' failed validation: {e.json()}")
            logger.error(f"Schema drift detected in business '{slug}': {e}")
            
    if validation_errors:
        error_msg = "\n".join(validation_errors)
        pytest.fail(f"Detected schema drift in {len(validation_errors)} businesses:\n{error_msg}")
    
    if processed_count == 0:
        pytest.skip("No businesses found in Firestore to validate.")
        
    logger.info(f"Successfully validated {processed_count} businesses against Pydantic schema.")
