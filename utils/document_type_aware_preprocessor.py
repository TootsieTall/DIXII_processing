#!/usr/bin/env python3
"""
Phase 4: Document-Type Aware Preprocessing
Applies specialized image enhancement based on document type predictions
"""

import os
import cv2
import numpy as np
from PIL import Image, ImageEnhance, ImageFilter, ImageOps
import logging
from typing import Dict, Tuple, Optional, List
import time
import json

class DocumentTypeAwarePreprocessor:
    """
    Phase 4: Document-Type Aware Preprocessing
    Applies specialized image enhancements based on document type predictions
    """
    
    def __init__(self, stats_file: str = "preprocessing_stats.json"):
        self.stats_file = stats_file
        self.load_preprocessing_stats()
        
        # Setup logging
        self.logger = logging.getLogger(__name__)
        
        # Document-type specific preprocessing strategies
        self.preprocessing_strategies = {
            'W-2': {
                'description': 'Structured tax form with wage boxes',
                'methods': ['high_contrast_enhancement', 'wage_box_focus', 'text_field_sharpening'],
                'priority_areas': ['wage_amounts', 'tax_withheld', 'employer_info'],
                'enhancement_strength': 1.3,
                'noise_reduction': 'moderate',
                'contrast_boost': 1.4
            },
            '1099-NEC': {
                'description': 'Income reporting with small text fields',
                'methods': ['text_sharpening', 'small_field_enhancement', 'amount_box_focus'],
                'priority_areas': ['income_amounts', 'payer_info', 'recipient_info'],
                'enhancement_strength': 1.4,
                'noise_reduction': 'aggressive',
                'contrast_boost': 1.5
            },
            '1099-MISC': {
                'description': 'Miscellaneous income form',
                'methods': ['text_sharpening', 'small_field_enhancement', 'amount_box_focus'],
                'priority_areas': ['income_amounts', 'payer_info', 'recipient_info'],
                'enhancement_strength': 1.4,
                'noise_reduction': 'aggressive',
                'contrast_boost': 1.5
            },
            'Form 1040': {
                'description': 'Complex tax return with tables',
                'methods': ['edge_detection_enhancement', 'table_structure_focus', 'line_enhancement'],
                'priority_areas': ['income_lines', 'deduction_tables', 'tax_calculation'],
                'enhancement_strength': 1.2,
                'noise_reduction': 'light',
                'contrast_boost': 1.3
            },
            'Schedule C': {
                'description': 'Business income and expense form',
                'methods': ['table_structure_focus', 'line_enhancement', 'business_field_focus'],
                'priority_areas': ['income_lines', 'expense_categories', 'net_profit'],
                'enhancement_strength': 1.2,
                'noise_reduction': 'moderate',
                'contrast_boost': 1.3
            },
            'Receipt': {
                'description': 'Variable quality receipts',
                'methods': ['noise_reduction', 'rotation_correction', 'contrast_enhancement'],
                'priority_areas': ['amount', 'merchant_name', 'date'],
                'enhancement_strength': 1.6,
                'noise_reduction': 'aggressive',
                'contrast_boost': 1.7
            },
            'Invoice': {
                'description': 'Business invoices',
                'methods': ['table_enhancement', 'header_focus', 'amount_enhancement'],
                'priority_areas': ['invoice_number', 'amounts', 'line_items'],
                'enhancement_strength': 1.3,
                'noise_reduction': 'moderate',
                'contrast_boost': 1.4
            },
            'Bank Statement': {
                'description': 'Structured bank statements',
                'methods': ['table_structure_focus', 'transaction_line_enhancement', 'header_preservation'],
                'priority_areas': ['transaction_amounts', 'dates', 'descriptions'],
                'enhancement_strength': 1.2,
                'noise_reduction': 'light',
                'contrast_boost': 1.3
            },
            'Default': {
                'description': 'General purpose preprocessing',
                'methods': ['general_enhancement', 'basic_noise_reduction', 'standard_contrast'],
                'priority_areas': ['text_areas', 'numbers', 'key_fields'],
                'enhancement_strength': 1.2,
                'noise_reduction': 'moderate',
                'contrast_boost': 1.3
            }
        }
        
        # Quality assessment thresholds
        self.quality_thresholds = {
            'brightness': {'low': 50, 'high': 200},
            'contrast': {'low': 20, 'high': 80},
            'sharpness': {'low': 0.3, 'high': 0.8},
            'noise_level': {'low': 0.1, 'high': 0.4}
        }
    
    def load_preprocessing_stats(self):
        """Load preprocessing performance statistics"""
        try:
            if os.path.exists(self.stats_file):
                with open(self.stats_file, 'r') as f:
                    data = json.load(f)
                    self.preprocessing_stats = data.get('stats', {})
            else:
                self.preprocessing_stats = {}
        except Exception as e:
            print(f"Error loading preprocessing stats: {e}")
            self.preprocessing_stats = {}
    
    def save_preprocessing_stats(self):
        """Save preprocessing performance statistics"""
        try:
            data = {
                'stats': self.preprocessing_stats,
                'last_updated': time.time()
            }
            with open(self.stats_file, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            print(f"Error saving preprocessing stats: {e}")
    
    def analyze_image_quality(self, image_path: str) -> Dict:
        """Analyze image quality to determine preprocessing needs"""
        try:
            # Load image
            img = cv2.imread(image_path, cv2.IMREAD_GRAYSCALE)
            if img is None:
                return {'quality': 'unknown', 'needs_enhancement': True}
            
            # Calculate quality metrics
            brightness = np.mean(img)
            contrast = np.std(img)
            
            # Sharpness using Laplacian variance
            laplacian = cv2.Laplacian(img, cv2.CV_64F)
            sharpness = laplacian.var()
            
            # Noise estimation using local standard deviation
            kernel = np.ones((5,5), np.float32)/25
            img_smooth = cv2.filter2D(img, -1, kernel)
            noise_level = np.mean(np.abs(img - img_smooth))
            
            # Normalize sharpness and noise
            sharpness_normalized = min(sharpness / 1000, 1.0)
            noise_normalized = min(noise_level / 50, 1.0)
            
            quality_metrics = {
                'brightness': brightness,
                'contrast': contrast,
                'sharpness': sharpness_normalized,
                'noise_level': noise_normalized
            }
            
            # Determine overall quality
            quality_score = self._calculate_quality_score(quality_metrics)
            
            return {
                'quality_score': quality_score,
                'quality_level': self._get_quality_level(quality_score),
                'metrics': quality_metrics,
                'needs_enhancement': quality_score < 0.6,
                'enhancement_priority': self._get_enhancement_priority(quality_metrics)
            }
            
        except Exception as e:
            self.logger.error(f"Error analyzing image quality: {e}")
            return {'quality': 'unknown', 'needs_enhancement': True}
    
    def _calculate_quality_score(self, metrics: Dict) -> float:
        """Calculate overall quality score from metrics"""
        # Weight different factors
        brightness_weight = 0.2
        contrast_weight = 0.3
        sharpness_weight = 0.3
        noise_weight = 0.2
        
        # Normalize brightness (optimal around 120-140)
        brightness_score = 1.0 - abs(metrics['brightness'] - 130) / 130
        brightness_score = max(0, min(1, brightness_score))
        
        # Normalize contrast (higher is generally better, up to a point)
        contrast_score = min(metrics['contrast'] / 60, 1.0)
        
        # Sharpness score (already normalized)
        sharpness_score = metrics['sharpness']
        
        # Noise score (lower noise is better)
        noise_score = 1.0 - metrics['noise_level']
        
        overall_score = (
            brightness_score * brightness_weight +
            contrast_score * contrast_weight +
            sharpness_score * sharpness_weight +
            noise_score * noise_weight
        )
        
        return overall_score
    
    def _get_quality_level(self, score: float) -> str:
        """Convert quality score to level"""
        if score >= 0.8:
            return 'excellent'
        elif score >= 0.6:
            return 'good'
        elif score >= 0.4:
            return 'fair'
        else:
            return 'poor'
    
    def _get_enhancement_priority(self, metrics: Dict) -> List[str]:
        """Determine which enhancements should be prioritized"""
        priorities = []
        
        if metrics['brightness'] < 80 or metrics['brightness'] > 180:
            priorities.append('brightness_correction')
        
        if metrics['contrast'] < 30:
            priorities.append('contrast_enhancement')
        
        if metrics['sharpness'] < 0.4:
            priorities.append('sharpening')
        
        if metrics['noise_level'] > 0.3:
            priorities.append('noise_reduction')
        
        return priorities
    
    def preprocess_document(self, image_path: str, doc_type: str, 
                          doc_confidence: float = 0.0) -> Dict:
        """Preprocess document based on type and quality analysis"""
        preprocessing_start = time.time()
        
        try:
            # Validate inputs
            if not image_path or not os.path.exists(image_path):
                return {
                    'enhanced_image_path': image_path,
                    'enhancement_applied': False,
                    'error': 'Invalid image path',
                    'processing_time': time.time() - preprocessing_start
                }
            
            # Ensure doc_type is not None
            if doc_type is None:
                doc_type = 'Unknown'
            
            # Analyze image quality
            quality_analysis = self.analyze_image_quality(image_path)
            
            # Get preprocessing strategy
            strategy = self._get_preprocessing_strategy(doc_type, doc_confidence, quality_analysis)
            
            # Check if preprocessing should be applied
            if not strategy.get('should_preprocess', True):
                return {
                    'enhanced_image_path': image_path,
                    'enhancement_applied': False,
                    'processing_time': time.time() - preprocessing_start,
                    'skip_reason': 'strategy_skip',
                    'original_quality': quality_analysis,
                    'strategy_used': strategy,
                    'doc_type': doc_type,
                    'doc_confidence': doc_confidence
                }
            
            # Apply preprocessing
            enhanced_image_path = self._apply_preprocessing(image_path, strategy)
            enhancement_applied = enhanced_image_path != image_path
            
            processing_time = time.time() - preprocessing_start
            
            results = {
                'enhanced_image_path': enhanced_image_path,
                'enhancement_applied': enhancement_applied,
                'original_quality': quality_analysis,
                'strategy_used': strategy,
                'processing_time': processing_time,
                'doc_type': doc_type,
                'doc_confidence': doc_confidence
            }
            
            # Update statistics
            self._update_preprocessing_stats(results)
            
            return results
            
        except Exception as e:
            self.logger.error(f"Error in document preprocessing: {e}")
            return {
                'enhanced_image_path': image_path,
                'enhancement_applied': False,
                'error': str(e),
                'processing_time': time.time() - preprocessing_start
            }
    
    def _get_preprocessing_strategy(self, doc_type: str, doc_confidence: float, 
                                  quality_analysis: Dict) -> Dict:
        """Determine preprocessing strategy based on document type and quality"""
        # Normalize document type
        normalized_type = self._normalize_doc_type(doc_type)
        
        # Get base strategy
        if normalized_type in self.preprocessing_strategies:
            base_strategy = self.preprocessing_strategies[normalized_type].copy()
        else:
            base_strategy = self.preprocessing_strategies['Default'].copy()
        
        # Adjust strategy based on confidence
        if doc_confidence < 0.5:
            # Low confidence - use more conservative approach
            base_strategy['enhancement_strength'] *= 0.8
            base_strategy['methods'] = ['general_enhancement', 'basic_noise_reduction']
        elif doc_confidence > 0.8:
            # High confidence - can use aggressive document-specific enhancements
            base_strategy['enhancement_strength'] *= 1.1
        
        # Adjust strategy based on quality
        quality_score = quality_analysis.get('quality_score', 0.5)
        if quality_score < 0.4:
            # Poor quality - more aggressive enhancement
            base_strategy['enhancement_strength'] *= 1.3
            base_strategy['noise_reduction'] = 'aggressive'
        elif quality_score > 0.8:
            # Good quality - lighter enhancement
            base_strategy['enhancement_strength'] *= 0.8
            base_strategy['noise_reduction'] = 'light'
        
        # Determine if preprocessing should be applied
        should_preprocess = (
            quality_analysis.get('needs_enhancement', True) or
            quality_score < 0.6 or
            doc_confidence > 0.7  # High confidence in doc type allows specialized enhancement
        )
        
        base_strategy.update({
            'should_preprocess': should_preprocess,
            'quality_driven_adjustments': quality_analysis.get('enhancement_priority', []),
            'confidence_adjustment': doc_confidence,
            'final_enhancement_strength': base_strategy['enhancement_strength']
        })
        
        return base_strategy
    
    def _normalize_doc_type(self, doc_type: str) -> str:
        """Normalize document type for strategy lookup"""
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
            'SCHEDULE C': 'Schedule C',
            'BANKSTATEMENT': 'Bank Statement',
            'BANK STATEMENT': 'Bank Statement'
        }
        
        normalized = type_mappings.get(doc_type, doc_type)
        
        # Check if normalized type exists in strategies
        if normalized in self.preprocessing_strategies:
            return normalized
        else:
            return 'Default'
    
    def _apply_preprocessing(self, image_path: str, strategy: Dict) -> str:
        """Apply the preprocessing strategy to the image"""
        try:
            # Check if any enhancement is actually needed
            methods = strategy.get('methods', [])
            quality_driven = strategy.get('quality_driven_adjustments', [])
            
            # If no enhancement methods specified, return original
            if not methods and not quality_driven:
                self.logger.info(f"No enhancement needed for {image_path}")
                return image_path
            
            # Load image
            pil_image = Image.open(image_path)
            if pil_image.mode != 'RGB':
                pil_image = pil_image.convert('RGB')
            
            # Apply document-specific enhancements
            enhanced_image = self._apply_document_specific_enhancements(pil_image, strategy)
            
            # Apply quality-driven enhancements
            if strategy.get('quality_driven_adjustments'):
                enhanced_image = self._apply_quality_enhancements(enhanced_image, strategy)
            
            # Only save enhanced image if actual changes were made
            if enhanced_image is not pil_image:
                enhanced_path = self._generate_enhanced_filename(image_path)
                enhanced_image.save(enhanced_path, 'JPEG', quality=95)
                return enhanced_path
            else:
                # No changes made, return original
                self.logger.info(f"No enhancement applied, using original file")
                return image_path
            
        except Exception as e:
            self.logger.error(f"Error applying preprocessing: {e}")
            return image_path
    
    def _apply_document_specific_enhancements(self, image: Image.Image, strategy: Dict) -> Image.Image:
        """Apply document-type specific enhancements"""
        enhanced = image.copy()
        methods = strategy.get('methods', [])
        strength = strategy.get('final_enhancement_strength', 1.2)
        
        for method in methods:
            if method == 'high_contrast_enhancement':
                enhanced = self._enhance_contrast(enhanced, strength * 1.2)
            elif method == 'wage_box_focus':
                enhanced = self._enhance_structured_areas(enhanced, 'wage_boxes')
            elif method == 'text_field_sharpening':
                enhanced = self._sharpen_text_areas(enhanced, strength)
            elif method == 'text_sharpening':
                enhanced = self._apply_text_sharpening(enhanced, strength * 1.1)
            elif method == 'small_field_enhancement':
                enhanced = self._enhance_small_text(enhanced, strength * 1.3)
            elif method == 'amount_box_focus':
                enhanced = self._enhance_amount_areas(enhanced)
            elif method == 'edge_detection_enhancement':
                enhanced = self._enhance_edges_and_lines(enhanced)
            elif method == 'table_structure_focus':
                enhanced = self._enhance_table_structures(enhanced)
            elif method == 'line_enhancement':
                enhanced = self._enhance_form_lines(enhanced)
            elif method == 'noise_reduction':
                enhanced = self._reduce_noise(enhanced, strategy.get('noise_reduction', 'moderate'))
            elif method == 'rotation_correction':
                enhanced = self._correct_rotation(enhanced)
            elif method == 'contrast_enhancement':
                enhanced = self._enhance_contrast(enhanced, strength)
            elif method == 'general_enhancement':
                enhanced = self._apply_general_enhancement(enhanced, strength)
            elif method == 'basic_noise_reduction':
                enhanced = self._reduce_noise(enhanced, 'light')
        
        return enhanced
    
    def _apply_quality_enhancements(self, image: Image.Image, strategy: Dict) -> Image.Image:
        """Apply quality-driven enhancements"""
        enhanced = image
        priorities = strategy.get('quality_driven_adjustments', [])
        
        for priority in priorities:
            if priority == 'brightness_correction':
                enhanced = self._correct_brightness(enhanced)
            elif priority == 'contrast_enhancement':
                enhanced = self._enhance_contrast(enhanced, 1.4)
            elif priority == 'sharpening':
                enhanced = self._apply_sharpening(enhanced)
            elif priority == 'noise_reduction':
                enhanced = self._reduce_noise(enhanced, 'aggressive')
        
        return enhanced
    
    # Specific enhancement methods
    def _enhance_contrast(self, image: Image.Image, factor: float) -> Image.Image:
        """Enhance image contrast"""
        enhancer = ImageEnhance.Contrast(image)
        return enhancer.enhance(factor)
    
    def _sharpen_text_areas(self, image: Image.Image, strength: float) -> Image.Image:
        """Sharpen text areas for better OCR"""
        # Apply unsharp mask
        blurred = image.filter(ImageFilter.GaussianBlur(1))
        sharpened = ImageEnhance.Sharpness(image).enhance(strength)
        return sharpened
    
    def _enhance_small_text(self, image: Image.Image, strength: float) -> Image.Image:
        """Enhance small text areas like amounts and codes"""
        # Increase contrast and sharpness for small text
        contrast_enhanced = ImageEnhance.Contrast(image).enhance(strength)
        sharpness_enhanced = ImageEnhance.Sharpness(contrast_enhanced).enhance(strength * 0.8)
        return sharpness_enhanced
    
    def _enhance_structured_areas(self, image: Image.Image, area_type: str) -> Image.Image:
        """Enhance structured areas like wage boxes"""
        # Apply moderate contrast enhancement
        enhanced = ImageEnhance.Contrast(image).enhance(1.3)
        # Add slight sharpening
        enhanced = ImageEnhance.Sharpness(enhanced).enhance(1.2)
        return enhanced
    
    def _enhance_amount_areas(self, image: Image.Image) -> Image.Image:
        """Specifically enhance areas containing monetary amounts"""
        # High contrast for number recognition
        contrast_enhanced = ImageEnhance.Contrast(image).enhance(1.5)
        # Moderate sharpening
        sharpened = ImageEnhance.Sharpness(contrast_enhanced).enhance(1.3)
        return sharpened
    
    def _enhance_edges_and_lines(self, image: Image.Image) -> Image.Image:
        """Enhance edges and lines for form structure detection"""
        # Convert to numpy for OpenCV processing
        cv_image = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)
        
        # Apply edge enhancement
        kernel = np.array([[-1,-1,-1], [-1,9,-1], [-1,-1,-1]])
        enhanced = cv2.filter2D(cv_image, -1, kernel)
        
        # Convert back to PIL
        enhanced_rgb = cv2.cvtColor(enhanced, cv2.COLOR_BGR2RGB)
        return Image.fromarray(enhanced_rgb)
    
    def _enhance_table_structures(self, image: Image.Image) -> Image.Image:
        """Enhance table structures and grid lines"""
        # Moderate contrast boost for table lines
        enhanced = ImageEnhance.Contrast(image).enhance(1.2)
        # Light sharpening to define lines
        enhanced = ImageEnhance.Sharpness(enhanced).enhance(1.1)
        return enhanced
    
    def _enhance_form_lines(self, image: Image.Image) -> Image.Image:
        """Enhance form lines and field boundaries"""
        # Apply edge-preserving enhancement
        enhanced = ImageEnhance.Contrast(image).enhance(1.25)
        enhanced = ImageEnhance.Sharpness(enhanced).enhance(1.15)
        return enhanced
    
    def _reduce_noise(self, image: Image.Image, level: str) -> Image.Image:
        """Reduce image noise based on level"""
        if level == 'light':
            return image.filter(ImageFilter.MedianFilter(size=3))
        elif level == 'moderate':
            smoothed = image.filter(ImageFilter.MedianFilter(size=3))
            return smoothed.filter(ImageFilter.GaussianBlur(0.5))
        elif level == 'aggressive':
            smoothed = image.filter(ImageFilter.MedianFilter(size=5))
            return smoothed.filter(ImageFilter.GaussianBlur(1.0))
        else:
            return image
    
    def _correct_rotation(self, image: Image.Image) -> Image.Image:
        """Attempt to correct document rotation"""
        # Simple implementation - could be enhanced with more sophisticated detection
        try:
            # Convert to grayscale for analysis
            gray = image.convert('L')
            cv_image = cv2.cvtColor(np.array(gray), cv2.COLOR_RGB2BGR)
            
            # Detect lines using HoughLines
            edges = cv2.Canny(cv_image, 50, 150, apertureSize=3)
            lines = cv2.HoughLines(edges, 1, np.pi/180, threshold=200)
            
            if lines is not None and len(lines) > 0:
                # Calculate average angle
                angles = []
                for rho, theta in lines[:10]:  # Use first 10 lines
                    angle = theta * 180 / np.pi
                    if angle > 45:
                        angle = angle - 90
                    angles.append(angle)
                
                if angles:
                    avg_angle = np.mean(angles)
                    if abs(avg_angle) > 1:  # Only rotate if significant skew
                        return image.rotate(-avg_angle, expand=True, fillcolor='white')
            
            return image
        except:
            return image
    
    def _correct_brightness(self, image: Image.Image) -> Image.Image:
        """Correct image brightness"""
        enhancer = ImageEnhance.Brightness(image)
        return enhancer.enhance(1.2)
    
    def _apply_sharpening(self, image: Image.Image) -> Image.Image:
        """Apply general sharpening"""
        return image.filter(ImageFilter.SHARPEN)
    
    def _apply_text_sharpening(self, image: Image.Image, strength: float) -> Image.Image:
        """Apply text-specific sharpening"""
        enhancer = ImageEnhance.Sharpness(image)
        return enhancer.enhance(strength)
    
    def _apply_general_enhancement(self, image: Image.Image, strength: float) -> Image.Image:
        """Apply general purpose enhancement"""
        # Balanced enhancement
        contrast_enhanced = ImageEnhance.Contrast(image).enhance(strength)
        sharpened = ImageEnhance.Sharpness(contrast_enhanced).enhance(strength * 0.8)
        return sharpened
    
    def _generate_enhanced_filename(self, original_path: str) -> str:
        """Generate filename for enhanced image"""
        path_parts = os.path.splitext(original_path)
        return f"{path_parts[0]}_enhanced{path_parts[1]}"
    
    def _update_preprocessing_stats(self, results: Dict):
        """Update preprocessing statistics"""
        doc_type = results.get('doc_type', 'Unknown')
        
        if doc_type not in self.preprocessing_stats:
            self.preprocessing_stats[doc_type] = {
                'total_processed': 0,
                'enhancements_applied': 0,
                'average_processing_time': 0.0,
                'quality_improvements': [],
                'strategy_usage': {}
            }
        
        stats = self.preprocessing_stats[doc_type]
        stats['total_processed'] += 1
        
        if results.get('enhancement_applied'):
            stats['enhancements_applied'] += 1
        
        # Update average processing time
        processing_time = results.get('processing_time', 0.0)
        total_time = stats['average_processing_time'] * (stats['total_processed'] - 1) + processing_time
        stats['average_processing_time'] = total_time / stats['total_processed']
        
        # Track strategy usage
        strategy = results.get('strategy_used', {})
        strategy_name = f"{doc_type}_strategy"
        if strategy_name not in stats['strategy_usage']:
            stats['strategy_usage'][strategy_name] = 0
        stats['strategy_usage'][strategy_name] += 1
        
        # Auto-save periodically
        if stats['total_processed'] % 10 == 0:
            self.save_preprocessing_stats()
    
    def get_preprocessing_statistics(self) -> Dict:
        """Get comprehensive preprocessing statistics"""
        total_processed = sum(stats['total_processed'] for stats in self.preprocessing_stats.values())
        total_enhanced = sum(stats['enhancements_applied'] for stats in self.preprocessing_stats.values())
        
        if total_processed == 0:
            return {'message': 'No preprocessing statistics available yet'}
        
        overall_stats = {
            'total_documents_processed': total_processed,
            'total_enhancements_applied': total_enhanced,
            'enhancement_rate': (total_enhanced / total_processed) * 100,
            'document_type_breakdown': {}
        }
        
        for doc_type, stats in self.preprocessing_stats.items():
            overall_stats['document_type_breakdown'][doc_type] = {
                'processed': stats['total_processed'],
                'enhanced': stats['enhancements_applied'],
                'enhancement_rate': (stats['enhancements_applied'] / stats['total_processed']) * 100,
                'avg_processing_time': stats['average_processing_time']
            }
        
        return overall_stats
    
    def print_preprocessing_statistics(self):
        """Print detailed preprocessing statistics"""
        print("\n" + "="*60)
        print("📸 PHASE 4: DOCUMENT-TYPE AWARE PREPROCESSING")
        print("="*60)
        
        stats = self.get_preprocessing_statistics()
        
        if 'message' in stats:
            print(stats['message'])
            return
        
        print(f"📊 Overall Statistics:")
        print(f"   Total Documents Processed: {stats['total_documents_processed']}")
        print(f"   Total Enhancements Applied: {stats['total_enhancements_applied']}")
        print(f"   Enhancement Rate: {stats['enhancement_rate']:.1f}%")
        
        print(f"\n📄 Document Type Breakdown:")
        for doc_type, breakdown in stats['document_type_breakdown'].items():
            print(f"   {doc_type}:")
            print(f"      Processed: {breakdown['processed']}")
            print(f"      Enhanced: {breakdown['enhanced']}")
            print(f"      Enhancement Rate: {breakdown['enhancement_rate']:.1f}%")
            print(f"      Avg Processing Time: {breakdown['avg_processing_time']:.3f}s")
        
        print("="*60) 