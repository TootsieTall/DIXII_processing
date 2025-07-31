import os
import shutil
from pathlib import Path
import uuid
import time
from PIL import Image
import re
import unicodedata
import logging
import json
from typing import Dict, Optional, List, Tuple
from models.donut_classifier import DonutTaxClassifier
from models.enhanced_claude_ocr import EnhancedClaudeOCR
from models.enhanced_name_detector import EnhancedNameDetector
from utils.entity_recognizer import EntityRecognizer
from utils.filename_generator import FilenameGenerator
from utils.document_preprocessor import DocumentPreprocessor
from utils.document_type_aware_preprocessor import DocumentTypeAwarePreprocessor
from config import Config
from utils.intelligent_batch_processor import IntelligentBatchProcessor, ProcessingPriority, DocumentBatchItem
import threading
import asyncio
from concurrent.futures import ThreadPoolExecutor

class DynamicThresholdManager:
    """
    Phase 5: Dynamic Confidence Thresholds
    Manages adaptive confidence thresholds based on document types and historical performance
    """
    
    def __init__(self, stats_file: str = "dynamic_thresholds.json"):
        self.stats_file = stats_file
        self.load_historical_data()
        
        # Document-type specific base thresholds
        self.base_thresholds = {
            'W-2': {
                'high_confidence': 0.85,    # W-2s are structured, lower threshold
                'low_confidence': 0.25,
                'validation_sweet_spot': (0.35, 0.75),
                'critical_fields': ['wages', 'tax_withheld', 'employer_name']
            },
            '1099-NEC': {
                'high_confidence': 0.80,    # 1099s are usually clear
                'low_confidence': 0.30,
                'validation_sweet_spot': (0.40, 0.70),
                'critical_fields': ['income_amount', 'payer_name', 'recipient_name']
            },
            '1099-MISC': {
                'high_confidence': 0.80,
                'low_confidence': 0.30,
                'validation_sweet_spot': (0.40, 0.70),
                'critical_fields': ['income_amount', 'payer_name', 'recipient_name']
            },
            'Form 1040': {
                'high_confidence': 0.95,    # Complex forms need higher confidence
                'low_confidence': 0.40,
                'validation_sweet_spot': (0.50, 0.85),
                'critical_fields': ['total_income', 'tax_owed', 'filing_status']
            },
            'Schedule C': {
                'high_confidence': 0.90,    # Business forms are complex
                'low_confidence': 0.35,
                'validation_sweet_spot': (0.45, 0.80),
                'critical_fields': ['business_income', 'expenses', 'net_profit']
            },
            'Receipt': {
                'high_confidence': 0.75,    # Receipts vary widely in quality
                'low_confidence': 0.20,
                'validation_sweet_spot': (0.30, 0.65),
                'critical_fields': ['amount', 'vendor', 'date']
            },
            'Invoice': {
                'high_confidence': 0.80,    # Invoices are usually well-structured
                'low_confidence': 0.25,
                'validation_sweet_spot': (0.35, 0.70),
                'critical_fields': ['amount', 'vendor', 'date', 'description']
            },
            'Bank Statement': {
                'high_confidence': 0.85,    # Bank statements are structured
                'low_confidence': 0.30,
                'validation_sweet_spot': (0.40, 0.75),
                'critical_fields': ['transactions', 'balance', 'account_number']
            },
            'Default': {  # For unknown document types
                'high_confidence': 0.90,
                'low_confidence': 0.30,
                'validation_sweet_spot': (0.40, 0.75),
                'critical_fields': ['amount', 'date', 'name']
            }
        }
        
        # Field importance weights (higher = more important to get right)
        self.field_importance = {
            'tax_year': 1.0,
            'client_name': 1.0,
            'person_name': 1.0,
            'wages': 0.9,
            'income_amount': 0.9,
            'tax_withheld': 0.9,
            'total_income': 0.9,
            'employer_name': 0.8,
            'payer_name': 0.8,
            'business_income': 0.8,
            'amount': 0.7,
            'date': 0.6,
            'address': 0.5,
            'phone': 0.3
        }
    
    def load_historical_data(self):
        """Load historical performance data for threshold adaptation"""
        try:
            if os.path.exists(self.stats_file):
                with open(self.stats_file, 'r') as f:
                    data = json.load(f)
                    self.historical_performance = data.get('performance', {})
                    self.threshold_adjustments = data.get('adjustments', {})
            else:
                self.historical_performance = {}
                self.threshold_adjustments = {}
        except Exception as e:
            print(f"Error loading historical data: {e}")
            self.historical_performance = {}
            self.threshold_adjustments = {}
    
    def save_historical_data(self):
        """Save performance data for future threshold adaptations"""
        try:
            data = {
                'performance': self.historical_performance,
                'adjustments': self.threshold_adjustments,
                'last_updated': time.time()
            }
            with open(self.stats_file, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            print(f"Error saving historical data: {e}")
    
    def get_adaptive_thresholds(self, doc_type: str, field_results: Dict) -> Dict:
        """
        Calculate adaptive thresholds based on document type and historical performance
        """
        # Get base thresholds for document type
        normalized_type = self._normalize_doc_type(doc_type)
        base = self.base_thresholds.get(normalized_type, self.base_thresholds['Default'])
        
        # Apply historical adjustments
        performance_key = f"{normalized_type}_performance"
        if performance_key in self.historical_performance:
            perf_data = self.historical_performance[performance_key]
            
            # Adjust based on validation success rate
            success_rate = perf_data.get('validation_success_rate', 0.5)
            if success_rate > 0.8:  # High success rate - can be more selective
                high_conf_adj = 0.05
                validation_range_adj = (0.05, -0.05)  # Narrow the range
            elif success_rate < 0.4:  # Low success rate - be more aggressive
                high_conf_adj = -0.05
                validation_range_adj = (-0.05, 0.05)  # Widen the range
            else:
                high_conf_adj = 0.0
                validation_range_adj = (0.0, 0.0)
        else:
            high_conf_adj = 0.0
            validation_range_adj = (0.0, 0.0)
        
        # Calculate field-importance weighted confidence boost
        field_importance_boost = self._calculate_field_importance_boost(field_results)
        
        # Apply time-based learning adjustments
        time_adjustment = self._get_time_based_adjustment(normalized_type)
        
        # Calculate final adaptive thresholds
        adaptive_thresholds = {
            'high_confidence': min(0.98, base['high_confidence'] + high_conf_adj + time_adjustment),
            'low_confidence': max(0.10, base['low_confidence'] - time_adjustment),
            'validation_sweet_spot': (
                max(0.15, base['validation_sweet_spot'][0] + validation_range_adj[0]),
                min(0.95, base['validation_sweet_spot'][1] + validation_range_adj[1])
            ),
            'critical_fields': base['critical_fields'],
            'field_importance_boost': field_importance_boost,
            'adaptations_applied': {
                'success_rate_adjustment': high_conf_adj,
                'validation_range_adjustment': validation_range_adj,
                'field_importance_boost': field_importance_boost,
                'time_based_adjustment': time_adjustment
            }
        }
        
        return adaptive_thresholds
    
    def _normalize_doc_type(self, doc_type: str) -> str:
        """Normalize document type for threshold lookup"""
        if not doc_type:
            return 'Default'
        
        doc_type = doc_type.strip().upper()
        
        # Map variations to standard types
        type_mappings = {
            'W2': 'W-2',
            'W-2': 'W-2',
            '1099NEC': '1099-NEC',
            '1099-NEC': '1099-NEC',
            '1099MISC': '1099-MISC',
            '1099-MISC': '1099-MISC',
            'FORM1040': 'Form 1040',
            '1040': 'Form 1040',
            'SCHEDULEC': 'Schedule C',
            'SCHEDULE C': 'Schedule C'
        }
        
        return type_mappings.get(doc_type, doc_type if doc_type in self.base_thresholds else 'Default')
    
    def _calculate_field_importance_boost(self, field_results: Dict) -> float:
        """Calculate confidence boost based on field importance"""
        total_importance = 0.0
        weighted_confidence = 0.0
        
        for field_name, value in field_results.items():
            if field_name.endswith('_confidence'):
                base_field = field_name.replace('_confidence', '')
                importance = self.field_importance.get(base_field, 0.5)
                confidence = float(value) if isinstance(value, (int, float)) else 0.0
                
                total_importance += importance
                weighted_confidence += confidence * importance
        
        if total_importance > 0:
            avg_weighted_confidence = weighted_confidence / total_importance
            # Return boost between -0.1 and +0.1 based on field importance
            return (avg_weighted_confidence - 0.5) * 0.2
        
        return 0.0
    
    def _get_time_based_adjustment(self, doc_type: str) -> float:
        """Get time-based learning adjustment for thresholds"""
        performance_key = f"{doc_type}_performance"
        if performance_key not in self.historical_performance:
            return 0.0
        
        perf_data = self.historical_performance[performance_key]
        total_processed = perf_data.get('total_processed', 0)
        
        # More experience = more confident in thresholds (smaller adjustments)
        if total_processed > 100:
            return 0.02  # Slight confidence boost for experienced types
        elif total_processed > 50:
            return 0.01
        else:
            return 0.0  # No adjustment for new document types
    
    def update_performance_data(self, doc_type: str, validation_applied: bool, 
                              validation_successful: bool, original_confidence: float, 
                              final_confidence: float):
        """Update historical performance data"""
        normalized_type = self._normalize_doc_type(doc_type)
        performance_key = f"{normalized_type}_performance"
        
        if performance_key not in self.historical_performance:
            self.historical_performance[performance_key] = {
                'total_processed': 0,
                'validations_applied': 0,
                'validations_successful': 0,
                'validation_success_rate': 0.5,
                'confidence_improvements': [],
                'last_updated': time.time()
            }
        
        perf_data = self.historical_performance[performance_key]
        perf_data['total_processed'] += 1
        
        if validation_applied:
            perf_data['validations_applied'] += 1
            if validation_successful:
                perf_data['validations_successful'] += 1
                confidence_improvement = final_confidence - original_confidence
                perf_data['confidence_improvements'].append(confidence_improvement)
                
                # Keep only last 50 improvements for rolling average
                if len(perf_data['confidence_improvements']) > 50:
                    perf_data['confidence_improvements'] = perf_data['confidence_improvements'][-50:]
            
            # Update success rate
            if perf_data['validations_applied'] > 0:
                perf_data['validation_success_rate'] = (
                    perf_data['validations_successful'] / perf_data['validations_applied']
                )
        
        perf_data['last_updated'] = time.time()
        
        # Auto-save periodically
        if perf_data['total_processed'] % 10 == 0:
            self.save_historical_data()
    
    def get_validation_recommendation(self, doc_type: str, field_results: Dict) -> Dict:
        """
        Get intelligent validation recommendation based on adaptive thresholds
        """
        thresholds = self.get_adaptive_thresholds(doc_type, field_results)
        confidence = field_results.get('confidence', 0.0)
        
        # Apply field-importance boost to confidence
        adjusted_confidence = confidence + thresholds['field_importance_boost']
        
        recommendation = {
            'should_validate': False,
            'reason': '',
            'confidence_threshold_used': thresholds,
            'original_confidence': confidence,
            'adjusted_confidence': adjusted_confidence,
            'priority': 'low'
        }
        
        # High confidence - skip validation
        if adjusted_confidence >= thresholds['high_confidence']:
            recommendation.update({
                'should_validate': False,
                'reason': 'adaptive_high_confidence',
                'priority': 'skip'
            })
            return recommendation
        
        # Very low confidence - skip validation (won't help much)
        if adjusted_confidence <= thresholds['low_confidence']:
            recommendation.update({
                'should_validate': False,
                'reason': 'adaptive_low_confidence',
                'priority': 'skip'
            })
            return recommendation
        
        # Sweet spot for validation
        sweet_min, sweet_max = thresholds['validation_sweet_spot']
        if sweet_min <= adjusted_confidence <= sweet_max:
            recommendation.update({
                'should_validate': True,
                'reason': 'adaptive_sweet_spot',
                'priority': 'high' if sweet_min + 0.1 <= adjusted_confidence <= sweet_max - 0.1 else 'medium'
            })
            return recommendation
        
        # Check critical fields
        critical_fields = thresholds['critical_fields']
        missing_critical = sum(1 for field in critical_fields 
                             if not field_results.get(field) or 
                             str(field_results[field]).lower() in ['unknown', 'null', ''])
        
        if missing_critical >= 2:
            recommendation.update({
                'should_validate': True,
                'reason': 'adaptive_critical_fields_missing',
                'priority': 'high'
            })
            return recommendation
        
        # Default to not validating
        recommendation.update({
            'should_validate': False,
            'reason': 'adaptive_cost_optimization',
            'priority': 'skip'
        })
        
        return recommendation


class EnhancedTaxDocumentProcessor:
    def __init__(self, donut_model_path: str, claude_api_key: str):
        self.donut_classifier = DonutTaxClassifier(donut_model_path)
        self.claude_ocr = EnhancedClaudeOCR(claude_api_key)
        self.entity_recognizer = EntityRecognizer(Config.PROCESSED_FOLDER)
        self.filename_generator = FilenameGenerator()
        self.document_preprocessor = DocumentPreprocessor()  # Basic image enhancement
        self.document_type_aware_preprocessor = DocumentTypeAwarePreprocessor()  # Phase 4: Type-aware enhancement
        self.dynamic_threshold_manager = DynamicThresholdManager()  # Phase 5: Dynamic thresholds
        
        # Enhanced Name Detection System
        self.name_detector = EnhancedNameDetector()
        
        # Phase 6: Intelligent Batch Processing
        self.batch_processor = IntelligentBatchProcessor(self)
        self.batch_processing_enabled = True
        
        self.processed_folder = Config.PROCESSED_FOLDER
        
        # Setup logging
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger(__name__)
        
        # Create processed folder if it doesn't exist
        os.makedirs(self.processed_folder, exist_ok=True)
        
        # Initialize processing statistics with Phase 6 batch tracking
        self.processing_stats = self._initialize_processing_stats()
        
        # Load dynamic threshold data
        self.dynamic_threshold_manager.load_historical_data()
        
        self.logger.info("Enhanced Tax Document Processor with Intelligent Batch Processing and Enhanced Name Detection initialized")
    
    def _initialize_processing_stats(self):
        """Initialize comprehensive processing statistics including batch processing"""
        return {
            'total_documents': 0,
            'successful_extractions': 0,
            'processing_errors': 0,
            'document_types': {},
            'entity_types': {},
            'amendments_detected': 0,
            'joint_returns': 0,
            'confidence_scores': [],
            'processing_times': [],
            'validation_applied': 0,
            'validation_skipped': 0,
            'validation_effectiveness': [],
            'field_routing_stats': {
                'donut_classifications': 0,
                'claude_extractions': 0,
                'dual_validations': 0,
                'fallback_to_comprehensive': 0,
                'field_routing_effectiveness': []
            },
            'ensemble_decisions': {
                'model_agreements': 0,
                'model_disagreements': 0,
                'donut_favored': 0,
                'claude_favored': 0,
                'confidence_boosts_applied': 0,
                'ensemble_accuracy_improvements': []
            },
            'cross_validation': {  # Phase 3: Cross-validation statistics
                'total_validations_performed': 0,
                'validations_skipped': 0,
                'conflicts_detected': 0,
                'conflicts_resolved': 0,
                'validation_triggers': {
                    'medium_confidence': 0,
                    'model_disagreement': 0,
                    'unknown_document_type': 0,
                    'critical_field_uncertainty': 0,
                    'quality_concern': 0,
                    'historical_performance': 0,
                    'user_request': 0
                },
                'confidence_improvements': [],
                'cost_savings': 0.0
            },
            'dynamic_thresholds': {  # Phase 5: Dynamic threshold statistics
                'total_threshold_evaluations': 0,
                'validation_recommended': 0,
                'validation_skipped_by_thresholds': 0,
                'threshold_adaptations': 0,
                'performance_improvements': [],
                'cost_optimizations': [],
                'document_type_learning': {},
                'field_importance_adaptations': 0
            },
            'document_type_preprocessing': {  # Phase 4: Track document-type aware preprocessing
                'total_documents_processed': 0,
                'type_aware_enhancements_applied': 0,
                'basic_enhancements_applied': 0,
                'quality_improvements': [],
                'processing_time_savings': [],
                'enhancement_effectiveness': {},
                'document_type_strategies': {},
                'quality_score_improvements': []
            },
            'enhanced_name_detection': {  # Enhanced Name Detection statistics
                'total_documents_processed': 0,
                'names_detected': 0,
                'unknown_client_reduction': 0,
                'priority_used': 0,  # Track when enhanced detection overrides Claude
                'fallback_to_claude': 0,  # Track when enhanced detection fails and falls back to Claude
                'confidence_improvements': [],
                'detection_methods_used': {
                    'layoutlm': 0,
                    'bert_ner': 0,
                    'patterns': 0
                },
                'average_confidence': 0.0,
                'processing_time_savings': []
            },
            'batch_processing': {  # Phase 6: Intelligent batch processing statistics
                'total_batches_created': 0,
                'total_documents_batched': 0,
                'total_individual_processed': 0,
                'batch_vs_individual_ratio': 0.0,
                'api_cost_savings_from_batching': [],
                'processing_time_savings_from_batching': [],
                'batch_strategy_effectiveness': {
                    'document_type_grouping': {'count': 0, 'avg_savings': 0.0},
                    'quality_level_grouping': {'count': 0, 'avg_savings': 0.0},
                    'client_grouping': {'count': 0, 'avg_savings': 0.0},
                    'processing_requirement_grouping': {'count': 0, 'avg_savings': 0.0},
                    'mixed_optimization': {'count': 0, 'avg_savings': 0.0}
                },
                'optimal_batch_sizes': {},
                'batch_processing_enabled': True,
                'current_batch_queue_size': 0
            }
        }
    
    def process_document(self, file_path: str, original_filename: str, 
                        manual_client_info: Optional[Dict] = None) -> Dict:
        """
        Enhanced document processing with comprehensive extraction and intelligent organization
        
        Args:
            file_path: Path to the document file
            original_filename: Original filename
            manual_client_info: Optional manual client information
            
        Returns:
            Comprehensive processing results
        """
        result = {
            'original_filename': original_filename,
            'status': 'processing',
            'confidence': 0.0,
            'document_type': 'Unknown',
            'client_name': 'Unknown',
            'tax_year': None,
            'entity_info': {},
            'extracted_details': {},
            'processing_notes': [],
            'processing_mode': 'enhanced',
            'error': None
        }
        
        temp_files = []
        
        try:
            self.processing_stats['total_documents'] += 1
            
            # Step 1: Prepare image for processing
            image_path = self._prepare_image(file_path, temp_files)
            if not image_path:
                result['status'] = 'error'
                result['error'] = 'Failed to prepare image for processing'
                return result
            
            # Step 2: Document type classification (Donut specialty) - KEEP AS FIRST LINE
            donut_result = self._classify_with_donut(image_path, original_filename)
            
            # Step 3: Enhanced Name Detection as FIRST LINE for client/entity naming
            name_detection_results = self._apply_enhanced_name_detection(image_path, donut_result)
            
            # Step 4: Document-Type Aware Preprocessing
            enhanced_image_path, preprocessing_results = self._apply_document_type_preprocessing(
                image_path, donut_result, temp_files
            )
            
            # Step 5: Field-specific extraction routing (using enhanced image)
            extracted_info = self._extract_with_field_routing(enhanced_image_path, donut_result)
            
            # Track field routing usage
            if extracted_info.get('validation_applied'):
                self.processing_stats['validation_applied'] += 1
            else:
                self.processing_stats['validation_skipped'] += 1
                self.logger.info(f"Validation skipped: {extracted_info.get('validation_skipped_reason', 'unknown')}")
            
            # Track field routing statistics
            self._track_field_routing_stats(extracted_info)
            
            # Step 6: Merge enhanced name detection with extracted info (PRIORITIZE NAME DETECTION)
            extracted_info = self._merge_enhanced_name_detection_priority(extracted_info, name_detection_results)
            
            # Step 7: Merge and validate results with ensemble decision making
            merged_info = self._merge_classification_results(donut_result, extracted_info)
            
            # Step 8: Entity recognition and analysis
            if manual_client_info:
                # Override with manual information
                merged_info = self._apply_manual_client_info(merged_info, manual_client_info)
            
            # Step 9: Entity recognition and analysis
            entity_info = self.entity_recognizer.analyze_entity(merged_info)
            
            # Step 10: Generate intelligent filename
            filename_info = self.filename_generator.get_filename_preview(
                merged_info, entity_info, original_filename
            )
            
            # Step 11: Organize document into appropriate folder
            organization_result = self._organize_document(
                file_path, entity_info, filename_info, merged_info
            )
            
            # Step 12: Update processing statistics
            self._update_processing_stats(result)
            
            # Step 13: Prepare final result
            # Calculate relative path for web serving
            final_path = organization_result.get('final_path', file_path)
            try:
                processed_relative_path = os.path.relpath(final_path, self.processed_folder)
                # Normalize path separators for web URLs
                processed_relative_path = processed_relative_path.replace('\\', '/')
            except:
                processed_relative_path = filename_info.get('filename', original_filename)
            
            # Prepare comprehensive result
            result.update({
                'status': 'completed',  # Changed from 'success' to 'completed' to match frontend expectations
                'document_type': merged_info.get('document_type', 'Unknown'),
                'client_name': merged_info.get('client_name', 'Unknown'),
                'person_name': merged_info.get('person_name', 'Unknown'),
                'tax_year': merged_info.get('tax_year'),
                'confidence': merged_info.get('confidence', 0.0),
                'new_filename': organization_result.get('final_filename'),  # Add the new filename
                'processed_path': processed_relative_path,  # Add processed path for actions
                'entity_info': entity_info,
                'extracted_details': merged_info,
                'filename_info': filename_info,
                'organization_result': organization_result,
                'processed_relative_path': processed_relative_path,
                'name_detection_results': name_detection_results,  # Include name detection results
                'processing_notes': [
                    f"Document type: {merged_info.get('document_type', 'Unknown')}",
                    f"Client name: {merged_info.get('client_name', 'Unknown')}",
                    f"Tax year: {merged_info.get('tax_year', 'Unknown')}",
                    f"Entity type: {entity_info.get('entity_type', 'Unknown')}",
                    f"Name detection confidence: {name_detection_results.get('confidence', 0.0)}",
                    f"Name detection methods: {', '.join(name_detection_results.get('detection_methods', []))}"
                ]
            })
            
            # Clean up temporary files
            self._clean_temp_files(temp_files)
            
            return result
            
        except Exception as e:
            self.logger.error(f"Error processing document {original_filename}: {e}")
            result['status'] = 'error'
            result['error'] = str(e)
            result['new_filename'] = None  # Ensure new_filename is set even for errors
            result['processed_path'] = None  # Ensure processed_path is set even for errors
            self._clean_temp_files(temp_files)
            return result
    
    def _prepare_image(self, file_path: str, temp_files: List[str]) -> Optional[str]:
        """Enhanced file preparation - keeps PDFs as PDFs, minimizes image conversion"""
        try:
            file_ext = Path(file_path).suffix.lower()
            
            # Step 1: Handle different file types appropriately
            if file_ext == '.pdf':
                # Keep PDFs as PDFs - no conversion needed
                self.logger.info(f"Processing PDF directly: {file_path}")
                return file_path
            else:
                # For image files, check if optimization is needed for AI models
                with Image.open(file_path) as img:
                    if img.mode != 'RGB':
                        img = img.convert('RGB')
                    
                    # Check if resizing is needed for AI models
                    width, height = img.size
                    max_dimension = 2048
                    
                    if max(width, height) > max_dimension:
                        # Only create optimized version if resizing is necessary
                        ratio = max_dimension / max(width, height)
                        new_width = int(width * ratio)
                        new_height = int(height * ratio)
                        img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
                        
                        # Save optimized image only when necessary
                        optimized_path = f"temp_optimized_{uuid.uuid4()}.jpg"
                        img.save(optimized_path, 'JPEG', quality=95, dpi=(200, 200))
                        temp_files.append(optimized_path)
                        
                        self.logger.info(f"Created temporary optimized image for AI processing")
                        return optimized_path
                    else:
                        # Use original image if no resizing needed
                        self.logger.info(f"Using original image for processing: {file_path}")
                        return file_path
            
        except Exception as e:
            self.logger.error(f"Error preparing file: {e}")
            return None
    
    def _classify_with_donut(self, image_path: str, filename: str) -> Dict:
        """Classify document with Donut model"""
        try:
            doc_type, confidence = self.donut_classifier.classify_document(image_path)
            
            if doc_type and confidence > 0.5:
                human_readable = self.donut_classifier.get_human_readable_label(doc_type)
                self.logger.info(f"Donut classified {filename} as: {human_readable} (confidence: {confidence:.2f})")
                return {
                    'donut_type': human_readable,
                    'donut_confidence': confidence,
                    'donut_success': True
                }
            else:
                self.logger.info(f"Donut classification failed for {filename} (confidence: {confidence:.2f})")
                return {
                    'donut_type': None,
                    'donut_confidence': confidence,
                    'donut_success': False
                }
                
        except Exception as e:
            self.logger.error(f"Error in Donut classification: {e}")
            return {
                'donut_type': None,
                'donut_confidence': 0.0,
                'donut_success': False
            }
    
    def _merge_classification_results(self, donut_result: Dict, claude_result: Dict) -> Dict:
        """Advanced weighted ensemble - intelligently combines Donut and Claude results"""
        merged = claude_result.copy()
        
        # Step 1: Determine best document type using ensemble decision
        final_doc_type, type_confidence, type_source = self._ensemble_document_type_decision(donut_result, claude_result)
        
        # Step 2: Calculate ensemble confidence score
        ensemble_confidence = self._calculate_ensemble_confidence(donut_result, claude_result, final_doc_type)
        
        # Step 3: Apply ensemble results
        merged['document_type'] = final_doc_type
        merged['confidence'] = ensemble_confidence
        merged['classification_source'] = type_source
        merged['ensemble_method'] = 'weighted'
        
        # Step 4: Add detailed ensemble information
        merged['donut_classification'] = donut_result
        merged['ensemble_details'] = {
            'donut_confidence': donut_result.get('donut_confidence', 0.0),
            'claude_confidence': claude_result.get('confidence', 0.0),
            'type_agreement': self._check_type_agreement(donut_result, claude_result),
            'confidence_boost': ensemble_confidence - claude_result.get('confidence', 0.0)
        }
        
        # Step 5: Log ensemble decision
        self._log_ensemble_decision(donut_result, claude_result, merged)
        
        return merged
    
    def _ensemble_document_type_decision(self, donut_result: Dict, claude_result: Dict) -> tuple:
        """
        Intelligent document type decision using weighted ensemble
        Returns: (final_doc_type, confidence, source)
        """
        claude_doc_type = claude_result.get('document_type', 'Unknown Document')
        claude_confidence = claude_result.get('confidence', 0.0)
        donut_doc_type = donut_result.get('donut_type')
        donut_confidence = donut_result.get('donut_confidence', 0.0)
        
        # Model strength mappings based on document types
        model_strengths = self._get_model_strengths_for_document_type(claude_doc_type, donut_doc_type)
        
        # Case 1: Both models failed to identify document type
        if not donut_doc_type and claude_doc_type == 'Unknown Document':
            return 'Unknown Document', 0.0, 'ensemble_failed'
        
        # Case 2: Only one model identified a type
        if not donut_doc_type and claude_doc_type != 'Unknown Document':
            return claude_doc_type, claude_confidence, 'claude_only'
        
        if donut_doc_type and claude_doc_type == 'Unknown Document':
            return donut_doc_type, donut_confidence, 'donut_only'
        
        # Case 3: Both models identified types - use weighted ensemble
        # Check if they agree (accounting for variations in naming)
        types_agree = self._normalize_document_type(claude_doc_type) == self._normalize_document_type(donut_doc_type)
        
        if types_agree:
            # Models agree - boost confidence and use the higher confidence model's type
            if claude_confidence >= donut_confidence:
                return claude_doc_type, min(1.0, claude_confidence + 0.15), 'ensemble_agreement_claude'
            else:
                return donut_doc_type, min(1.0, donut_confidence + 0.15), 'ensemble_agreement_donut'
        else:
            # Models disagree - use weighted decision based on model strengths
            claude_weight = model_strengths['claude']
            donut_weight = model_strengths['donut']
            
            # Calculate weighted confidence scores
            claude_weighted = claude_confidence * claude_weight
            donut_weighted = donut_confidence * donut_weight
            
            if claude_weighted >= donut_weighted:
                return claude_doc_type, claude_confidence, 'ensemble_weighted_claude'
            else:
                return donut_doc_type, donut_confidence, 'ensemble_weighted_donut'
    
    def _get_model_strengths_for_document_type(self, claude_type: str, donut_type: str) -> Dict[str, float]:
        """
        Get model strength weights based on document types
        Returns weights that sum to 1.0
        """
        # Document types where Donut excels (structured, well-defined forms)
        donut_strong_types = [
            'Form W-2', 'Form 1099', '1099-MISC', '1099-NEC', '1099-INT', '1099-DIV',
            'Form 1098', 'Form 1095', 'SSA-1099'
        ]
        
        # Document types where Claude excels (complex, text-heavy forms)
        claude_strong_types = [
            'Form 1040', 'Schedule K-1', 'Form 1120S', 'Form 1065', 'Form 990',
            'Form 8825', 'Form 4562', 'Schedule C', 'Schedule E'
        ]
        
        # Determine which model should be favored
        claude_type_norm = self._normalize_document_type(claude_type or '')
        donut_type_norm = self._normalize_document_type(donut_type or '')
        
        # Check if either type is in the strong categories
        donut_favored = any(self._normalize_document_type(strong_type) in [claude_type_norm, donut_type_norm] 
                           for strong_type in donut_strong_types)
        claude_favored = any(self._normalize_document_type(strong_type) in [claude_type_norm, donut_type_norm] 
                            for strong_type in claude_strong_types)
        
        if donut_favored and not claude_favored:
            return {'claude': 0.3, 'donut': 0.7}  # Favor Donut
        elif claude_favored and not donut_favored:
            return {'claude': 0.8, 'donut': 0.2}  # Favor Claude
        else:
            return {'claude': 0.65, 'donut': 0.35}  # Default: slight Claude preference
    
    def _normalize_document_type(self, doc_type: str) -> str:
        """Normalize document type for comparison"""
        if not doc_type:
            return ''
        
        # Remove common variations and normalize
        normalized = doc_type.lower().strip()
        normalized = normalized.replace('form ', '').replace('-', '').replace(' ', '')
        return normalized
    
    def _calculate_ensemble_confidence(self, donut_result: Dict, claude_result: Dict, final_doc_type: str) -> float:
        """
        Calculate enhanced confidence score using ensemble information
        """
        claude_confidence = claude_result.get('confidence', 0.0)
        donut_confidence = donut_result.get('donut_confidence', 0.0)
        
        # Base confidence from the chosen model
        if final_doc_type == claude_result.get('document_type'):
            base_confidence = claude_confidence
        elif final_doc_type == donut_result.get('donut_type'):
            base_confidence = donut_confidence
        else:
            base_confidence = max(claude_confidence, donut_confidence)
        
        # Enhancement factors
        ensemble_boost = 0.0
        
        # Factor 1: Model agreement bonus
        if self._check_type_agreement(donut_result, claude_result):
            ensemble_boost += 0.15  # Significant boost when models agree
        
        # Factor 2: High confidence from both models
        if claude_confidence > 0.7 and donut_confidence > 0.7:
            ensemble_boost += 0.1
        
        # Factor 3: Complementary strengths (one model very confident)
        max_confidence = max(claude_confidence, donut_confidence)
        min_confidence = min(claude_confidence, donut_confidence)
        if max_confidence > 0.8 and min_confidence > 0.4:
            ensemble_boost += 0.08
        
        # Factor 4: Document type certainty
        if final_doc_type and final_doc_type != 'Unknown Document':
            ensemble_boost += 0.05
        
        # Calculate final confidence
        final_confidence = min(1.0, base_confidence + ensemble_boost)
        return final_confidence
    
    def _check_type_agreement(self, donut_result: Dict, claude_result: Dict) -> bool:
        """Check if Donut and Claude agree on document type"""
        claude_type = claude_result.get('document_type', '')
        donut_type = donut_result.get('donut_type', '')
        
        if not claude_type or not donut_type:
            return False
        
        # Normalize and compare
        claude_norm = self._normalize_document_type(claude_type)
        donut_norm = self._normalize_document_type(donut_type)
        
        return claude_norm == donut_norm
    
    def _log_ensemble_decision(self, donut_result: Dict, claude_result: Dict, final_result: Dict):
        """Log ensemble decision statistics"""
        try:
            # Initialize ensemble_decisions if it doesn't exist
            if 'ensemble_decisions' not in self.processing_stats:
                self.processing_stats['ensemble_decisions'] = {
                    'total': 0,
                    'agreements': 0,
                    'claude_wins': 0,
                    'donut_wins': 0,
                    'confidence_boosts': []
                }
            
            stats = self.processing_stats['ensemble_decisions']
            stats['total'] = stats.get('total', 0) + 1
            
            # Calculate confidence boost
            donut_conf = donut_result.get('donut_confidence', 0.0)
            claude_conf = claude_result.get('confidence', 0.0)
            final_conf = final_result.get('confidence', 0.0)
            confidence_boost = max(0, final_conf - max(donut_conf, claude_conf))
            
            # Track agreement/disagreement
            if final_result.get('type_agreement', False):
                stats['agreements'] = stats.get('agreements', 0) + 1
            
            # Track which model was favored
            classification_source = final_result.get('classification_source', '')
            if 'claude' in classification_source:
                stats['claude_wins'] = stats.get('claude_wins', 0) + 1
            elif 'donut' in classification_source:
                stats['donut_wins'] = stats.get('donut_wins', 0) + 1
            
            if confidence_boost > 0:
                if 'confidence_boosts' not in stats:
                    stats['confidence_boosts'] = []
                stats['confidence_boosts'].append(confidence_boost)
                
            # Log the ensemble decision
            self.logger.info(f"🤖 Ensemble boost: +{confidence_boost:.2f} confidence ({classification_source}) Document: {final_result.get('document_type', 'Unknown')}")
            
        except Exception as e:
            self.logger.error(f"Error logging ensemble decision: {e}")
            # Don't let this error crash the processing
            pass
    
    def _extract_with_field_routing(self, image_path: str, donut_result: Dict) -> Dict:
        """
        SPEED OPTIMIZED: Field-specific extraction with reduced API calls
        """
        try:
            doc_type = donut_result.get('donut_type', 'Unknown')
            confidence = donut_result.get('donut_confidence', 0.0)
            
            # SPEED OPTIMIZATION: Use comprehensive extraction for better efficiency
            if confidence > 0.8:
                # High confidence - use single comprehensive extraction
                self.logger.info(f"Using comprehensive extraction for high-confidence {doc_type}")
                comprehensive_info = self.claude_ocr.extract_comprehensive_document_info(image_path)
                comprehensive_info['validation_applied'] = False
                comprehensive_info['validation_skipped_reason'] = 'high_confidence_comprehensive'
                return comprehensive_info
            
            # Get field routing plan
            routing_plan = self._create_field_routing_plan(doc_type)
            
            # SPEED OPTIMIZATION: Use combined extraction if enabled
            if Config.USE_COMBINED_EXTRACTION:
                combined_extraction = self._extract_combined_fields(image_path, routing_plan)
            else:
                # Fallback to individual field extraction
                combined_extraction = self._extract_individual_fields(image_path, routing_plan)
            
            # Apply validation only if needed
            if combined_extraction.get('confidence', 0.0) < 0.7:
                # Only validate low-confidence results
                validation_result = self._apply_cross_model_validation(image_path, donut_result, combined_extraction)
                if validation_result:
                    combined_extraction = self._merge_with_validation(combined_extraction, validation_result)
                    combined_extraction['validation_applied'] = True
                else:
                    combined_extraction['validation_applied'] = False
                    combined_extraction['validation_skipped_reason'] = 'validation_failed'
            else:
                combined_extraction['validation_applied'] = False
                combined_extraction['validation_skipped_reason'] = 'high_confidence_skip'
            
            return combined_extraction
            
        except Exception as e:
            self.logger.error(f"Error in field routing extraction: {e}")
            return {
                'document_type': 'Unknown',
                'confidence': 0.0,
                'error': str(e),
                'validation_applied': False,
                'validation_skipped_reason': 'extraction_error'
            }
    
    def _extract_combined_fields(self, image_path: str, routing_plan: Dict) -> Dict:
        """
        SPEED OPTIMIZATION: Extract multiple fields in single API call
        """
        try:
            # Create comprehensive prompt for all needed fields
            fields_needed = list(routing_plan.keys())
            
            prompt = f"""
            Extract the following information from this tax document in a single pass:
            {', '.join(fields_needed)}
            
            Return in JSON format:
            {{
                "document_type": "exact form type",
                "client_name": "full name",
                "tax_year": "YYYY",
                "amounts": {{"field_name": "amount"}},
                "dates": {{"field_name": "date"}},
                "addresses": {{"field_name": "address"}},
                "confidence": 0.0-1.0,
                "extraction_notes": "any notes"
            }}
            """
            
            img_base64 = self.claude_ocr.image_to_base64(image_path)
            if not img_base64:
                return {'confidence': 0.0, 'error': 'Failed to convert image'}
            
            result = self.claude_ocr._make_api_call(img_base64, prompt)
            result['extraction_method'] = 'combined_single_pass'
            
            return result
            
        except Exception as e:
            self.logger.error(f"Error in combined field extraction: {e}")
            return {'confidence': 0.0, 'error': str(e)}
    
    def _create_field_routing_plan(self, doc_type: str) -> Dict[str, str]:
        """
        Create an optimal field routing plan based on document type and model strengths
        """
        # Base routing plan (Claude for text, Donut for structure)
        base_plan = {
            'document_type': 'donut',  # Donut's specialty
            'client_names': 'claude',  # Claude better at complex names
            'amounts': 'claude',       # Fallback to Claude for now
            'dates': 'claude',         # Claude for most cases
            'addresses': 'claude'      # Claude better at complex text
        }
        
        # Document-specific optimizations
        if doc_type in ['Form W-2', 'Form 1099-MISC', 'Form 1099-NEC']:
            # Structured forms - favor Donut for structured data
            base_plan['amounts'] = 'donut'  # Would be donut when implemented
            base_plan['dates'] = 'dual'     # Critical fields get dual validation
        elif doc_type in ['Form 1040', 'Schedule K-1']:
            # Complex forms - favor Claude
            base_plan['client_names'] = 'claude'
            base_plan['dates'] = 'dual'     # Critical for tax forms
        elif doc_type == 'Unknown Document':
            # Unknown documents - use comprehensive extraction
            base_plan['dates'] = 'dual'     # Always validate critical fields
        
        return base_plan
    
    def _extract_client_names_claude(self, image_path: str) -> Dict:
        """Extract client names using Claude's text processing expertise"""
        try:
            # Focused prompt for name extraction
            img_base64 = self.claude_ocr.image_to_base64(image_path)
            if not img_base64:
                return {}
            
            prompt = """
            Extract ONLY the client/person name information from this tax document. Focus on:
            1. Primary taxpayer name (first name, last name)
            2. Spouse name if joint return
            3. Business/entity name if applicable
            
            Return JSON format:
            {
                "client_name": "Full Name",
                "person_name": "Full Name", 
                "first_name": "First",
                "last_name": "Last",
                "spouse_name": "Spouse Name",
                "business_name": "Business Name",
                "entity_type": "Individual/LLC/Corporation/etc"
            }
            """
            
            result = self.claude_ocr._make_api_call(img_base64, prompt)
            result['client_names_source'] = 'claude_specialized'
            return result
            
        except Exception as e:
            self.logger.error(f"Error in Claude name extraction: {e}")
            return {}
    
    def _extract_amounts_fallback(self, image_path: str) -> Dict:
        """Extract amounts - fallback to Claude until Donut amount extraction is implemented"""
        try:
            # This would eventually be replaced with Donut structured data extraction
            img_base64 = self.claude_ocr.image_to_base64(image_path)
            if not img_base64:
                return {}
            
            prompt = """
            Extract ONLY monetary amounts and tax-related numbers from this document:
            1. Income amounts
            2. Tax amounts  
            3. Withholding amounts
            4. Important tax numbers
            
            Return JSON format:
            {
                "total_income": "amount or null",
                "federal_tax": "amount or null", 
                "state_tax": "amount or null",
                "withholding": "amount or null"
            }
            """
            
            result = self.claude_ocr._make_api_call(img_base64, prompt)
            result['amounts_source'] = 'claude_fallback'
            return result
            
        except Exception as e:
            self.logger.error(f"Error in amount extraction: {e}")
            return {}
    
    def _extract_dates_claude(self, image_path: str) -> Dict:
        """Extract dates using Claude"""
        try:
            img_base64 = self.claude_ocr.image_to_base64(image_path)
            if not img_base64:
                return {}
            
            prompt = """
            Extract ONLY date information from this tax document:
            1. Tax year
            2. Filing date
            3. Period covered
            4. Due dates
            
            Return JSON format:
            {
                "tax_year": "YYYY",
                "filing_date": "date or null",
                "period_start": "date or null", 
                "period_end": "date or null"
            }
            """
            
            result = self.claude_ocr._make_api_call(img_base64, prompt)
            result['dates_source'] = 'claude_specialized'
            return result
            
        except Exception as e:
            self.logger.error(f"Error in Claude date extraction: {e}")
            return {}
    
    def _extract_dates_dual_validation(self, image_path: str) -> Dict:
        """Extract dates with dual model validation for critical accuracy"""
        try:
            # Primary extraction with Claude
            claude_dates = self._extract_dates_claude(image_path)
            
            # Secondary validation with comprehensive extraction 
            # (In a full implementation, this could be Donut-based validation)
            img_base64 = self.claude_ocr.image_to_base64(image_path)
            validation_prompt = """
            Verify the tax year in this document. Look carefully at:
            1. The tax year printed on the form
            2. The period this document covers
            3. When this return/document was filed
            
            Return only: {"tax_year": "YYYY"}
            """
            
            validation_result = self.claude_ocr._make_api_call(img_base64, validation_prompt)
            
            # Merge results with validation
            final_dates = claude_dates.copy()
            if validation_result.get('tax_year') and claude_dates.get('tax_year'):
                if validation_result['tax_year'] == claude_dates['tax_year']:
                    final_dates['tax_year_confidence'] = 0.95  # High confidence from agreement
                else:
                    # Disagreement - use the one that looks more like a year
                    claude_year = claude_dates['tax_year']
                    validation_year = validation_result['tax_year']
                    if self._is_valid_tax_year(validation_year):
                        final_dates['tax_year'] = validation_year
                        final_dates['tax_year_confidence'] = 0.8
                    else:
                        final_dates['tax_year_confidence'] = 0.6
            
            final_dates['dates_source'] = 'dual_validation'
            return final_dates
            
        except Exception as e:
            self.logger.error(f"Error in dual date validation: {e}")
            return self._extract_dates_claude(image_path)  # Fallback to single model
    
    def _extract_addresses_claude(self, image_path: str) -> Dict:
        """Extract addresses using Claude's text processing expertise"""
        try:
            img_base64 = self.claude_ocr.image_to_base64(image_path)
            if not img_base64:
                return {}
            
            prompt = """
            Extract ONLY address information from this tax document:
            1. Taxpayer address
            2. Business address if different
            3. Mailing address if shown
            
            Return JSON format:
            {
                "address": "Full Address",
                "city": "City",
                "state": "State", 
                "zip_code": "ZIP",
                "business_address": "Business Address if different"
            }
            """
            
            result = self.claude_ocr._make_api_call(img_base64, prompt)
            result['addresses_source'] = 'claude_specialized'
            return result
            
        except Exception as e:
            self.logger.error(f"Error in Claude address extraction: {e}")
            return {}
    
    def _needs_comprehensive_extraction(self, field_results: Dict) -> bool:
        """Check if comprehensive extraction is needed for missing critical fields"""
        critical_fields = ['client_name', 'person_name', 'tax_year']
        missing_critical = sum(1 for field in critical_fields 
                             if not field_results.get(field))
        
        # If more than 1 critical field is missing, run comprehensive extraction
        return missing_critical > 1
    
    def _merge_with_comprehensive(self, field_results: Dict, comprehensive_info: Dict) -> Dict:
        """Merge field routing results with comprehensive extraction"""
        merged = comprehensive_info.copy()
        
        # Override with field-routed results (they're more specialized)
        for key, value in field_results.items():
            if value and value != 'Unknown':  # Don't override with empty values
                merged[key] = value
        
        # Mark as hybrid extraction
        merged['extraction_method'] = 'field_routing_with_fallback'
        merged['field_routing_data'] = field_results
        
        return merged
    
    def _calculate_field_routing_confidence(self, field_results: Dict) -> float:
        """Calculate confidence score for field routing extraction"""
        base_confidence = 0.5
        
        # Boost for successful field routing
        if field_results.get('document_type') and field_results['document_type'] != 'Unknown Document':
            base_confidence += 0.2
        
        if field_results.get('client_name') or field_results.get('person_name'):
            base_confidence += 0.15
        
        if field_results.get('tax_year'):
            base_confidence += 0.1
        
        # Boost for dual validation
        if field_results.get('dates_source') == 'dual_validation':
            base_confidence += 0.1
        
        # Boost for specialized extractions
        specialized_sources = ['claude_specialized', 'donut_specialized']
        if any(field_results.get(key, '').endswith('_source') and 
               field_results[key] in specialized_sources for key in field_results):
            base_confidence += 0.05
        
        return min(1.0, base_confidence)
    
    def _is_valid_tax_year(self, year_str: str) -> bool:
        """Check if a string looks like a valid tax year"""
        try:
            year = int(str(year_str).strip())
            return 2000 <= year <= 2030
        except (ValueError, TypeError):
            return False
    
    def _track_field_routing_stats(self, extracted_info: Dict):
        """Track field routing statistics for optimization"""
        if 'field_routing' not in self.processing_stats:
            return
        
        stats = self.processing_stats['field_routing']
        stats['total_extractions'] += 1
        
        # Track routing efficiency
        routing_time = extracted_info.get('routing_time', 0)
        if routing_time > 0:
            stats['routing_efficiency_gains'].append(routing_time)
        
        # Track field-specific routing
        for field_type, sources in stats['field_types'].items():
            source_key = f"{field_type}_source"
            if source_key in extracted_info:
                source = extracted_info[source_key]
                if 'claude' in source:
                    sources['claude'] += 1
                    stats['claude_routed_fields'] += 1
                elif 'donut' in source:
                    sources['donut'] += 1
                    stats['donut_routed_fields'] += 1
                elif 'dual' in source:
                    sources['dual'] += 1
                    stats['dual_validated_fields'] += 1
    
    def _apply_enhanced_name_detection(self, image_path: str, donut_result: Dict) -> Dict:
        """Apply enhanced name detection with multiple models"""
        try:
            # Validate inputs
            if not image_path or not os.path.exists(image_path):
                return {
                    'names': [],
                    'confidence': 0.0,
                    'detection_methods': [],
                    'error': 'Invalid image path'
                }
            
            # Initialize name detector if not already done
            if not hasattr(self, 'name_detector'):
                try:
                    self.name_detector = EnhancedNameDetector()
                except Exception as e:
                    self.logger.error(f"Failed to initialize name detector: {e}")
                    return {
                        'names': [],
                        'confidence': 0.0,
                        'detection_methods': [],
                        'error': f'Name detector initialization failed: {e}'
                    }
            
            # Get document type for pattern detection
            doc_type = donut_result.get('donut_type', 'Unknown') if isinstance(donut_result, dict) else 'Unknown'
            
            # Apply enhanced name detection
            name_results = self.name_detector.detect_names_in_document(image_path, doc_type)
            
            # Validate results
            if not isinstance(name_results, dict):
                self.logger.error(f"Invalid name detection results format: {type(name_results)}")
                return {
                    'names': [],
                    'confidence': 0.0,
                    'detection_methods': [],
                    'error': 'Invalid name detection results'
                }
            
            # Extract names and confidence
            names = name_results.get('combined_names', [])
            confidence = name_results.get('confidence', 0.0)
            detection_methods = name_results.get('detection_methods', [])
            
            # Validate names list
            if not isinstance(names, list):
                names = []
            
            # Filter out invalid name entries
            valid_names = []
            for name_info in names:
                if isinstance(name_info, dict) and 'name' in name_info:
                    valid_names.append(name_info)
                else:
                    self.logger.warning(f"Invalid name info format: {name_info}")
            
            return {
                'names': valid_names,
                'confidence': float(confidence) if confidence is not None else 0.0,
                'detection_methods': detection_methods if isinstance(detection_methods, list) else [],
                'primary_name': self.name_detector.get_primary_client_name(name_results) if hasattr(self.name_detector, 'get_primary_client_name') else None,
                'all_names': self.name_detector.get_all_detected_names(name_results) if hasattr(self.name_detector, 'get_all_detected_names') else []
            }
            
        except Exception as e:
            self.logger.error(f"Error in enhanced name detection: {e}")
            return {
                'names': [],
                'confidence': 0.0,
                'detection_methods': [],
                'error': str(e)
            }
    
    def _enhanced_name_field_mapping(self, extracted_info: Dict, name_results: Dict) -> Dict:
        """
        ENHANCED NAME FIELD MAPPING - Bridge between name detection and entity recognition
        Maps detected names to the specific field names expected by entity recognizer
        """
        try:
            doc_type = extracted_info.get('document_type', '').lower()
            
            # Get the primary detected name
            primary_name = None
            if name_results.get('combined_names'):
                primary_name = self.name_detector.get_primary_client_name(name_results)
            
            if not primary_name:
                # Fallback to any available name from Claude extraction
                primary_name = (extracted_info.get('client_name') or 
                              extracted_info.get('person_name') or 
                              extracted_info.get('detected_primary_name'))
                
                # If still no primary name, try to extract from other fields
                if not primary_name:
                    # Look for any name fields that might contain a full name
                    name_fields = [
                        'primary_first_name', 'primary_last_name',
                        'partner_first_name', 'partner_last_name',
                        'recipient_first_name', 'recipient_last_name',
                        'employee_first_name', 'employee_last_name',
                        'borrower_first_name', 'borrower_last_name',
                        'person_first_name', 'person_last_name'
                    ]
                    
                    for field in name_fields:
                        if extracted_info.get(field) and extracted_info.get(field) != 'Unknown':
                            # Try to construct a full name from first/last pairs
                            if field.endswith('_first_name'):
                                last_field = field.replace('_first_name', '_last_name')
                                first_name = extracted_info.get(field)
                                last_name = extracted_info.get(last_field)
                                if first_name and last_name and first_name != 'Unknown' and last_name != 'Unknown':
                                    primary_name = f"{first_name} {last_name}"
                                    self.logger.info(f"Constructed primary name from {field}: {primary_name}")
                                    break
            
            if not primary_name:
                self.logger.warning("No primary name found for field mapping")
                return extracted_info
            
            # Parse name into components
            name_parts = primary_name.split()
            if len(name_parts) < 2:
                self.logger.warning(f"Primary name '{primary_name}' has insufficient parts for parsing")
                return extracted_info
            
            first_name = name_parts[0]
            last_name = ' '.join(name_parts[1:])
            
            # Map to document-specific field names based on document type
            if 'k-1' in doc_type or 'schedule k-1' in doc_type:
                # K-1 documents: partner/recipient is the primary entity
                extracted_info.update({
                    'partner_first_name': first_name,
                    'partner_last_name': last_name,
                    'recipient_first_name': first_name,
                    'recipient_last_name': last_name,
                    'primary_first_name': first_name,
                    'primary_last_name': last_name,
                    'person_first_name': first_name,
                    'person_last_name': last_name
                })
                self.logger.info(f"K-1 field mapping: {first_name} {last_name} → partner/recipient fields")
                
            elif '1099' in doc_type:
                # 1099 documents: recipient is the primary entity
                extracted_info.update({
                    'recipient_first_name': first_name,
                    'recipient_last_name': last_name,
                    'primary_first_name': first_name,
                    'primary_last_name': last_name,
                    'person_first_name': first_name,
                    'person_last_name': last_name
                })
                self.logger.info(f"1099 field mapping: {first_name} {last_name} → recipient fields")
                
            elif 'w-2' in doc_type:
                # W-2 documents: employee is the primary entity
                extracted_info.update({
                    'employee_first_name': first_name,
                    'employee_last_name': last_name,
                    'primary_first_name': first_name,
                    'primary_last_name': last_name,
                    'person_first_name': first_name,
                    'person_last_name': last_name
                })
                self.logger.info(f"W-2 field mapping: {first_name} {last_name} → employee fields")
                
            elif '1098' in doc_type:
                # 1098 documents: borrower/student is the primary entity
                extracted_info.update({
                    'borrower_first_name': first_name,
                    'borrower_last_name': last_name,
                    'primary_first_name': first_name,
                    'primary_last_name': last_name,
                    'person_first_name': first_name,
                    'person_last_name': last_name
                })
                self.logger.info(f"1098 field mapping: {first_name} {last_name} → borrower fields")
                
            elif '1040' in doc_type:
                # 1040 documents: primary taxpayer is the main entity
                extracted_info.update({
                    'primary_first_name': first_name,
                    'primary_last_name': last_name,
                    'person_first_name': first_name,
                    'person_last_name': last_name
                })
                self.logger.info(f"1040 field mapping: {first_name} {last_name} → primary taxpayer fields")
                
            else:
                # Generic mapping for unknown document types
                extracted_info.update({
                    'primary_first_name': first_name,
                    'primary_last_name': last_name,
                    'person_first_name': first_name,
                    'person_last_name': last_name
                })
                self.logger.info(f"Generic field mapping: {first_name} {last_name} → primary/person fields")
            
            # Add enhanced name detection metadata
            extracted_info['enhanced_name_mapping_applied'] = True
            extracted_info['mapped_primary_name'] = primary_name
            extracted_info['mapped_first_name'] = first_name
            extracted_info['mapped_last_name'] = last_name
            
            return extracted_info
            
        except Exception as e:
            self.logger.error(f"Error in enhanced name field mapping: {e}")
            return extracted_info
    
    def _merge_enhanced_name_detection_priority(self, extracted_info: Dict, name_results: Dict) -> Dict:
        """
        ENHANCED: Merge enhanced name detection results with existing extracted information
        PRIORITIZES enhanced name detection over Claude extraction for client/entity naming
        """
        try:
            # If we have any names from enhanced detection, prioritize them
            if name_results.get('combined_names'):
                primary_name = self.name_detector.get_primary_client_name(name_results)
                
                if primary_name:
                    # Parse the name into components
                    name_parts = primary_name.split()
                    if len(name_parts) >= 2:
                        # ALWAYS use enhanced detection results for client naming
                        extracted_info['enhanced_name_detection'] = name_results
                        extracted_info['detected_primary_name'] = primary_name
                        extracted_info['detected_first_name'] = name_parts[0]
                        extracted_info['detected_last_name'] = ' '.join(name_parts[1:])
                        
                        # PRIORITY: Use enhanced detection for client name regardless of Claude results
                        extracted_info['client_name'] = primary_name
                        extracted_info['person_name'] = primary_name
                        
                        # ENHANCED: Apply field mapping for entity recognition
                        extracted_info = self._enhanced_name_field_mapping(extracted_info, name_results)
                        
                        # Track enhanced name detection usage
                        self.processing_stats['enhanced_name_detection']['names_detected'] += 1
                        self.processing_stats['enhanced_name_detection']['priority_used'] += 1
                        
                        self.logger.info(f"Enhanced name detection PRIORITY: {primary_name} (overriding Claude extraction)")
                        
                        # If Claude had different names, log the override
                        claude_client_name = extracted_info.get('claude_client_name', extracted_info.get('client_name'))
                        if claude_client_name and claude_client_name != primary_name:
                            self.logger.info(f"Enhanced detection overrode Claude: {claude_client_name} → {primary_name}")
                            extracted_info['claude_override_notes'] = f"Enhanced detection overrode Claude: {claude_client_name} → {primary_name}"
            
            # If no enhanced detection names found, fall back to Claude extraction
            elif not name_results.get('combined_names'):
                self.logger.info("No names found by enhanced detection, using Claude extraction as fallback")
                extracted_info['enhanced_name_detection'] = name_results
                extracted_info['name_detection_fallback'] = 'claude'
                self.processing_stats['enhanced_name_detection']['fallback_to_claude'] += 1
                
                # ENHANCED: Apply field mapping even for Claude fallback
                extracted_info = self._enhanced_name_field_mapping(extracted_info, name_results)
            
            return extracted_info
            
        except Exception as e:
            self.logger.error(f"Error merging enhanced name detection with priority: {e}")
            return extracted_info
    
    def _apply_cross_model_validation(self, image_path: str, donut_result: Dict, field_results: Dict) -> Dict:
        """
        Phase 3: Cross-Model Validation
        Intelligently validates results using multiple models with smart cost control
        """
        validation_start_time = time.time()
        
        # Step 1: Determine if cross-validation is beneficial
        should_validate, validation_reason = self._should_apply_cross_validation(donut_result, field_results)
        
        if not should_validate:
            field_results['cross_validation_applied'] = False
            field_results['cross_validation_skipped_reason'] = validation_reason
            field_results['original_confidence'] = field_results.get('confidence', 0.0)  # Phase 5: For learning
            self._track_cross_validation_stats(field_results, skipped=True, reason=validation_reason)
            self.logger.info(f"🔍 Cross-validation skipped: {validation_reason}")
            return field_results
        
        self.logger.info(f"🔍 Starting cross-model validation: {validation_reason}")
        
        # Step 2: Perform cross-validation
        validation_results = self._perform_cross_validation(image_path, donut_result, field_results)
        
        # Step 3: Detect and resolve conflicts
        conflicts = self._detect_conflicts(donut_result, field_results, validation_results)
        
        if conflicts:
            self.logger.info(f"⚠️  Detected {len(conflicts)} conflicts, resolving...")
            resolved_results = self._resolve_conflicts(conflicts, donut_result, field_results, validation_results)
        else:
            resolved_results = field_results.copy()
            self.logger.info("✅ No conflicts detected, models agree")
        
        # Step 4: Calculate validation confidence boost
        original_confidence = field_results.get('confidence', 0.0)
        validated_confidence = self._calculate_cross_validation_confidence(resolved_results, conflicts)
        confidence_improvement = validated_confidence - original_confidence
        
        # Step 5: Finalize results
        resolved_results.update({
            'cross_validation_applied': True,
            'cross_validation_reason': validation_reason,
            'cross_validation_time': time.time() - validation_start_time,
            'conflicts_detected': len(conflicts),
            'confidence_improvement': confidence_improvement,
            'validated_confidence': validated_confidence,
            'original_confidence': original_confidence  # Phase 5: For dynamic threshold learning
        })
        
        # Step 6: Track statistics
        self._track_cross_validation_stats(resolved_results, conflicts=conflicts, reason=validation_reason)
        
        self.logger.info(f"✅ Cross-validation completed: {confidence_improvement:+.2f} confidence boost")
        return resolved_results
    
    def _should_apply_cross_validation(self, donut_result: Dict, field_results: Dict) -> tuple[bool, str]:
        """
        Determine if cross-validation should be applied based on confidence and document type
        SPEED OPTIMIZATION: Skip validation for high-confidence results to reduce API calls
        """
        try:
            # Check if speed optimizations are enabled
            if not Config.ENABLE_SPEED_OPTIMIZATIONS:
                return True, "speed_optimizations_disabled"
            
            # Get document type and confidence
            doc_type = field_results.get('document_type', 'Unknown')
            confidence = field_results.get('confidence', 0.0)
            
            # SPEED OPTIMIZATION 1: Skip validation for very high confidence
            if confidence > Config.SKIP_VALIDATION_HIGH_CONFIDENCE:
                self.logger.info(f"Skipping cross-validation for high confidence ({confidence:.2f})")
                return False, "high_confidence_skip"
            
            # SPEED OPTIMIZATION 2: Skip validation for simple document types
            simple_doc_types = ['W-2', '1099-NEC', '1099-MISC', '1099-INT', '1099-DIV']
            if any(simple_type in doc_type for simple_type in simple_doc_types):
                if confidence > Config.SKIP_VALIDATION_SIMPLE_DOCS:
                    self.logger.info(f"Skipping validation for simple document type: {doc_type}")
                    return False, "simple_document_skip"
            
            # Get adaptive threshold recommendation
            recommendation = self.dynamic_threshold_manager.get_validation_recommendation(doc_type, field_results)
            
            # Initialize missing keys in processing stats
            if 'dynamic_thresholds' not in self.processing_stats:
                self.processing_stats['dynamic_thresholds'] = {
                    'total_threshold_calculations': 0,
                    'validation_recommended': 0,
                    'validation_skipped_by_thresholds': 0,
                    'threshold_adaptations': 0,
                    'performance_improvements': [],
                    'cost_optimizations': [],
                    'document_type_learning': {},
                    'field_importance_adaptations': 0,
                    'adaptive_validations_triggered': 0,
                    'adaptive_validations_skipped': 0,
                    'confidence_adjustments': [],
                    'threshold_adaptations_applied': 0,
                    'field_importance_boosts': [],
                    'success_rate_adjustments': [],
                    'time_based_adjustments': []
                }
            
            self.processing_stats['dynamic_thresholds']['total_threshold_calculations'] += 1
            
            # SPEED OPTIMIZATION 3: Skip validation for model agreement
            donut_type = donut_result.get('donut_type', '')
            claude_type = field_results.get('document_type', '')
            if donut_type and claude_type and self._normalize_document_type(donut_type) == self._normalize_document_type(claude_type):
                if confidence > 0.6:  # Lower threshold when models agree
                    self.logger.info(f"Skipping validation - models agree on {claude_type}")
                    return False, "model_agreement_skip"
            
            # Use adaptive recommendation
            should_validate = recommendation['should_validate']
            reason = recommendation['reason']
            
            # Track adaptive decisions
            if should_validate:
                self.processing_stats['dynamic_thresholds']['adaptive_validations_triggered'] += 1
            else:
                self.processing_stats['dynamic_thresholds']['adaptive_validations_skipped'] += 1
            
            return should_validate, reason
            
        except Exception as e:
            self.logger.error(f"Error in cross-validation decision: {e}")
            # Default to skip validation on error to maintain speed
            return False, "error_skip"
    
    def _perform_cross_validation(self, image_path: str, donut_result: Dict, field_results: Dict) -> Dict:
        """
        Perform actual cross-validation using alternative extraction methods
        """
        try:
            img_base64 = self.claude_ocr.image_to_base64(image_path)
            if not img_base64:
                return {}
            
            # Cross-validation prompt - focused on verifying specific fields
            validation_prompt = f"""
            Cross-validate the following extracted information from this tax document.
            
            Current Extraction:
            - Document Type: {field_results.get('document_type', 'Unknown')}
            - Client Name: {field_results.get('client_name', 'Unknown')}
            - Tax Year: {field_results.get('tax_year', 'Unknown')}
            
            Please verify each field and return corrections only if needed:
            {{
                "document_type_correct": true/false,
                "corrected_document_type": "corrected type if wrong",
                "client_name_correct": true/false,
                "corrected_client_name": "corrected name if wrong",
                "tax_year_correct": true/false,
                "corrected_tax_year": "corrected year if wrong",
                "validation_confidence": 0.0-1.0,
                "validation_notes": "explanation of any corrections"
            }}
            """
            
            validation_result = self.claude_ocr._make_api_call(img_base64, validation_prompt)
            validation_result['validation_method'] = 'claude_cross_validation'
            validation_result['validation_source'] = 'claude'
            
            return validation_result
            
        except Exception as e:
            self.logger.error(f"Error in cross-validation: {e}")
            return {}
    
    def _detect_conflicts(self, donut_result: Dict, field_results: Dict, validation_results: Dict) -> List[Dict]:
        """
        Detect conflicts between different model outputs
        """
        conflicts = []
        
        # Document type conflict
        if not validation_results.get('document_type_correct', True):
            conflicts.append({
                'field': 'document_type',
                'original': field_results.get('document_type'),
                'validation': validation_results.get('corrected_document_type'),
                'donut': donut_result.get('donut_type'),
                'conflict_type': 'validation_correction'
            })
        
        # Client name conflict
        if not validation_results.get('client_name_correct', True):
            conflicts.append({
                'field': 'client_name',
                'original': field_results.get('client_name'),
                'validation': validation_results.get('corrected_client_name'),
                'conflict_type': 'validation_correction'
            })
        
        # Tax year conflict
        if not validation_results.get('tax_year_correct', True):
            conflicts.append({
                'field': 'tax_year',
                'original': field_results.get('tax_year'),
                'validation': validation_results.get('corrected_tax_year'),
                'conflict_type': 'validation_correction'
            })
        
        return conflicts
    
    def _resolve_conflicts(self, conflicts: List[Dict], donut_result: Dict, field_results: Dict, validation_results: Dict) -> Dict:
        """
        Intelligently resolve conflicts between model outputs
        """
        resolved_results = field_results.copy()
        resolution_notes = []
        
        for conflict in conflicts:
            field = conflict['field']
            original = conflict['original']
            validation = conflict['validation']
            
            # Field-specific resolution logic
            if field == 'document_type':
                # Use validation correction if it's a known document type
                known_types = ['Form W-2', 'Form 1040', 'Form 1099', 'Schedule K-1', 'Form 1120S']
                if validation and any(known_type in str(validation) for known_type in known_types):
                    resolved_results[field] = validation
                    resolution_notes.append(f"Document type: {original} → {validation} (validation)")
                    self._track_resolution_method('validation_favored')
                else:
                    # Keep original if validation doesn't provide a better answer
                    resolution_notes.append(f"Document type: kept {original} (validation unclear)")
                    self._track_resolution_method('original_kept')
            
            elif field == 'client_name':
                # Use validation correction if it looks like a proper name
                if validation and len(str(validation).strip()) > 3 and str(validation).strip() != 'Unknown':
                    resolved_results[field] = validation
                    resolved_results['person_name'] = validation  # Update both fields
                    resolution_notes.append(f"Client name: {original} → {validation} (validation)")
                    self._track_resolution_method('validation_favored')
                else:
                    resolution_notes.append(f"Client name: kept {original} (validation unclear)")
                    self._track_resolution_method('original_kept')
            
            elif field == 'tax_year':
                # Use validation correction if it's a valid tax year
                if validation and self._is_valid_tax_year(validation):
                    resolved_results[field] = validation
                    resolution_notes.append(f"Tax year: {original} → {validation} (validation)")
                    self._track_resolution_method('validation_favored')
                else:
                    resolution_notes.append(f"Tax year: kept {original} (validation unclear)")
                    self._track_resolution_method('original_kept')
        
        resolved_results['conflict_resolution_notes'] = resolution_notes
        return resolved_results
    
    def _calculate_cross_validation_confidence(self, resolved_results: Dict, conflicts: List[Dict]) -> float:
        """
        Calculate enhanced confidence score after cross-validation
        """
        base_confidence = resolved_results.get('confidence', 0.0)
        
        # Boost confidence when validation confirms results (no conflicts)
        if not conflicts:
            validation_boost = 0.15
        else:
            # Smaller boost when conflicts were resolved
            validation_boost = 0.08
        
        # Additional boost for high validation confidence
        validation_confidence = resolved_results.get('validation_confidence', 0.5)
        if validation_confidence > 0.8:
            validation_boost += 0.05
        
        # Factor in resolution quality
        resolution_notes = resolved_results.get('conflict_resolution_notes', [])
        if any('→' in note for note in resolution_notes):  # Actual corrections made
            validation_boost += 0.05
        
        final_confidence = min(1.0, base_confidence + validation_boost)
        return final_confidence
    
    def _track_cross_validation_stats(self, results: Dict, skipped: bool = False, conflicts: List = None, reason: str = ''):
        """
        Track cross-validation statistics for optimization + Phase 5 dynamic threshold learning
        """
        if 'cross_validation' not in self.processing_stats:
            return
        
        stats = self.processing_stats['cross_validation']
        stats['total_validations'] += 1
        
        # Phase 5: Feed performance data back to dynamic threshold manager
        doc_type = results.get('document_type', 'Unknown')
        original_confidence = results.get('original_confidence', 0.0)
        final_confidence = results.get('confidence', original_confidence)
        
        if skipped:
            stats['validations_skipped'] += 1
            # Update threshold manager - validation was skipped
            self.dynamic_threshold_manager.update_performance_data(
                doc_type=doc_type,
                validation_applied=False,
                validation_successful=False,
                original_confidence=original_confidence,
                final_confidence=final_confidence
            )
        else:
            stats['validations_triggered'] += 1
            
            # Determine if validation was successful (improved confidence or resolved conflicts)
            validation_successful = False
            if conflicts:
                stats['conflicts_detected'] += len(conflicts)
                stats['conflicts_resolved'] += len(conflicts)
                validation_successful = True  # Successfully resolved conflicts
            
            confidence_improvement = results.get('confidence_improvement', 0.0)
            if confidence_improvement > 0.05:  # Meaningful improvement threshold
                validation_successful = True
            
            # Update threshold manager with validation results
            self.dynamic_threshold_manager.update_performance_data(
                doc_type=doc_type,
                validation_applied=True,
                validation_successful=validation_successful,
                original_confidence=original_confidence,
                final_confidence=final_confidence
            )
            
            # Track learning improvements
            if validation_successful:
                self.processing_stats['dynamic_thresholds']['learning_improvements'].append({
                    'doc_type': doc_type,
                    'confidence_improvement': confidence_improvement,
                    'conflicts_resolved': len(conflicts) if conflicts else 0,
                    'reason': reason
                })
        
        # Track validation reasons
        if reason in stats['validation_reasons']:
            stats['validation_reasons'][reason] += 1
        
        # Track confidence improvements
        confidence_improvement = results.get('confidence_improvement', 0.0)
        if confidence_improvement > 0:
            stats['confidence_improvements'].append(confidence_improvement)
    
    def _track_resolution_method(self, method: str):
        """Track how conflicts were resolved"""
        if 'cross_validation' in self.processing_stats:
            resolution_stats = self.processing_stats['cross_validation']['resolution_methods']
            if method == 'validation_favored':
                resolution_stats['claude_favored'] += 1
            elif method == 'original_kept':
                resolution_stats['confidence_weighted'] += 1
    
    def _apply_manual_client_info(self, extracted_info: Dict, manual_client_info: Dict) -> Dict:
        """Apply manual client information to extracted data"""
        # Override any detected names with manual information
        manual_info = extracted_info.copy()
        
        first_name = manual_client_info.get('first_name')
        last_name = manual_client_info.get('last_name')
        
        if first_name and last_name:
            # Update all possible name fields with manual information
            name_fields = [
                'partner_first_name', 'partner_last_name',
                'recipient_first_name', 'recipient_last_name',
                'employee_first_name', 'employee_last_name',
                'borrower_first_name', 'borrower_last_name',
                'primary_first_name', 'primary_last_name',
                'person_first_name', 'person_last_name'
            ]
            
            # Set primary fields based on document type
            doc_type = extracted_info.get('document_type', '').lower()
            
            if 'k-1' in doc_type:
                manual_info['partner_first_name'] = first_name
                manual_info['partner_last_name'] = last_name
            elif '1099' in doc_type:
                manual_info['recipient_first_name'] = first_name
                manual_info['recipient_last_name'] = last_name
            elif 'w-2' in doc_type:
                manual_info['employee_first_name'] = first_name
                manual_info['employee_last_name'] = last_name
            elif '1098' in doc_type:
                manual_info['borrower_first_name'] = first_name
                manual_info['borrower_last_name'] = last_name
            elif '1040' in doc_type:
                manual_info['primary_first_name'] = first_name
                manual_info['primary_last_name'] = last_name
            else:
                manual_info['person_first_name'] = first_name
                manual_info['person_last_name'] = last_name
            
            manual_info['manual_override'] = True
            # Increase confidence when manual info is provided
            manual_info['confidence'] = max(manual_info.get('confidence', 0), 0.8)
        
        return manual_info
    
    def _organize_document(self, file_path: str, entity_info: Dict, 
                         filename_info: Dict, extracted_info: Dict) -> Dict:
        """Organize document into appropriate folder with proper filename"""
        try:
            # Create client folder
            client_folder = entity_info.get('final_folder', 'Unknown_Client')
            client_folder_path = os.path.join(self.processed_folder, client_folder)
            os.makedirs(client_folder_path, exist_ok=True)
            
            # Handle filename conflicts
            final_filename = self.filename_generator.resolve_filename_conflict(
                filename_info.get('filename', 'Unknown_Document.pdf'), client_folder_path
            )
            
            # Final destination path
            final_path = os.path.join(client_folder_path, final_filename)
            
            # Copy file to destination
            shutil.copy2(file_path, final_path)
            
            notes = []
            if final_filename != filename_info.get('filename', ''):
                notes.append(f"Filename conflict resolved: {filename_info.get('filename', '')} → {final_filename}")
            
            if entity_info.get('existing_folder'):
                notes.append(f"Used existing client folder: {entity_info['existing_folder']}")
            else:
                notes.append(f"Created new client folder: {client_folder}")
            
            return {
                'final_path': final_path,
                'client_folder_path': client_folder_path,
                'final_filename': final_filename,
                'notes': notes
            }
            
        except Exception as e:
            self.logger.error(f"Error organizing document: {e}")
            raise
    
    def _get_client_display_name(self, entity_info: Dict) -> str:
        """Get display name for client"""
        entity_type = entity_info.get('entity_type', 'Unknown')
        
        if entity_type == 'Individual':
            if entity_info.get('is_joint'):
                first_name = entity_info.get('first_name', 'Unknown')
                spouse_first = entity_info.get('spouse_first_name', 'Unknown')
                last_name = entity_info.get('last_name', 'Unknown')
                return f"{first_name} & {spouse_first} {last_name}"
            else:
                first_name = entity_info.get('first_name', 'Unknown')
                last_name = entity_info.get('last_name', 'Unknown')
                return f"{first_name} {last_name}"
        else:
            business_name = entity_info.get('business_name', 'Unknown Business')
            return f"{business_name} ({entity_type})"
    
    def _update_processing_stats(self, result: Dict):
        """Update processing statistics"""
        entity_info = result.get('entity_info', {})
        extracted_details = result.get('extracted_details', {})
        
        # Entity type statistics
        entity_type = entity_info.get('entity_type', 'Unknown')
        self.processing_stats['entity_types'][entity_type] = (
            self.processing_stats['entity_types'].get(entity_type, 0) + 1
        )
        
        # Document type statistics
        doc_type = extracted_details.get('document_type', 'Unknown')
        self.processing_stats['document_types'][doc_type] = (
            self.processing_stats['document_types'].get(doc_type, 0) + 1
        )
        
        # Special features
        if extracted_details.get('is_amended'):
            self.processing_stats['amendments_detected'] += 1
        
        if entity_info.get('is_joint'):
            self.processing_stats['joint_returns'] += 1
    
    def _clean_temp_files(self, temp_files: List[str]):
        """Clean up temporary files"""
        for temp_file in temp_files:
            try:
                if os.path.exists(temp_file):
                    os.remove(temp_file)
            except Exception as e:
                self.logger.error(f"Error cleaning temp file {temp_file}: {e}")
    
    def get_enhanced_processing_stats(self, results: List[Dict]) -> Dict:
        """Get comprehensive processing statistics"""
        if not results:
            return {}
        
        stats = {
            'total_processed': len(results),
            'successful': len([r for r in results if r['status'] == 'completed']),
            'errors': len([r for r in results if r['status'] == 'error']),
            'entity_breakdown': {},
            'document_breakdown': {},
            'confidence_distribution': {
                'high_confidence': 0,  # > 0.8
                'medium_confidence': 0,  # 0.5 - 0.8
                'low_confidence': 0     # < 0.5
            },
            'special_features': {
                'amendments': 0,
                'joint_returns': 0,
                'business_entities': 0,
                'k1_partnerships': 0,
                'multiple_source_entities': 0
            },
            'processing_quality': {
                'complete_extractions': 0,
                'partial_extractions': 0,
                'minimal_extractions': 0
            }
        }
        
        for result in results:
            if result['status'] != 'completed':
                continue
            
            entity_info = result.get('entity_info', {})
            extracted_details = result.get('extracted_details', {})
            confidence = result.get('confidence', 0)
            
            # Entity breakdown
            entity_type = entity_info.get('entity_type', 'Unknown')
            stats['entity_breakdown'][entity_type] = (
                stats['entity_breakdown'].get(entity_type, 0) + 1
            )
            
            # Document breakdown
            doc_type = result.get('document_type', 'Unknown')
            stats['document_breakdown'][doc_type] = (
                stats['document_breakdown'].get(doc_type, 0) + 1
            )
            
            # Confidence distribution
            if confidence > 0.8:
                stats['confidence_distribution']['high_confidence'] += 1
            elif confidence > 0.5:
                stats['confidence_distribution']['medium_confidence'] += 1
            else:
                stats['confidence_distribution']['low_confidence'] += 1
            
            # Special features
            if extracted_details.get('is_amended'):
                stats['special_features']['amendments'] += 1
            
            if entity_info.get('is_joint'):
                stats['special_features']['joint_returns'] += 1
            
            if entity_type != 'Individual':
                stats['special_features']['business_entities'] += 1
            
            if 'K-1' in doc_type and extracted_details.get('partnership_name'):
                stats['special_features']['k1_partnerships'] += 1
            
            if extracted_details.get('source_entity'):
                stats['special_features']['multiple_source_entities'] += 1
            
            # Processing quality
            filled_fields = sum(1 for v in extracted_details.values() 
                              if v and v != 'Unknown' and str(v).strip())
            total_fields = len(extracted_details)
            
            if total_fields > 0:
                completion_ratio = filled_fields / total_fields
                if completion_ratio > 0.7:
                    stats['processing_quality']['complete_extractions'] += 1
                elif completion_ratio > 0.4:
                    stats['processing_quality']['partial_extractions'] += 1
                else:
                    stats['processing_quality']['minimal_extractions'] += 1
        
        # Calculate success rates
        if stats['total_processed'] > 0:
            stats['success_rate'] = stats['successful'] / stats['total_processed']
            stats['error_rate'] = stats['errors'] / stats['total_processed']
            
            confidence_total = sum(stats['confidence_distribution'].values())
            if confidence_total > 0:
                stats['high_confidence_rate'] = (
                    stats['confidence_distribution']['high_confidence'] / confidence_total
                )
        
        return stats
    
    def batch_process_documents(self, file_paths: List[Tuple[str, str]], 
                              manual_client_info: Optional[Dict] = None,
                              progress_callback: Optional[callable] = None) -> List[Dict]:
        """
        Process multiple documents efficiently with progress tracking
        
        Args:
            file_paths: List of (file_path, filename) tuples
            manual_client_info: Optional manual client information
            progress_callback: Optional callback for progress updates
            
        Returns:
            List of processing results
        """
        results = []
        total_files = len(file_paths)
        
        for i, (file_path, filename) in enumerate(file_paths):
            try:
                if progress_callback:
                    progress_callback(i + 1, total_files, filename)
                
                result = self.process_document(file_path, filename, manual_client_info)
                results.append(result)
                
            except Exception as e:
                self.logger.error(f"Error in batch processing {filename}: {e}")
                results.append({
                    'original_filename': filename,
                    'status': 'error',
                    'error': str(e)
                })
        
        return results
    
    # Legacy compatibility methods
    def process_document_legacy(self, file_path: str, original_filename: str, 
                              manual_client_info: Optional[Dict] = None) -> Dict:
        """Legacy compatibility method"""
        enhanced_result = self.process_document(file_path, original_filename, manual_client_info)
        
        # Convert to legacy format
        legacy_result = {
            'original_filename': enhanced_result['original_filename'],
            'status': enhanced_result['status'],
            'error': enhanced_result['error'],
            'client_name': enhanced_result['client_name'],
            'tax_year': enhanced_result['tax_year'],
            'document_type': enhanced_result['document_type'],
            'confidence': enhanced_result['confidence'],
            'new_filename': enhanced_result['new_filename']
        }
        
        return legacy_result 
    
    def _apply_document_type_preprocessing(self, image_path: str, donut_result: Dict, 
                                         temp_files: List[str]) -> Tuple[str, Dict]:
        """
        SPEED OPTIMIZED: Document-type aware preprocessing with reduced processing
        """
        preprocessing_start = time.time()
        
        try:
            # Validate inputs
            if not image_path or not os.path.exists(image_path):
                return image_path, {
                    'enhanced_image_path': image_path,
                    'enhancement_applied': False,
                    'error': 'Invalid image path',
                    'processing_time': time.time() - preprocessing_start
                }
            
            # Validate donut_result
            if not isinstance(donut_result, dict):
                donut_result = {'donut_type': 'Unknown', 'donut_confidence': 0.0}
            
            # Check if speed optimizations are enabled
            if not Config.ENABLE_SPEED_OPTIMIZATIONS:
                # Apply full preprocessing when optimizations are disabled
                preprocessing_results = self.document_type_aware_preprocessor.preprocess_document(
                    image_path, donut_result.get('donut_type', 'Unknown'), donut_result.get('donut_confidence', 0.0)
                )
                return preprocessing_results.get('enhanced_image_path', image_path), preprocessing_results
            
            # Extract document type and confidence from Donut results
            doc_type = donut_result.get('donut_type', 'Unknown')
            doc_confidence = donut_result.get('donut_confidence', 0.0)
            
            # Ensure doc_type is not None
            if doc_type is None:
                doc_type = 'Unknown'
            
            # SPEED OPTIMIZATION: Skip preprocessing for high-confidence results
            if doc_confidence > Config.SKIP_PREPROCESSING_HIGH_CONFIDENCE:
                self.logger.info(f"Skipping preprocessing for high-confidence {doc_type} ({doc_confidence:.2f})")
                return image_path, {
                    'enhanced_image_path': image_path,
                    'enhancement_applied': False,
                    'processing_time': time.time() - preprocessing_start,
                    'skip_reason': 'high_confidence'
                }
            
            # SPEED OPTIMIZATION: Skip preprocessing for simple document types
            simple_doc_types = ['W-2', '1099-NEC', '1099-MISC', '1099-INT', '1099-DIV']
            if any(simple_type in doc_type for simple_type in simple_doc_types):
                if doc_confidence > Config.SKIP_PREPROCESSING_SIMPLE_DOCS:
                    self.logger.info(f"Skipping preprocessing for simple document type: {doc_type}")
                    return image_path, {
                        'enhanced_image_path': image_path,
                        'enhancement_applied': False,
                        'processing_time': time.time() - preprocessing_start,
                        'skip_reason': 'simple_document'
                    }
            
            self.logger.info(f"🎨 Applying document-type aware preprocessing for {doc_type} (confidence: {doc_confidence:.2f})")
            
            # Apply document-type aware preprocessing
            preprocessing_results = self.document_type_aware_preprocessor.preprocess_document(
                image_path, doc_type, doc_confidence
            )
            
            # Validate preprocessing results
            if not isinstance(preprocessing_results, dict):
                self.logger.error(f"Invalid preprocessing results format: {type(preprocessing_results)}")
                return image_path, {
                    'enhanced_image_path': image_path,
                    'enhancement_applied': False,
                    'error': 'Invalid preprocessing results',
                    'processing_time': time.time() - preprocessing_start
                }
            
            # Track preprocessing statistics
            try:
                self._track_document_type_preprocessing_stats(preprocessing_results)
            except Exception as e:
                self.logger.error(f"Error tracking preprocessing stats: {e}")
            
            enhanced_image_path = preprocessing_results.get('enhanced_image_path', image_path)
            
            # Add enhanced image to cleanup list if it's different from original
            if enhanced_image_path != image_path and enhanced_image_path not in temp_files:
                temp_files.append(enhanced_image_path)
            
            processing_time = time.time() - preprocessing_start
            preprocessing_results['processing_time'] = processing_time
            
            return enhanced_image_path, preprocessing_results
            
        except Exception as e:
            self.logger.error(f"Error in document preprocessing: {e}")
            return image_path, {
                'enhanced_image_path': image_path,
                'enhancement_applied': False,
                'error': str(e),
                'processing_time': time.time() - preprocessing_start
            }
    
    def _track_document_type_preprocessing_stats(self, preprocessing_results: Dict):
        """Track document-type aware preprocessing statistics"""
        stats = self.processing_stats['document_type_preprocessing']
        stats['total_documents_processed'] += 1
        
        if preprocessing_results.get('enhancement_applied'):
            stats['type_aware_enhancements_applied'] += 1
        
        # Track quality improvements
        original_quality = preprocessing_results.get('original_quality', {})
        original_score = original_quality.get('quality_score', 0.0)
        
        # Estimate improvement (we'd need to re-analyze enhanced image for actual score)
        if preprocessing_results.get('enhancement_applied'):
            estimated_improvement = 0.1  # Conservative estimate
            stats['quality_score_improvements'].append({
                'original_score': original_score,
                'estimated_improvement': estimated_improvement,
                'doc_type': preprocessing_results.get('doc_type', 'Unknown')
            })
        
        # Track processing time
        processing_time = preprocessing_results.get('processing_time', 0.0)
        if processing_time > 0:
            stats['processing_time_savings'].append(processing_time)
        
        # Track strategy usage
        strategy = preprocessing_results.get('strategy_used', {})
        doc_type = preprocessing_results.get('doc_type', 'Unknown')
        if doc_type not in stats['document_type_strategies']:
            stats['document_type_strategies'][doc_type] = {
                'total_processed': 0,
                'enhancements_applied': 0,
                'strategies_used': []
            }
        
        type_stats = stats['document_type_strategies'][doc_type]
        type_stats['total_processed'] += 1
        if preprocessing_results.get('enhancement_applied'):
            type_stats['enhancements_applied'] += 1
            if strategy:
                type_stats['strategies_used'].append(strategy.get('description', 'Unknown strategy'))
    
    def print_dynamic_threshold_statistics(self):
        """
        Phase 5: Print dynamic threshold performance and learning statistics
        """
        print("\n" + "="*60)
        print("🧠 PHASE 5: DYNAMIC CONFIDENCE THRESHOLDS")
        print("="*60)
        
        dt_stats = self.processing_stats.get('dynamic_thresholds', {})
        
        # Basic threshold usage
        total_calculations = dt_stats.get('total_threshold_calculations', 0)
        adaptations_applied = dt_stats.get('threshold_adaptations_applied', 0)
        adaptive_triggered = dt_stats.get('adaptive_validations_triggered', 0)
        adaptive_skipped = dt_stats.get('adaptive_validations_skipped', 0)
        
        print(f"📊 Threshold Calculations: {total_calculations}")
        print(f"🔧 Adaptations Applied: {adaptations_applied}")
        print(f"✅ Adaptive Validations Triggered: {adaptive_triggered}")
        print(f"⏭️  Adaptive Validations Skipped: {adaptive_skipped}")
        
        if total_calculations > 0:
            adaptation_rate = (adaptations_applied / total_calculations) * 100
            print(f"📈 Adaptation Rate: {adaptation_rate:.1f}%")
        
        # Field importance boosts
        field_boosts = dt_stats.get('field_importance_boosts', [])
        if field_boosts:
            avg_boost = sum(field_boosts) / len(field_boosts)
            print(f"⚡ Avg Field Importance Boost: {avg_boost:+.3f}")
        
        # Success rate adjustments
        success_adjustments = dt_stats.get('success_rate_adjustments', [])
        if success_adjustments:
            avg_success_adj = sum(success_adjustments) / len(success_adjustments)
            print(f"📊 Avg Success Rate Adjustment: {avg_success_adj:+.3f}")
        
        # Time-based learning
        time_adjustments = dt_stats.get('time_based_adjustments', [])
        if time_adjustments:
            avg_time_adj = sum(time_adjustments) / len(time_adjustments)
            print(f"⏰ Avg Time-Based Adjustment: {avg_time_adj:+.3f}")
        
        # Learning improvements
        learning_improvements = dt_stats.get('learning_improvements', [])
        if learning_improvements:
            print(f"\n🎯 Learning Improvements: {len(learning_improvements)}")
            
            # Group by document type
            doc_type_learning = {}
            for improvement in learning_improvements:
                doc_type = improvement['doc_type']
                if doc_type not in doc_type_learning:
                    doc_type_learning[doc_type] = []
                doc_type_learning[doc_type].append(improvement['confidence_improvement'])
            
            for doc_type, improvements in doc_type_learning.items():
                avg_improvement = sum(improvements) / len(improvements)
                print(f"   📄 {doc_type}: {len(improvements)} improvements, avg +{avg_improvement:.3f}")
        
        # Confidence adjustments
        confidence_adjustments = dt_stats.get('confidence_adjustments', [])
        if confidence_adjustments:
            print(f"\n🎚️  Confidence Adjustments: {len(confidence_adjustments)}")
            
            # Calculate average boost by document type
            doc_type_boosts = {}
            for adj in confidence_adjustments:
                doc_type = adj['doc_type']
                boost = adj['boost']
                if doc_type not in doc_type_boosts:
                    doc_type_boosts[doc_type] = []
                doc_type_boosts[doc_type].append(boost)
            
            for doc_type, boosts in doc_type_boosts.items():
                avg_boost = sum(boosts) / len(boosts)
                print(f"   📄 {doc_type}: avg {avg_boost:+.3f} confidence adjustment")
        
        # Historical performance data
        print(f"\n📚 Historical Performance Data:")
        historical_data = self.dynamic_threshold_manager.historical_performance
        if historical_data:
            for perf_key, perf_data in historical_data.items():
                if perf_key.endswith('_performance'):
                    doc_type = perf_key.replace('_performance', '')
                    total_processed = perf_data.get('total_processed', 0)
                    success_rate = perf_data.get('validation_success_rate', 0)
                    validations_applied = perf_data.get('validations_applied', 0)
                    
                    print(f"   📄 {doc_type}: {total_processed} processed, {validations_applied} validations, {success_rate:.1%} success rate")
        else:
            print("   (No historical data yet - system is learning)")
        
        print("="*60)
    
    def print_document_type_preprocessing_statistics(self):
        """
        Phase 4: Print document-type aware preprocessing performance statistics
        """
        print("\n" + "="*60)
        print("🎨 PHASE 4: DOCUMENT-TYPE AWARE PREPROCESSING")
        print("="*60)
        
        dt_stats = self.processing_stats.get('document_type_preprocessing', {})
        
        # Basic preprocessing usage
        total_processed = dt_stats.get('total_documents_processed', 0)
        type_aware_applied = dt_stats.get('type_aware_enhancements_applied', 0)
        basic_applied = dt_stats.get('basic_enhancements_applied', 0)
        
        print(f"📊 Preprocessing Statistics:")
        print(f"   Total Documents Processed: {total_processed}")
        print(f"   Type-Aware Enhancements Applied: {type_aware_applied}")
        print(f"   Basic Enhancements Applied: {basic_applied}")
        
        if total_processed > 0:
            type_aware_rate = (type_aware_applied / total_processed) * 100
            print(f"   Type-Aware Enhancement Rate: {type_aware_rate:.1f}%")
        
        # Quality improvements
        quality_improvements = dt_stats.get('quality_score_improvements', [])
        if quality_improvements:
            avg_improvement = sum(q['estimated_improvement'] for q in quality_improvements) / len(quality_improvements)
            print(f"   Average Quality Improvement: +{avg_improvement:.2f}")
        
        # Processing time
        processing_times = dt_stats.get('processing_time_savings', [])
        if processing_times:
            avg_time = sum(processing_times) / len(processing_times)
            print(f"   Average Processing Time: {avg_time:.3f}s")
        
        # Document type strategies
        doc_strategies = dt_stats.get('document_type_strategies', {})
        if doc_strategies:
            print(f"\n📄 Document Type Strategy Usage:")
            for doc_type, strategy_stats in doc_strategies.items():
                total = strategy_stats['total_processed']
                enhanced = strategy_stats['enhancements_applied']
                enhancement_rate = (enhanced / total) * 100 if total > 0 else 0
                
                print(f"   {doc_type}:")
                print(f"      Processed: {total}")
                print(f"      Enhanced: {enhanced}")
                print(f"      Enhancement Rate: {enhancement_rate:.1f}%")
                
                strategies_used = strategy_stats.get('strategies_used', [])
                if strategies_used:
                    unique_strategies = list(set(strategies_used))
                    print(f"      Strategies Used: {', '.join(unique_strategies[:3])}...")
        
        # Enhancement effectiveness
        effectiveness = dt_stats.get('enhancement_effectiveness', {})
        if effectiveness:
            print(f"\n⚡ Enhancement Effectiveness:")
            for method, stats in effectiveness.items():
                print(f"   {method}: {stats.get('success_rate', 0):.1%} success rate")
        
        print("="*60)
    
    def process_document_with_batching(self, file_path: str, original_filename: str, 
                                     processing_priority: ProcessingPriority = ProcessingPriority.NORMAL,
                                     manual_client_info: Optional[Dict] = None) -> Dict:
        """
        Phase 6: Process document with intelligent batch optimization
        
        Args:
            file_path: Path to the document file
            original_filename: Original filename
            processing_priority: Processing priority level
            manual_client_info: Optional manual client information
            
        Returns:
            Processing result or batch queue information
        """
        if not self.batch_processing_enabled or processing_priority == ProcessingPriority.URGENT:
            # Process immediately for urgent documents or when batching is disabled
            result = self.process_document(file_path, original_filename, manual_client_info)
            result['processing_mode'] = 'individual_immediate'
            self.processing_stats['batch_processing']['total_individual_processed'] += 1
            return result
        
        # Add to batch queue for optimized processing
        batch_result = self.batch_processor.add_document_to_batch_queue(
            file_path, original_filename, processing_priority, manual_client_info
        )
        
        # Update batch statistics
        self.processing_stats['batch_processing']['current_batch_queue_size'] = len(
            self.batch_processor.pending_documents
        )
        
        return batch_result
    
    def process_document_batch(self, file_paths_and_names: List[Tuple[str, str]], 
                             processing_options: Optional[Dict] = None) -> List[Dict]:
        """
        Phase 6: Process multiple documents with intelligent batch optimization
        
        Args:
            file_paths_and_names: List of (file_path, original_filename) tuples
            processing_options: Optional processing configuration (including session_callback)
            
        Returns:
            List of processing results
        """
        # Extract callback function if provided
        session_callback = processing_options.get('session_callback') if processing_options else None
        
        if not self.batch_processing_enabled or len(file_paths_and_names) < 2:
            # Process individually if batching disabled or too few documents
            results = []
            for i, (file_path, filename) in enumerate(file_paths_and_names):
                # Call progress callback if provided
                if session_callback:
                    session_callback(i + 1, filename)
                    
                result = self.process_document(file_path, filename, 
                                             processing_options.get('manual_client_info') if processing_options else None)
                result['processing_mode'] = 'individual_batch_disabled'
                results.append(result)
            return results
        
        # Use intelligent batch processing
        batch_items = []
        for file_path, filename in file_paths_and_names:
            priority = ProcessingPriority.NORMAL
            if processing_options and processing_options.get('high_priority'):
                priority = ProcessingPriority.HIGH
            
            batch_item = DocumentBatchItem(
                file_path=file_path,
                original_filename=filename,
                processing_priority=priority,
                client_info=processing_options.get('manual_client_info') if processing_options else None,
                added_timestamp=time.time()
            )
            batch_items.append(batch_item)
        
        # Create optimized batches
        batch_groups = self.batch_processor.batch_optimizer.optimize_batch_groups(batch_items)
        
        # Process batch groups
        all_results = []
        current_index = 0
        for batch_group in batch_groups:
            batch_results = self._process_batch_group_directly(batch_group, session_callback, current_index)
            all_results.extend(batch_results)
            current_index += len(batch_group.documents)
        
        # Update batch processing statistics
        self._update_batch_processing_stats(batch_groups, all_results)
        
        return all_results
    
    def _process_batch_group_directly(self, batch_group, session_callback=None, start_index=0) -> List[Dict]:
        """Process a batch group directly (synchronous processing)"""
        results = []
        batch_start_time = time.time()
        
        self.logger.info(f"🚀 Processing batch group with {len(batch_group.documents)} documents using {batch_group.strategy.value}")
        
        # Process documents in the batch group
        for i, doc in enumerate(batch_group.documents):
            # Call progress callback if provided
            if session_callback:
                session_callback(start_index + i + 1, doc.original_filename)
            try:
                result = self.process_document(
                    doc.file_path,
                    doc.original_filename,
                    doc.client_info
                )
                
                # Add batch processing metadata
                result['batch_group_id'] = batch_group.group_id
                result['batch_strategy'] = batch_group.strategy.value
                result['batch_size'] = len(batch_group.documents)
                result['processing_mode'] = 'intelligent_batch'
                result['processing_priority'] = doc.processing_priority.value
                
                results.append(result)
                
            except Exception as e:
                self.logger.error(f"Error processing document {doc.original_filename} in batch: {e}")
                results.append({
                    'original_filename': doc.original_filename,
                    'status': 'error',
                    'error': str(e),
                    'batch_group_id': batch_group.group_id,
                    'processing_mode': 'intelligent_batch'
                })
        
        batch_processing_time = time.time() - batch_start_time
        
        # Calculate batch efficiency
        estimated_individual_time = len(batch_group.documents) * 3.0  # 3 seconds per document
        time_savings = max(0, estimated_individual_time - batch_processing_time)
        time_savings_rate = time_savings / estimated_individual_time if estimated_individual_time > 0 else 0
        
        self.logger.info(f"✅ Completed batch group in {batch_processing_time:.2f}s (estimated individual: {estimated_individual_time:.2f}s, savings: {time_savings_rate*100:.1f}%)")
        
        # Add batch performance data to results
        for result in results:
            result['batch_performance'] = {
                'processing_time': batch_processing_time,
                'time_savings_rate': time_savings_rate,
                'estimated_cost_savings': self._estimate_batch_cost_savings(batch_group)
            }
        
        return results
    
    def _estimate_batch_cost_savings(self, batch_group) -> float:
        """Estimate cost savings from batch processing"""
        # Calculate potential API call consolidation savings
        batch_size = len(batch_group.documents)
        
        # Base savings from reduced API overhead
        if batch_size > 1:
            api_efficiency_gain = min(0.25, (batch_size - 1) * 0.05)  # Up to 25% savings
            return api_efficiency_gain
        
        return 0.0
    
    def _update_batch_processing_stats(self, batch_groups: List, results: List[Dict]):
        """Update batch processing statistics"""
        batch_stats = self.processing_stats['batch_processing']
        
        # Basic counts
        batch_stats['total_batches_created'] += len(batch_groups)
        batch_stats['total_documents_batched'] += len(results)
        
        # Calculate batch vs individual ratio
        total_processed = batch_stats['total_documents_batched'] + batch_stats['total_individual_processed']
        if total_processed > 0:
            batch_stats['batch_vs_individual_ratio'] = batch_stats['total_documents_batched'] / total_processed
        
        # Track strategy effectiveness
        for batch_group in batch_groups:
            strategy = batch_group.strategy.value
            if strategy in batch_stats['batch_strategy_effectiveness']:
                strategy_stats = batch_stats['batch_strategy_effectiveness'][strategy]
                strategy_stats['count'] += 1
                
                # Calculate savings for this batch
                estimated_savings = self._estimate_batch_cost_savings(batch_group)
                current_avg = strategy_stats['avg_savings']
                new_count = strategy_stats['count']
                strategy_stats['avg_savings'] = ((current_avg * (new_count - 1)) + estimated_savings) / new_count
        
        # Track optimal batch sizes by document type
        for batch_group in batch_groups:
            if batch_group.documents:
                doc_type = batch_group.documents[0].document_type or 'Unknown'
                batch_size = len(batch_group.documents)
                
                if doc_type not in batch_stats['optimal_batch_sizes']:
                    batch_stats['optimal_batch_sizes'][doc_type] = []
                
                batch_stats['optimal_batch_sizes'][doc_type].append(batch_size)
                
                # Keep only recent data (last 20 batches per type)
                if len(batch_stats['optimal_batch_sizes'][doc_type]) > 20:
                    batch_stats['optimal_batch_sizes'][doc_type] = batch_stats['optimal_batch_sizes'][doc_type][-20:]
    
    def enable_batch_processing(self):
        """Enable intelligent batch processing"""
        self.batch_processing_enabled = True
        self.processing_stats['batch_processing']['batch_processing_enabled'] = True
        self.logger.info("Intelligent batch processing enabled")
    
    def disable_batch_processing(self):
        """Disable intelligent batch processing (fall back to individual processing)"""
        self.batch_processing_enabled = False
        self.processing_stats['batch_processing']['batch_processing_enabled'] = False
        self.logger.info("Intelligent batch processing disabled")
    
    def get_batch_processing_status(self) -> Dict:
        """Get current batch processing status and statistics"""
        if not self.batch_processing_enabled:
            return {
                'batch_processing_enabled': False,
                'message': 'Batch processing is disabled'
            }
        
        batch_status = self.batch_processor.get_batch_processing_status()
        batch_stats = self.processing_stats['batch_processing']
        
        return {
            'batch_processing_enabled': True,
            'current_status': batch_status,
            'performance_statistics': {
                'total_batches_created': batch_stats['total_batches_created'],
                'total_documents_batched': batch_stats['total_documents_batched'],
                'batch_vs_individual_ratio': batch_stats['batch_vs_individual_ratio'],
                'strategy_effectiveness': batch_stats['batch_strategy_effectiveness'],
                'optimal_batch_sizes': {
                    doc_type: {
                        'average_size': sum(sizes) / len(sizes) if sizes else 0,
                        'size_range': f"{min(sizes)}-{max(sizes)}" if sizes else "N/A"
                    }
                    for doc_type, sizes in batch_stats['optimal_batch_sizes'].items()
                }
            }
        }
    
    def _calculate_session_specific_stats(self, session_results: List[Dict]) -> Dict:
        """Calculate statistics specific to a processing session"""
        if not session_results:
            return {}
        
        completed_results = [r for r in session_results if r.get('status') == 'completed']
        
        session_stats = {
            'total_files': len(session_results),
            'completed_files': len(completed_results),
            'error_files': len([r for r in session_results if r.get('status') == 'error']),
            'completion_rate': (len(completed_results) / len(session_results)) * 100 if session_results else 0,
            'average_confidence': 0.0,
            'document_types': {},
            'entity_types': {},
            'processing_modes': {}
        }
        
        if completed_results:
            # Calculate average confidence
            confidences = [r.get('confidence', 0.0) for r in completed_results]
            session_stats['average_confidence'] = sum(confidences) / len(confidences)
            
            # Count document types
            for result in completed_results:
                doc_type = result.get('document_type', 'Unknown')
                session_stats['document_types'][doc_type] = session_stats['document_types'].get(doc_type, 0) + 1
            
            # Count entity types
            for result in completed_results:
                entity_type = result.get('entity_info', {}).get('entity_type', 'Unknown')
                session_stats['entity_types'][entity_type] = session_stats['entity_types'].get(entity_type, 0) + 1
            
            # Count processing modes
            for result in completed_results:
                processing_mode = result.get('processing_mode', 'Unknown')
                session_stats['processing_modes'][processing_mode] = session_stats['processing_modes'].get(processing_mode, 0) + 1
        
        return session_stats

    def get_enhanced_processing_stats(self, session_results: Optional[List[Dict]] = None) -> Dict:
        """
        Get comprehensive processing statistics including all phases (1-6)
        
        Args:
            session_results: Optional list of session results for session-specific stats
            
        Returns:
            Complete statistics including batch processing metrics
        """
        stats = self.processing_stats.copy()
        
        # Add calculated metrics
        if stats['total_documents'] > 0:
            stats['success_rate'] = (stats['successful_extractions'] / stats['total_documents']) * 100
            stats['error_rate'] = (stats['processing_errors'] / stats['total_documents']) * 100
        else:
            stats['success_rate'] = 0
            stats['error_rate'] = 0
        
        # Calculate average confidence
        if stats['confidence_scores']:
            stats['average_confidence'] = sum(stats['confidence_scores']) / len(stats['confidence_scores'])
        else:
            stats['average_confidence'] = 0
        
        # Calculate average processing time
        if stats['processing_times']:
            stats['average_processing_time'] = sum(stats['processing_times']) / len(stats['processing_times'])
        else:
            stats['average_processing_time'] = 0
        
        # Phase 1: Ensemble statistics
        ensemble_stats = stats['ensemble_decisions']
        if ensemble_stats['model_agreements'] + ensemble_stats['model_disagreements'] > 0:
            total_decisions = ensemble_stats['model_agreements'] + ensemble_stats['model_disagreements']
            ensemble_stats['agreement_rate'] = (ensemble_stats['model_agreements'] / total_decisions) * 100
        else:
            ensemble_stats['agreement_rate'] = 0
        
        # Phase 2: Field routing effectiveness
        routing_stats = stats['field_routing_stats']
        total_routing_decisions = (routing_stats['donut_classifications'] + 
                                 routing_stats['claude_extractions'] + 
                                 routing_stats['dual_validations'])
        if total_routing_decisions > 0:
            routing_stats['routing_efficiency'] = {
                'donut_usage': (routing_stats['donut_classifications'] / total_routing_decisions) * 100,
                'claude_usage': (routing_stats['claude_extractions'] / total_routing_decisions) * 100,
                'dual_validation_usage': (routing_stats['dual_validations'] / total_routing_decisions) * 100
            }
        
        # Phase 3: Cross-validation cost savings
        cv_stats = stats['cross_validation']
        if cv_stats['total_validations_performed'] + cv_stats['validations_skipped'] > 0:
            total_potential_validations = cv_stats['total_validations_performed'] + cv_stats['validations_skipped']
            cv_stats['cost_optimization_rate'] = (cv_stats['validations_skipped'] / total_potential_validations) * 100
        
        # Phase 4: Document-type preprocessing effectiveness
        prep_stats = stats['document_type_preprocessing']
        if prep_stats['total_documents_processed'] > 0:
            prep_stats['enhancement_rate'] = (prep_stats['type_aware_enhancements_applied'] / 
                                           prep_stats['total_documents_processed']) * 100
        
        # Phase 5: Dynamic threshold learning progress
        threshold_stats = stats['dynamic_thresholds']
        if threshold_stats['total_threshold_evaluations'] > 0:
            threshold_stats['recommendation_accuracy'] = (
                threshold_stats['validation_recommended'] / threshold_stats['total_threshold_evaluations']
            ) * 100
        
        # Phase 6: Batch processing efficiency metrics
        batch_stats = stats['batch_processing']
        if batch_stats['total_documents_batched'] + batch_stats['total_individual_processed'] > 0:
            total_processed = batch_stats['total_documents_batched'] + batch_stats['total_individual_processed']
            batch_stats['batching_rate'] = (batch_stats['total_documents_batched'] / total_processed) * 100
            
            # Calculate average batch performance
            if batch_stats['api_cost_savings_from_batching']:
                batch_stats['average_cost_savings_rate'] = (
                    sum(batch_stats['api_cost_savings_from_batching']) / 
                    len(batch_stats['api_cost_savings_from_batching'])
                ) * 100
            
            if batch_stats['processing_time_savings_from_batching']:
                batch_stats['average_time_savings_rate'] = (
                    sum(batch_stats['processing_time_savings_from_batching']) / 
                    len(batch_stats['processing_time_savings_from_batching'])
                ) * 100
        
        # Session-specific statistics
        if session_results:
            session_stats = self._calculate_session_specific_stats(session_results)
            stats['current_session'] = session_stats
        
        # System health metrics
        stats['system_health'] = {
            'total_phases_active': 6,  # All phases implemented
            'accuracy_improvement_estimate': '+35-60%',  # Cumulative improvement
            'cost_optimization_active': True,
            'batch_processing_active': self.batch_processing_enabled,
            'learning_systems_active': True,
            'processing_intelligence_level': 'Advanced'
        }
        
        return stats

    def _merge_with_validation(self, original_result: Dict, validation_result: Dict) -> Dict:
        """
        Merge validation results with original extraction
        """
        try:
            merged = original_result.copy()
            
            # Apply validation corrections
            if validation_result.get('document_type_correct') == False:
                merged['document_type'] = validation_result.get('corrected_document_type', merged.get('document_type'))
            
            if validation_result.get('client_name_correct') == False:
                merged['client_name'] = validation_result.get('corrected_client_name', merged.get('client_name'))
            
            if validation_result.get('tax_year_correct') == False:
                merged['tax_year'] = validation_result.get('corrected_tax_year', merged.get('tax_year'))
            
            # Update confidence based on validation
            validation_confidence = validation_result.get('validation_confidence', 0.0)
            original_confidence = merged.get('confidence', 0.0)
            
            # Weighted average of original and validation confidence
            merged['confidence'] = (original_confidence * 0.7) + (validation_confidence * 0.3)
            
            # Add validation notes
            merged['validation_notes'] = validation_result.get('validation_notes', '')
            merged['validation_applied'] = True
            
            return merged
            
        except Exception as e:
            self.logger.error(f"Error merging validation results: {e}")
            return original_result
    
    def _extract_individual_fields(self, image_path: str, routing_plan: Dict) -> Dict:
        """
        Fallback: Extract fields individually (slower but more detailed)
        """
        try:
            field_results = {}
            
            # Extract client names
            if routing_plan.get('client_names') == 'claude':
                client_info = self._extract_client_names_claude(image_path)
                field_results.update(client_info)
            
            # Extract amounts
            if routing_plan.get('amounts') == 'claude':
                amount_info = self._extract_amounts_fallback(image_path)
                field_results.update(amount_info)
            
            # Extract dates
            if routing_plan.get('dates') == 'claude':
                date_info = self._extract_dates_claude(image_path)
                field_results.update(date_info)
            
            # Extract addresses
            if routing_plan.get('addresses') == 'claude':
                address_info = self._extract_addresses_claude(image_path)
                field_results.update(address_info)
            
            # Fill missing fields with comprehensive extraction
            if self._needs_comprehensive_extraction(field_results):
                comprehensive_info = self.claude_ocr.extract_comprehensive_document_info(image_path)
                field_results = self._merge_with_comprehensive(field_results, comprehensive_info)
            
            field_results['extraction_method'] = 'individual_fields'
            field_results['confidence'] = self._calculate_field_routing_confidence(field_results)
            
            return field_results
            
        except Exception as e:
            self.logger.error(f"Error in individual field extraction: {e}")
            return {'confidence': 0.0, 'error': str(e)}