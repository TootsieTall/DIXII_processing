import os
import shutil
from pathlib import Path
import uuid
from PIL import Image
import pdf2image
import re
import unicodedata
import logging
from typing import Dict, Optional, List, Tuple
from models.donut_classifier import DonutTaxClassifier
from models.enhanced_claude_ocr import EnhancedClaudeOCR
from utils.entity_recognizer import EntityRecognizer
from utils.filename_generator import FilenameGenerator
from config import Config

class EnhancedTaxDocumentProcessor:
    def __init__(self, donut_model_path: str, claude_api_key: str):
        self.donut_classifier = DonutTaxClassifier(donut_model_path)
        self.claude_ocr = EnhancedClaudeOCR(claude_api_key)
        self.entity_recognizer = EntityRecognizer(Config.PROCESSED_FOLDER)
        self.filename_generator = FilenameGenerator()
        self.processed_folder = Config.PROCESSED_FOLDER
        
        # Setup logging
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger(__name__)
        
        # Processing statistics
        self.processing_stats = {
            'total_documents': 0,
            'successful_extractions': 0,
            'entity_types': {},
            'document_types': {},
            'amendments_detected': 0,
            'joint_returns': 0,
            'processing_errors': 0
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
            'error': None,
            'client_name': None,
            'tax_year': None,
            'document_type': None,
            'confidence': 0.0,
            'new_filename': None,
            'client_folder': None,
            'processed_path': None,
            'entity_info': {},
            'extracted_details': {},
            'processing_notes': []
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
            
            # Step 2: Multi-stage document analysis
            # 2a: Initial classification with Donut
            donut_result = self._classify_with_donut(image_path, original_filename)
            
            # 2b: Comprehensive extraction with Enhanced Claude OCR
            extracted_info = self.claude_ocr.extract_comprehensive_document_info(image_path)
            
            # 2c: Merge and validate results
            merged_info = self._merge_classification_results(donut_result, extracted_info)
            
            # Step 3: Entity recognition and analysis
            if manual_client_info:
                # Override with manual information
                merged_info = self._apply_manual_client_info(merged_info, manual_client_info)
            
            entity_info = self.entity_recognizer.analyze_entity(merged_info)
            
            # Step 4: Generate intelligent filename
            filename_info = self.filename_generator.get_filename_preview(
                merged_info, entity_info, original_filename
            )
            
            # Step 5: Organize and save document
            organization_result = self._organize_document(
                file_path, entity_info, filename_info, merged_info
            )
            
            # Step 6: Update result with all information
            result.update({
                'status': 'completed',
                'client_name': self._get_client_display_name(entity_info),
                'tax_year': merged_info.get('tax_year', 'Unknown'),
                'document_type': merged_info.get('document_type', 'Unknown Document'),
                'confidence': merged_info.get('confidence', 0.0),
                'new_filename': filename_info['filename'],
                'client_folder': entity_info.get('final_folder'),
                'processed_path': organization_result['final_path'],
                'entity_info': entity_info,
                'extracted_details': merged_info,
                'processing_notes': organization_result.get('notes', [])
            })
            
            # Update statistics
            self._update_processing_stats(result)
            
            if result['confidence'] > 0.7:
                self.processing_stats['successful_extractions'] += 1
            
            self.logger.info(f"Successfully processed {original_filename}")
            
        except Exception as e:
            self.logger.error(f"Error processing {original_filename}: {e}")
            result['status'] = 'error'
            result['error'] = str(e)
            self.processing_stats['processing_errors'] += 1
            
        finally:
            # Clean up temporary files
            self._clean_temp_files(temp_files)
        
        return result
    
    def _prepare_image(self, file_path: str, temp_files: List[str]) -> Optional[str]:
        """Prepare image for processing (handle PDF conversion)"""
        try:
            file_ext = Path(file_path).suffix.lower()
            
            if file_ext == '.pdf':
                # Convert PDF to images
                images = pdf2image.convert_from_path(file_path, dpi=200)
                if not images:
                    return None
                
                # Use first page for processing
                temp_path = f"temp_{uuid.uuid4()}.jpg"
                images[0].save(temp_path, 'JPEG', quality=90)
                temp_files.append(temp_path)
                return temp_path
            else:
                # Direct image file
                return file_path
                
        except Exception as e:
            self.logger.error(f"Error preparing image: {e}")
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
        """Merge results from Donut and Claude OCR"""
        merged = claude_result.copy()
        
        # If Claude didn't identify document type well, use Donut result
        claude_doc_type = claude_result.get('document_type', 'Unknown Document')
        donut_doc_type = donut_result.get('donut_type')
        
        if (claude_doc_type == 'Unknown Document' or 
            claude_result.get('confidence', 0) < 0.5) and donut_doc_type:
            merged['document_type'] = donut_doc_type
            merged['confidence'] = max(merged.get('confidence', 0), donut_result.get('donut_confidence', 0))
            merged['classification_source'] = 'donut'
        else:
            merged['classification_source'] = 'claude'
        
        # Add Donut information for reference
        merged['donut_classification'] = donut_result
        
        return merged
    
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
                filename_info['filename'], client_folder_path
            )
            
            # Final destination path
            final_path = os.path.join(client_folder_path, final_filename)
            
            # Copy file to destination
            shutil.copy2(file_path, final_path)
            
            notes = []
            if final_filename != filename_info['filename']:
                notes.append(f"Filename conflict resolved: {filename_info['filename']} → {final_filename}")
            
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