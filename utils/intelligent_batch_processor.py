import logging
import time
import json
import uuid
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
import statistics
from collections import defaultdict
import asyncio
import threading
from concurrent.futures import ThreadPoolExecutor
import copy


class BatchStrategy(Enum):
    """Different batch processing strategies"""
    DOCUMENT_TYPE_GROUPING = "document_type_grouping"
    QUALITY_LEVEL_GROUPING = "quality_level_grouping"
    CLIENT_GROUPING = "client_grouping"
    PROCESSING_REQUIREMENT_GROUPING = "processing_requirement_grouping"
    MIXED_OPTIMIZATION = "mixed_optimization"


class ProcessingPriority(Enum):
    """Processing priority levels"""
    URGENT = "urgent"          # Process immediately
    HIGH = "high"              # Process within 30 seconds
    NORMAL = "normal"          # Process within 2 minutes
    LOW = "low"                # Process within 5 minutes
    BATCH_ONLY = "batch_only"  # Only process in optimal batches


@dataclass
class DocumentBatchItem:
    """Individual document in a batch"""
    file_path: str
    original_filename: str
    document_type: Optional[str] = None
    quality_score: Optional[float] = None
    client_info: Optional[Dict] = None
    processing_priority: ProcessingPriority = ProcessingPriority.NORMAL
    preprocessing_required: bool = True
    validation_recommended: bool = False
    estimated_api_cost: float = 0.0
    batch_group_id: Optional[str] = None
    added_timestamp: float = 0.0


@dataclass
class BatchGroup:
    """Group of similar documents for batch processing"""
    group_id: str
    strategy: BatchStrategy
    documents: List[DocumentBatchItem]
    estimated_total_cost: float = 0.0
    optimal_batch_size: int = 5
    created_timestamp: float = 0.0
    target_processing_time: float = 0.0


class DocumentSimilarityAnalyzer:
    """Analyzes document similarity for optimal batch grouping"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        
        # Similarity weights for grouping decisions
        self.similarity_weights = {
            'document_type': 0.4,      # Most important for API optimization
            'quality_level': 0.25,     # Important for preprocessing batching
            'client_similarity': 0.2,  # Useful for field extraction optimization
            'processing_requirements': 0.15  # Validation and enhancement needs
        }
    
    def analyze_batch_similarity(self, documents: List[DocumentBatchItem]) -> Dict[str, Any]:
        """
        Analyze how similar a group of documents are for batch processing
        
        Returns:
            Dictionary with similarity scores and batch recommendations
        """
        if len(documents) < 2:
            return {
                'similarity_score': 1.0,
                'recommended_strategy': BatchStrategy.MIXED_OPTIMIZATION,
                'grouping_factors': {}
            }
        
        # Analyze different similarity factors
        doc_type_similarity = self._analyze_document_type_similarity(documents)
        quality_similarity = self._analyze_quality_similarity(documents)
        client_similarity = self._analyze_client_similarity(documents)
        processing_similarity = self._analyze_processing_similarity(documents)
        
        # Calculate weighted similarity score
        total_similarity = (
            doc_type_similarity * self.similarity_weights['document_type'] +
            quality_similarity * self.similarity_weights['quality_level'] +
            client_similarity * self.similarity_weights['client_similarity'] +
            processing_similarity * self.similarity_weights['processing_requirements']
        )
        
        # Determine optimal batching strategy
        strategy = self._determine_optimal_strategy(
            doc_type_similarity, quality_similarity, 
            client_similarity, processing_similarity
        )
        
        return {
            'similarity_score': total_similarity,
            'recommended_strategy': strategy,
            'grouping_factors': {
                'document_type_similarity': doc_type_similarity,
                'quality_similarity': quality_similarity,
                'client_similarity': client_similarity,
                'processing_similarity': processing_similarity
            },
            'batch_optimization_potential': self._calculate_optimization_potential(documents, total_similarity)
        }
    
    def _analyze_document_type_similarity(self, documents: List[DocumentBatchItem]) -> float:
        """Analyze how similar document types are in the batch"""
        doc_types = [doc.document_type for doc in documents if doc.document_type]
        if not doc_types:
            return 0.5  # Unknown similarity
        
        # Perfect similarity if all same type
        unique_types = set(doc_types)
        if len(unique_types) == 1:
            return 1.0
        
        # Partial similarity for related types (e.g., different 1099s)
        related_groups = [
            {'Form W-2'},
            {'Form 1099-NEC', 'Form 1099-MISC', 'Form 1099-INT', 'Form 1099-DIV'},
            {'Form 1040', 'Schedule C', 'Schedule K-1'},
            {'Receipt', 'Invoice'}
        ]
        
        for group in related_groups:
            if unique_types.issubset(group):
                return 0.8  # High similarity for related types
        
        # Low similarity for mixed types
        return 0.2
    
    def _analyze_quality_similarity(self, documents: List[DocumentBatchItem]) -> float:
        """Analyze how similar document quality levels are"""
        qualities = [doc.quality_score for doc in documents if doc.quality_score is not None]
        if not qualities:
            return 0.5
        
        quality_std = statistics.stdev(qualities) if len(qualities) > 1 else 0
        
        # High similarity if all documents have similar quality
        if quality_std < 0.1:
            return 1.0
        elif quality_std < 0.2:
            return 0.8
        elif quality_std < 0.3:
            return 0.6
        else:
            return 0.3
    
    def _analyze_client_similarity(self, documents: List[DocumentBatchItem]) -> float:
        """Analyze if documents belong to same client"""
        clients = set()
        for doc in documents:
            if doc.client_info:
                client_key = f"{doc.client_info.get('first_name', '')}-{doc.client_info.get('last_name', '')}"
                clients.add(client_key)
        
        if len(clients) <= 1:
            return 1.0  # All same client or unknown
        elif len(clients) <= 3:
            return 0.7  # Few clients
        else:
            return 0.3  # Many different clients
    
    def _analyze_processing_similarity(self, documents: List[DocumentBatchItem]) -> float:
        """Analyze similarity of processing requirements"""
        preprocessing_counts = sum(1 for doc in documents if doc.preprocessing_required)
        validation_counts = sum(1 for doc in documents if doc.validation_recommended)
        
        total_docs = len(documents)
        
        # Calculate consistency of requirements
        preprocessing_consistency = abs(preprocessing_counts / total_docs - 0.5) * 2
        validation_consistency = abs(validation_counts / total_docs - 0.5) * 2
        
        return (preprocessing_consistency + validation_consistency) / 2
    
    def _determine_optimal_strategy(self, doc_sim: float, qual_sim: float, 
                                  client_sim: float, proc_sim: float) -> BatchStrategy:
        """Determine the optimal batching strategy based on similarity analysis"""
        similarities = {
            'document_type': doc_sim,
            'quality': qual_sim,
            'client': client_sim,
            'processing': proc_sim
        }
        
        # Find the highest similarity factor
        max_similarity = max(similarities.values())
        best_factor = max(similarities.keys(), key=lambda k: similarities[k])
        
        # Choose strategy based on strongest similarity
        if max_similarity > 0.8:
            if best_factor == 'document_type':
                return BatchStrategy.DOCUMENT_TYPE_GROUPING
            elif best_factor == 'quality':
                return BatchStrategy.QUALITY_LEVEL_GROUPING
            elif best_factor == 'client':
                return BatchStrategy.CLIENT_GROUPING
            else:
                return BatchStrategy.PROCESSING_REQUIREMENT_GROUPING
        else:
            # If no strong similarity, use mixed optimization
            return BatchStrategy.MIXED_OPTIMIZATION
    
    def _calculate_optimization_potential(self, documents: List[DocumentBatchItem], 
                                        similarity_score: float) -> Dict[str, float]:
        """Calculate potential API cost and time savings from batch processing"""
        if len(documents) < 2:
            return {'api_cost_savings': 0.0, 'processing_time_savings': 0.0}
        
        # Base savings increase with batch size and similarity
        batch_size = len(documents)
        base_api_savings = min(0.3, (batch_size - 1) * 0.05) * similarity_score
        base_time_savings = min(0.4, (batch_size - 1) * 0.08) * similarity_score
        
        return {
            'api_cost_savings': base_api_savings,
            'processing_time_savings': base_time_savings,
            'batch_efficiency_score': similarity_score * (batch_size / 10)  # Normalized efficiency
        }


class BatchOptimizer:
    """Optimizes batch processing strategies and timing"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        
        # Optimization parameters
        self.max_batch_size = 8  # Maximum documents per batch
        self.min_batch_size = 2  # Minimum for worthwhile batching
        self.max_wait_time = 120  # Maximum seconds to wait for batch completion
        self.cost_threshold = 0.15  # Minimum cost savings to justify batching
        
        # Document type specific optimizations
        self.type_specific_configs = {
            'Form W-2': {'optimal_batch_size': 6, 'api_multiplier': 0.8},
            'Form 1099-NEC': {'optimal_batch_size': 5, 'api_multiplier': 0.85},
            'Form 1099-MISC': {'optimal_batch_size': 5, 'api_multiplier': 0.85},
            'Form 1040': {'optimal_batch_size': 3, 'api_multiplier': 1.2},
            'Schedule C': {'optimal_batch_size': 4, 'api_multiplier': 1.1},
            'Receipt': {'optimal_batch_size': 8, 'api_multiplier': 0.7},
            'Invoice': {'optimal_batch_size': 7, 'api_multiplier': 0.75},
            'Unknown Document': {'optimal_batch_size': 4, 'api_multiplier': 1.0}
        }
    
    def optimize_batch_groups(self, documents: List[DocumentBatchItem]) -> List[BatchGroup]:
        """
        Create optimally grouped batches from a list of documents
        
        Returns:
            List of optimized batch groups
        """
        if len(documents) < self.min_batch_size:
            # Process individually if too few documents
            return self._create_individual_batches(documents)
        
        # Separate urgent documents for immediate processing
        urgent_docs = [doc for doc in documents if doc.processing_priority == ProcessingPriority.URGENT]
        batchable_docs = [doc for doc in documents if doc.processing_priority != ProcessingPriority.URGENT]
        
        batch_groups = []
        
        # Process urgent documents individually
        if urgent_docs:
            batch_groups.extend(self._create_individual_batches(urgent_docs))
        
        # Create optimized batches for remaining documents
        if len(batchable_docs) >= self.min_batch_size:
            batch_groups.extend(self._create_optimized_batches(batchable_docs))
        else:
            # Not enough for batching, process individually
            batch_groups.extend(self._create_individual_batches(batchable_docs))
        
        return batch_groups
    
    def _create_optimized_batches(self, documents: List[DocumentBatchItem]) -> List[BatchGroup]:
        """Create optimized batches using multiple strategies"""
        batch_groups = []
        remaining_docs = documents.copy()
        
        # Strategy 1: Group by document type (most effective for API optimization)
        type_groups = self._group_by_document_type(remaining_docs)
        for doc_type, type_docs in type_groups.items():
            if len(type_docs) >= self.min_batch_size:
                optimal_size = self.type_specific_configs.get(doc_type, {}).get('optimal_batch_size', 5)
                batches = self._split_into_optimal_batches(type_docs, optimal_size)
                
                for batch_docs in batches:
                    group = BatchGroup(
                        group_id=str(uuid.uuid4()),
                        strategy=BatchStrategy.DOCUMENT_TYPE_GROUPING,
                        documents=batch_docs,
                        created_timestamp=time.time()
                    )
                    self._calculate_batch_metrics(group)
                    batch_groups.append(group)
                
                # Remove processed documents
                for doc in type_docs:
                    if doc in remaining_docs:
                        remaining_docs.remove(doc)
        
        # Strategy 2: Group remaining documents by quality level
        if remaining_docs:
            quality_groups = self._group_by_quality_level(remaining_docs)
            for quality_range, quality_docs in quality_groups.items():
                if len(quality_docs) >= self.min_batch_size:
                    batches = self._split_into_optimal_batches(quality_docs, 4)
                    
                    for batch_docs in batches:
                        group = BatchGroup(
                            group_id=str(uuid.uuid4()),
                            strategy=BatchStrategy.QUALITY_LEVEL_GROUPING,
                            documents=batch_docs,
                            created_timestamp=time.time()
                        )
                        self._calculate_batch_metrics(group)
                        batch_groups.append(group)
                    
                    # Remove processed documents
                    for doc in quality_docs:
                        if doc in remaining_docs:
                            remaining_docs.remove(doc)
        
        # Strategy 3: Process remaining documents individually or in mixed batches
        if remaining_docs:
            if len(remaining_docs) >= self.min_batch_size:
                # Create mixed optimization batches
                batches = self._split_into_optimal_batches(remaining_docs, 4)
                for batch_docs in batches:
                    group = BatchGroup(
                        group_id=str(uuid.uuid4()),
                        strategy=BatchStrategy.MIXED_OPTIMIZATION,
                        documents=batch_docs,
                        created_timestamp=time.time()
                    )
                    self._calculate_batch_metrics(group)
                    batch_groups.append(group)
            else:
                # Process individually
                batch_groups.extend(self._create_individual_batches(remaining_docs))
        
        return batch_groups
    
    def _group_by_document_type(self, documents: List[DocumentBatchItem]) -> Dict[str, List[DocumentBatchItem]]:
        """Group documents by their type"""
        groups = defaultdict(list)
        for doc in documents:
            doc_type = doc.document_type or 'Unknown Document'
            groups[doc_type].append(doc)
        return dict(groups)
    
    def _group_by_quality_level(self, documents: List[DocumentBatchItem]) -> Dict[str, List[DocumentBatchItem]]:
        """Group documents by quality level ranges"""
        groups = defaultdict(list)
        for doc in documents:
            quality = doc.quality_score or 0.5
            if quality >= 0.8:
                groups['high_quality'].append(doc)
            elif quality >= 0.6:
                groups['medium_quality'].append(doc)
            else:
                groups['low_quality'].append(doc)
        return dict(groups)
    
    def _split_into_optimal_batches(self, documents: List[DocumentBatchItem], 
                                  optimal_size: int) -> List[List[DocumentBatchItem]]:
        """Split documents into optimally sized batches"""
        batches = []
        for i in range(0, len(documents), optimal_size):
            batch = documents[i:i + optimal_size]
            batches.append(batch)
        return batches
    
    def _create_individual_batches(self, documents: List[DocumentBatchItem]) -> List[BatchGroup]:
        """Create individual processing batches for urgent or unsuitable documents"""
        individual_batches = []
        for doc in documents:
            group = BatchGroup(
                group_id=str(uuid.uuid4()),
                strategy=BatchStrategy.MIXED_OPTIMIZATION,
                documents=[doc],
                created_timestamp=time.time()
            )
            self._calculate_batch_metrics(group)
            individual_batches.append(group)
        return individual_batches
    
    def _calculate_batch_metrics(self, batch_group: BatchGroup):
        """Calculate cost and timing metrics for a batch group"""
        total_cost = 0.0
        processing_time_estimate = 0.0
        
        for doc in batch_group.documents:
            # Base API cost estimation
            base_cost = 0.10  # Base Claude API call cost
            
            # Adjust based on document type
            doc_type = doc.document_type or 'Unknown Document'
            type_config = self.type_specific_configs.get(doc_type, {})
            api_multiplier = type_config.get('api_multiplier', 1.0)
            
            doc_cost = base_cost * api_multiplier
            
            # Add preprocessing and validation costs
            if doc.preprocessing_required:
                doc_cost += 0.02  # Preprocessing overhead
            if doc.validation_recommended:
                doc_cost += 0.08  # Validation API call
            
            total_cost += doc_cost
            processing_time_estimate += 3.0  # Base processing time per document
        
        # Apply batch processing discounts
        batch_size = len(batch_group.documents)
        if batch_size > 1:
            # API cost savings from batching
            api_discount = min(0.25, (batch_size - 1) * 0.05)
            total_cost *= (1 - api_discount)
            
            # Time savings from parallel processing
            time_discount = min(0.3, (batch_size - 1) * 0.06)
            processing_time_estimate *= (1 - time_discount)
        
        batch_group.estimated_total_cost = total_cost
        batch_group.target_processing_time = processing_time_estimate + time.time()
        batch_group.optimal_batch_size = self.type_specific_configs.get(
            batch_group.documents[0].document_type or 'Unknown Document', {}
        ).get('optimal_batch_size', 5)


class IntelligentBatchProcessor:
    """
    Main class for intelligent batch processing of tax documents
    Coordinates document grouping, optimization, and processing
    """
    
    def __init__(self, enhanced_processor):
        self.enhanced_processor = enhanced_processor
        self.similarity_analyzer = DocumentSimilarityAnalyzer()
        self.batch_optimizer = BatchOptimizer()
        self.logger = logging.getLogger(__name__)
        
        # Batch processing state
        self.pending_documents = []
        self.active_batches = {}
        self.completed_batches = []
        self.processing_stats = self._initialize_batch_stats()
        
        # Processing control
        self.max_concurrent_batches = 3
        self.batch_timeout = 60  # 1 minute max per batch (reduced from 5 minutes)
        self.auto_batch_interval = 15  # Check for auto-batching every 15 seconds
        
        # Statistics file
        self.stats_file = "batch_processing_stats.json"
        self._load_historical_stats()
        
        # Start background batch processor
        self.batch_processor_thread = None
        self.processing_active = False
    
    def _initialize_batch_stats(self) -> Dict:
        """Initialize batch processing statistics"""
        return {
            'total_batches_processed': 0,
            'total_documents_batched': 0,
            'total_individual_processed': 0,
            'cost_optimization_rate': 0.0,
            'time_optimization_rate': 0.0,
            'api_cost_savings': [],
            'processing_time_savings': [],
            'average_batch_size': [],
            'strategy_usage': {
                'document_type_grouping': 0,
                'quality_level_grouping': 0,
                'client_grouping': 0,
                'processing_requirement_grouping': 0,
                'mixed_optimization': 0
            },
            'batch_processing_enabled': True,
            'current_queue_size': 0,
            'active_batches_count': 0,
            'recent_completion_rate': 0.0,
            'average_wait_time': 0.0,
            'total_cost_saved': 0.0,
            'total_time_saved': 0.0
        }
    
    def add_document_to_batch_queue(self, file_path: str, original_filename: str,
                                  processing_priority: ProcessingPriority = ProcessingPriority.NORMAL,
                                  manual_client_info: Optional[Dict] = None) -> Dict:
        """
        Add a document to the batch processing queue
        
        Args:
            file_path: Path to the document
            original_filename: Original filename
            processing_priority: Processing priority level
            manual_client_info: Optional manual client information
            
        Returns:
            Dictionary with batch queue information
        """
        try:
            # Create document batch item
            batch_item = DocumentBatchItem(
                file_path=file_path,
                original_filename=original_filename,
                processing_priority=processing_priority,
                added_timestamp=time.time()
            )
            
            # Quick preliminary analysis for batch optimization
            batch_item = self._analyze_document_for_batching(batch_item)
            
            # Add client info if provided
            if manual_client_info:
                batch_item.client_info = manual_client_info
            
            # Add to pending queue
            self.pending_documents.append(batch_item)
            
            self.logger.info(f"Added {original_filename} to batch queue (priority: {processing_priority.value})")
            
            # Start batch processor if not already running
            if not self.processing_active:
                self._start_batch_processor()
            
            # Check if immediate processing is needed
            if processing_priority == ProcessingPriority.URGENT:
                return self._process_urgent_document(batch_item)
            
            return {
                'status': 'queued_for_batch',
                'queue_position': len(self.pending_documents),
                'estimated_wait_time': self._estimate_wait_time(processing_priority),
                'batch_optimization_enabled': True
            }
            
        except Exception as e:
            self.logger.error(f"Error adding document to batch queue: {e}")
            return {
                'status': 'error',
                'error': str(e)
            }
    
    def _analyze_document_for_batching(self, batch_item: DocumentBatchItem) -> DocumentBatchItem:
        """Perform quick analysis to optimize document for batching"""
        try:
            # Quick document type prediction (using filename patterns)
            batch_item.document_type = self._predict_document_type_from_filename(batch_item.original_filename)
            
            # Estimate quality (would be better with actual image analysis)
            batch_item.quality_score = 0.7  # Default assumption
            
            # Determine processing requirements
            batch_item.preprocessing_required = True  # Conservative assumption
            batch_item.validation_recommended = self._should_recommend_validation(batch_item)
            
            # Estimate API cost
            batch_item.estimated_api_cost = self._estimate_document_api_cost(batch_item)
            
            return batch_item
            
        except Exception as e:
            self.logger.error(f"Error analyzing document for batching: {e}")
            return batch_item
    
    def _predict_document_type_from_filename(self, filename: str) -> Optional[str]:
        """Predict document type from filename patterns"""
        filename_lower = filename.lower()
        
        # Common filename patterns
        if 'w2' in filename_lower or 'w-2' in filename_lower:
            return 'Form W-2'
        elif '1099' in filename_lower:
            if 'nec' in filename_lower:
                return 'Form 1099-NEC'
            elif 'misc' in filename_lower:
                return 'Form 1099-MISC'
            else:
                return 'Form 1099-MISC'  # Default 1099 type
        elif '1040' in filename_lower:
            return 'Form 1040'
        elif 'receipt' in filename_lower:
            return 'Receipt'
        elif 'invoice' in filename_lower:
            return 'Invoice'
        
        return None  # Unknown document type
    
    def _should_recommend_validation(self, batch_item: DocumentBatchItem) -> bool:
        """Determine if validation should be recommended for this document"""
        # Base recommendation on document type and priority
        if batch_item.processing_priority == ProcessingPriority.URGENT:
            return True  # Always validate urgent documents
        
        # Complex document types benefit more from validation
        complex_types = ['Form 1040', 'Schedule K-1', 'Schedule C']
        if batch_item.document_type in complex_types:
            return True
        
        return False  # Default to no validation to save costs
    
    def _estimate_document_api_cost(self, batch_item: DocumentBatchItem) -> float:
        """Estimate API cost for processing this document"""
        base_cost = 0.10  # Base Claude API call
        
        # Adjust based on document type complexity
        type_multipliers = {
            'Form W-2': 0.8,
            'Form 1099-NEC': 0.8,
            'Form 1099-MISC': 0.8,
            'Form 1040': 1.3,
            'Schedule C': 1.2,
            'Receipt': 0.7,
            'Invoice': 0.7
        }
        
        doc_type = batch_item.document_type or 'Unknown Document'
        multiplier = type_multipliers.get(doc_type, 1.0)
        
        estimated_cost = base_cost * multiplier
        
        # Add validation cost if recommended
        if batch_item.validation_recommended:
            estimated_cost += 0.08
        
        return estimated_cost
    
    def _estimate_wait_time(self, priority: ProcessingPriority) -> float:
        """Estimate wait time based on priority and current queue"""
        base_wait_times = {
            ProcessingPriority.URGENT: 0,      # Immediate
            ProcessingPriority.HIGH: 30,      # 30 seconds
            ProcessingPriority.NORMAL: 90,    # 1.5 minutes
            ProcessingPriority.LOW: 180,      # 3 minutes
            ProcessingPriority.BATCH_ONLY: 300  # 5 minutes
        }
        
        base_wait = base_wait_times.get(priority, 90)
        queue_factor = len(self.pending_documents) * 10  # Additional 10 seconds per queued document
        
        return base_wait + queue_factor
    
    def _start_batch_processor(self):
        """Start the background batch processing thread"""
        if not self.processing_active:
            self.processing_active = True
            self.batch_processor_thread = threading.Thread(
                target=self._batch_processing_loop,
                daemon=True
            )
            self.batch_processor_thread.start()
            self.logger.info("Started intelligent batch processor")
    
    def _batch_processing_loop(self):
        """Main batch processing loop that runs in background"""
        while self.processing_active:
            try:
                # Check for documents ready for batch processing
                if self.pending_documents:
                    self._process_pending_batches()
                
                # Clean up completed batches
                self._cleanup_completed_batches()
                
                # Wait before next check
                time.sleep(self.auto_batch_interval)
                
            except Exception as e:
                self.logger.error(f"Error in batch processing loop: {e}")
                time.sleep(5)  # Brief pause before continuing
    
    def _process_pending_batches(self):
        """Process documents in the pending queue"""
        if not self.pending_documents:
            return
        
        # Separate documents by priority and timing
        ready_documents = []
        current_time = time.time()
        
        for doc in self.pending_documents[:]:  # Copy to avoid modification during iteration
            wait_time = current_time - doc.added_timestamp
            
            # Check if document is ready for processing
            if (doc.processing_priority == ProcessingPriority.URGENT or
                wait_time >= self._get_max_wait_time(doc.processing_priority) or
                len(self.pending_documents) >= self.batch_optimizer.max_batch_size):
                
                ready_documents.append(doc)
                self.pending_documents.remove(doc)
        
        if ready_documents:
            # Create optimized batches
            batch_groups = self.batch_optimizer.optimize_batch_groups(ready_documents)
            
            # Process each batch group
            for batch_group in batch_groups:
                self._execute_batch_group(batch_group)
    
    def _get_max_wait_time(self, priority: ProcessingPriority) -> float:
        """Get maximum wait time for a priority level"""
        max_wait_times = {
            ProcessingPriority.URGENT: 0,
            ProcessingPriority.HIGH: 30,
            ProcessingPriority.NORMAL: 120,
            ProcessingPriority.LOW: 300,
            ProcessingPriority.BATCH_ONLY: 600
        }
        return max_wait_times.get(priority, 120)
    
    def _execute_batch_group(self, batch_group: BatchGroup):
        """Execute processing for a batch group"""
        if len(self.active_batches) >= self.max_concurrent_batches:
            # Queue for later processing
            self.pending_documents.extend(batch_group.documents)
            return
        
        self.logger.info(f"Executing batch group {batch_group.group_id} with {len(batch_group.documents)} documents (strategy: {batch_group.strategy.value})")
        
        # Add to active batches
        self.active_batches[batch_group.group_id] = {
            'batch_group': batch_group,
            'start_time': time.time(),
            'results': []
        }
        
        # Start batch processing thread
        batch_thread = threading.Thread(
            target=self._process_batch_group_thread,
            args=(batch_group,),
            daemon=True
        )
        batch_thread.start()
    
    def _process_batch_group_thread(self, batch_group: BatchGroup):
        """Process a batch group in a separate thread"""
        try:
            batch_start_time = time.time()
            results = []
            
            # Process documents in the batch group
            for doc in batch_group.documents:
                try:
                    # Process individual document using enhanced processor
                    result = self.enhanced_processor.process_document(
                        doc.file_path,
                        doc.original_filename,
                        doc.client_info
                    )
                    
                    # Add batch processing metadata
                    result['batch_group_id'] = batch_group.group_id
                    result['batch_strategy'] = batch_group.strategy.value
                    result['batch_size'] = len(batch_group.documents)
                    result['processing_priority'] = doc.processing_priority.value
                    
                    results.append(result)
                    
                except Exception as e:
                    self.logger.error(f"Error processing document {doc.original_filename} in batch: {e}")
                    results.append({
                        'original_filename': doc.original_filename,
                        'status': 'error',
                        'error': str(e),
                        'batch_group_id': batch_group.group_id
                    })
            
            # Calculate batch processing statistics
            batch_processing_time = time.time() - batch_start_time
            self._update_batch_statistics(batch_group, results, batch_processing_time)
            
            # Move batch to completed
            if batch_group.group_id in self.active_batches:
                self.active_batches[batch_group.group_id]['results'] = results
                self.active_batches[batch_group.group_id]['completion_time'] = time.time()
                
                # Move to completed batches
                self.completed_batches.append(self.active_batches[batch_group.group_id])
                del self.active_batches[batch_group.group_id]
            
            self.logger.info(f"Completed batch group {batch_group.group_id} in {batch_processing_time:.2f} seconds")
            
        except Exception as e:
            self.logger.error(f"Error processing batch group {batch_group.group_id}: {e}")
            # Clean up failed batch
            if batch_group.group_id in self.active_batches:
                del self.active_batches[batch_group.group_id]
    
    def _update_batch_statistics(self, batch_group: BatchGroup, results: List[Dict], processing_time: float):
        """Update batch processing statistics"""
        stats = self.processing_stats
        
        # Basic counts
        stats['total_batches_processed'] += 1
        stats['total_documents_batched'] += len(batch_group.documents)
        stats['average_batch_size'].append(len(batch_group.documents))
        
        # Strategy usage
        strategy_key = batch_group.strategy.value
        stats['strategy_usage'][strategy_key] = stats['strategy_usage'].get(strategy_key, 0) + 1
        
        # Performance metrics
        estimated_individual_time = len(batch_group.documents) * 3.0  # 3 seconds per document individually
        time_savings = max(0, estimated_individual_time - processing_time)
        time_savings_rate = time_savings / estimated_individual_time if estimated_individual_time > 0 else 0
        
        stats['processing_time_savings'].append({
            'batch_id': batch_group.group_id,
            'estimated_individual_time': estimated_individual_time,
            'actual_batch_time': processing_time,
            'time_saved': time_savings,
            'time_savings_rate': time_savings_rate
        })
        
        # Cost savings calculation
        estimated_individual_cost = sum(doc.estimated_api_cost for doc in batch_group.documents)
        actual_batch_cost = batch_group.estimated_total_cost
        cost_savings = max(0, estimated_individual_cost - actual_batch_cost)
        cost_savings_rate = cost_savings / estimated_individual_cost if estimated_individual_cost > 0 else 0
        
        stats['api_cost_savings'].append({
            'batch_id': batch_group.group_id,
            'estimated_individual_cost': estimated_individual_cost,
            'actual_batch_cost': actual_batch_cost,
            'cost_saved': cost_savings,
            'cost_savings_rate': cost_savings_rate
        })
        
        # Document type performance tracking
        for doc in batch_group.documents:
            doc_type = doc.document_type or 'Unknown Document'
            if doc_type not in stats['document_type_batch_performance']:
                stats['document_type_batch_performance'][doc_type] = {
                    'total_batched': 0,
                    'average_batch_size': [],
                    'success_rate': [],
                    'processing_times': []
                }
            
            type_stats = stats['document_type_batch_performance'][doc_type]
            type_stats['total_batched'] += 1
            type_stats['average_batch_size'].append(len(batch_group.documents))
            type_stats['processing_times'].append(processing_time / len(batch_group.documents))
        
        # Calculate overall optimization rates
        if stats['processing_time_savings']:
            recent_time_savings = [s['time_savings_rate'] for s in stats['processing_time_savings'][-10:]]
            stats['time_optimization_rate'] = sum(recent_time_savings) / len(recent_time_savings)
        
        if stats['api_cost_savings']:
            recent_cost_savings = [s['cost_savings_rate'] for s in stats['api_cost_savings'][-10:]]
            stats['cost_optimization_rate'] = sum(recent_cost_savings) / len(recent_cost_savings)
        
        # Save statistics
        self._save_batch_statistics()
    
    def _cleanup_completed_batches(self):
        """Clean up old completed batches to prevent memory buildup"""
        current_time = time.time()
        retention_time = 3600  # Keep completed batches for 1 hour
        
        self.completed_batches = [
            batch for batch in self.completed_batches
            if current_time - batch.get('completion_time', 0) < retention_time
        ]
    
    def _process_urgent_document(self, batch_item: DocumentBatchItem) -> Dict:
        """Process urgent document immediately, bypassing batch queue"""
        try:
            self.logger.info(f"Processing urgent document: {batch_item.original_filename}")
            
            result = self.enhanced_processor.process_document(
                batch_item.file_path,
                batch_item.original_filename,
                batch_item.client_info
            )
            
            # Add urgent processing metadata
            result['processing_mode'] = 'urgent_individual'
            result['batch_bypassed'] = True
            
            # Track individual processing
            self.processing_stats['total_individual_processed'] += 1
            
            return result
            
        except Exception as e:
            self.logger.error(f"Error processing urgent document: {e}")
            return {
                'original_filename': batch_item.original_filename,
                'status': 'error',
                'error': str(e),
                'processing_mode': 'urgent_individual'
            }
    
    def get_batch_processing_status(self) -> Dict:
        """Get current status of batch processing system"""
        try:
            return {
                'processing_active': self.processing_active,
                'pending_documents': len(self.pending_documents),
                'active_batches': len(self.active_batches),
                'completed_batches_recent': len(self.completed_batches),
                'total_batches_processed': self.processing_stats.get('total_batches_processed', 0),
                'total_documents_batched': self.processing_stats.get('total_documents_batched', 0),
                'total_individual_processed': self.processing_stats.get('total_individual_processed', 0),
                'current_optimization_rates': {
                    'cost_savings': self.processing_stats.get('cost_optimization_rate', 0.0),
                    'time_savings': self.processing_stats.get('time_optimization_rate', 0.0)
                },
                'queue_details': [
                    {
                        'filename': doc.original_filename,
                        'priority': doc.processing_priority.value,
                        'wait_time': time.time() - doc.added_timestamp,
                        'document_type': doc.document_type
                    }
                    for doc in self.pending_documents
                ]
            }
        except Exception as e:
            self.logger.error(f"Error getting batch processing status: {e}")
            return {
                'processing_active': self.processing_active,
                'pending_documents': len(self.pending_documents),
                'active_batches': len(self.active_batches),
                'completed_batches_recent': len(self.completed_batches),
                'error': str(e)
            }
    
    def get_batch_processing_statistics(self) -> Dict:
        """Get comprehensive batch processing statistics"""
        try:
            stats = self.processing_stats.copy()
            
            # Calculate summary metrics
            average_batch_size = stats.get('average_batch_size', [])
            if average_batch_size:
                stats['average_batch_size_value'] = sum(average_batch_size) / len(average_batch_size)
            else:
                stats['average_batch_size_value'] = 0.0
            
            # Calculate total savings
            api_cost_savings = stats.get('api_cost_savings', [])
            processing_time_savings = stats.get('processing_time_savings', [])
            
            total_cost_saved = sum(s.get('cost_saved', 0) for s in api_cost_savings)
            total_time_saved = sum(s.get('time_saved', 0) for s in processing_time_savings)
            
            stats['total_cost_saved'] = total_cost_saved
            stats['total_time_saved'] = total_time_saved
            
            # Strategy effectiveness
            strategy_usage = stats.get('strategy_usage', {})
            total_strategy_usage = sum(strategy_usage.values())
            if total_strategy_usage > 0:
                stats['strategy_effectiveness'] = {
                    strategy: (count / total_strategy_usage) * 100
                    for strategy, count in strategy_usage.items()
                }
            else:
                stats['strategy_effectiveness'] = {}
            
            return stats
            
        except Exception as e:
            self.logger.error(f"Error getting batch processing statistics: {e}")
            return {
                'error': str(e),
                'total_cost_saved': 0.0,
                'total_time_saved': 0.0,
                'average_batch_size_value': 0.0,
                'strategy_effectiveness': {}
            }
    
    def _load_historical_stats(self):
        """Load historical batch processing statistics"""
        try:
            if Path(self.stats_file).exists():
                with open(self.stats_file, 'r') as f:
                    historical_stats = json.load(f)
                    
                # Merge with current stats structure
                for key, value in historical_stats.items():
                    if key in self.processing_stats:
                        if isinstance(self.processing_stats[key], dict) and isinstance(value, dict):
                            self.processing_stats[key].update(value)
                        elif isinstance(self.processing_stats[key], list) and isinstance(value, list):
                            self.processing_stats[key].extend(value)
                        else:
                            self.processing_stats[key] = value
                
                self.logger.info("Loaded historical batch processing statistics")
        except Exception as e:
            self.logger.error(f"Error loading historical batch statistics: {e}")
    
    def _save_batch_statistics(self):
        """Save batch processing statistics to file"""
        try:
            # Create a simplified version for JSON serialization
            simplified_stats = copy.deepcopy(self.processing_stats)
            
            # Keep only recent data to prevent file bloat
            max_history = 100
            if len(simplified_stats['api_cost_savings']) > max_history:
                simplified_stats['api_cost_savings'] = simplified_stats['api_cost_savings'][-max_history:]
            if len(simplified_stats['processing_time_savings']) > max_history:
                simplified_stats['processing_time_savings'] = simplified_stats['processing_time_savings'][-max_history:]
            if len(simplified_stats['average_batch_size']) > max_history:
                simplified_stats['average_batch_size'] = simplified_stats['average_batch_size'][-max_history:]
            
            with open(self.stats_file, 'w') as f:
                json.dump(simplified_stats, f, indent=2)
                
        except Exception as e:
            self.logger.error(f"Error saving batch statistics: {e}")
    
    def stop_batch_processing(self):
        """Stop the batch processing system"""
        self.processing_active = False
        if self.batch_processor_thread:
            self.batch_processor_thread.join(timeout=5)
        
        # Save final statistics
        self._save_batch_statistics()
        
        self.logger.info("Stopped intelligent batch processor") 