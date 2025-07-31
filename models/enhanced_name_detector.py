import torch
from transformers import (
    LayoutLMForTokenClassification, 
    LayoutLMTokenizer,
    BertForTokenClassification,
    BertTokenizer,
    AutoTokenizer,
    AutoModelForTokenClassification
)
from PIL import Image, ImageDraw, ImageFont
import pytesseract
import numpy as np
import re
import logging
from typing import Dict, List, Tuple, Optional
import os
import json
import pickle
from datetime import datetime

class EnhancedNameDetector:
    """
    Enhanced name detection using multiple specialized models:
    1. LayoutLM for document-specific name detection
    2. BERT NER for general name recognition
    3. Rule-based fallback for tax document patterns
    """
    
    def __init__(self, models_dir: str = "models"):
        self.models_dir = models_dir
        self.logger = logging.getLogger(__name__)
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        
        # Initialize models
        self.layoutlm_model = None
        self.layoutlm_tokenizer = None
        self.bert_ner_model = None
        self.bert_ner_tokenizer = None
        
        # Learning system
        self.learning_data_file = os.path.join(models_dir, "name_learning_data.json")
        self.location_patterns_file = os.path.join(models_dir, "location_patterns.json")
        self.learning_data = self._load_learning_data()
        self.location_patterns = self._load_location_patterns()
        
        # Load models
        self._load_models()
        
        # Tax document name patterns
        self.tax_name_patterns = {
            'k1_recipient': [
                r'partner.*name.*?([A-Z][a-z]+ [A-Z][a-z]+)',
                r'recipient.*name.*?([A-Z][a-z]+ [A-Z][a-z]+)',
                r'shareholder.*name.*?([A-Z][a-z]+ [A-Z][a-z]+)',
                r'partner.*?([A-Z][a-z]+ [A-Z][a-z]+)',
                r'recipient.*?([A-Z][a-z]+ [A-Z][a-z]+)'
            ],
            'w2_employee': [
                r'employee.*name.*?([A-Z][a-z]+ [A-Z][a-z]+)',
                r'name.*employee.*?([A-Z][a-z]+ [A-Z][a-z]+)',
                r'employee.*?([A-Z][a-z]+ [A-Z][a-z]+)'
            ],
            '1099_recipient': [
                r'recipient.*name.*?([A-Z][a-z]+ [A-Z][a-z]+)',
                r'payee.*name.*?([A-Z][a-z]+ [A-Z][a-z]+)',
                r'recipient.*?([A-Z][a-z]+ [A-Z][a-z]+)',
                r'payee.*?([A-Z][a-z]+ [A-Z][a-z]+)'
            ],
            '1040_taxpayer': [
                r'taxpayer.*name.*?([A-Z][a-z]+ [A-Z][a-z]+)',
                r'primary.*name.*?([A-Z][a-z]+ [A-Z][a-z]+)',
                r'taxpayer.*?([A-Z][a-z]+ [A-Z][a-z]+)',
                r'primary.*?([A-Z][a-z]+ [A-Z][a-z]+)'
            ],
            'trust_entity': [
                r'([A-Z][a-z]+ [A-Z][a-z]+)\s+(?:Trust|TRUST)',
                r'(?:Trust|TRUST)\s+of\s+([A-Z][a-z]+ [A-Z][a-z]+)',
                r'([A-Z][a-z]+ [A-Z][a-z]+)\s+(?:Family|FAMILY)\s+(?:Trust|TRUST)',
                r'([A-Z][a-z]+ [A-Z][a-z]+)\s+(?:Living|LIVING)\s+(?:Trust|TRUST)',
                r'([A-Z][a-z]+ [A-Z][a-z]+)\s+(?:Revocable|REVOCABLE)\s+(?:Trust|TRUST)',
                r'([A-Z][a-z]+ [A-Z][a-z]+)\s+(?:Irrevocable|IRREVOCABLE)\s+(?:Trust|TRUST)'
            ],
            'llc_entity': [
                r'([A-Z][a-z]+ [A-Z][a-z]+)\s+(?:LLC|L\.L\.C\.)',
                r'([A-Z][a-z]+ [A-Z][a-z]+)\s+(?:Limited|LIMITED)\s+(?:Liability|LIABILITY)\s+(?:Company|COMPANY)',
                r'([A-Z][a-z]+ [A-Z][a-z]+)\s+(?:Corp|CORP|Corporation|CORPORATION)',
                r'([A-Z][a-z]+ [A-Z][a-z]+)\s+(?:Inc|INC|Incorporated|INCORPORATED)',
                r'([A-Z][a-z]+ [A-Z][a-z]+)\s+(?:Co|CO|Company|COMPANY)',
                r'([A-Z][a-z]+ [A-Z][a-z]+)\s+(?:Partnership|PARTNERSHIP)',
                r'([A-Z][a-z]+ [A-Z][a-z]+)\s+(?:LP|L\.P\.|Limited Partnership|LIMITED PARTNERSHIP)'
            ],
            'partnership_entity': [
                r'([A-Z][a-z]+ [A-Z][a-z]+)\s+&\s+([A-Z][a-z]+ [A-Z][a-z]+)',
                r'([A-Z][a-z]+ [A-Z][a-z]+)\s+AND\s+([A-Z][a-z]+ [A-Z][a-z]+)',
                r'([A-Z][a-z]+ [A-Z][a-z]+)\s+([A-Z][a-z]+ [A-Z][a-z]+)\s+(?:Partnership|PARTNERSHIP)',
                r'([A-Z][a-z]+ [A-Z][a-z]+)\s+([A-Z][a-z]+ [A-Z][a-z]+)\s+(?:LLC|L\.L\.C\.)'
            ],
            'estate_entity': [
                r'([A-Z][a-z]+ [A-Z][a-z]+)\s+(?:Estate|ESTATE)',
                r'(?:ESTATE)\s+of\s+([A-Z][a-z]+ [A-Z][a-z]+)',
                r'([A-Z][a-z]+ [A-Z][a-z]+)\s+(?:ESTATE)\s+(?:of|OF)\s+([A-Z][a-z]+ [A-Z][a-z]+)'
            ],
            'general_entity': [
                # General person name patterns
                r'\b([A-Z][a-z]+\s+[A-Z][a-z]+)\b',
                r'\b([A-Z][a-z]+\s+[A-Z][a-z]+\s+[A-Z][a-z]+)\b',
                # Names with titles
                r'\b(Mr\.|Ms\.|Mrs\.|Dr\.)\s+([A-Z][a-z]+\s+[A-Z][a-z]+)\b',
                # Business names with person names
                r'\b([A-Z][a-z]+\s+[A-Z][a-z]+)\s+(?:LLC|Corp|Inc|Co|Trust|Estate)\b'
            ]
        }
    
    def _load_models(self):
        """Load the specialized models for name detection"""
        try:
            # Load LayoutLM for document-specific name detection
            # Use a more appropriate model or handle the base model properly
            self.layoutlm_tokenizer = LayoutLMTokenizer.from_pretrained("microsoft/layoutlm-base-uncased")
            self.layoutlm_model = LayoutLMForTokenClassification.from_pretrained(
                "microsoft/layoutlm-base-uncased",
                num_labels=2  # Binary classification: name vs not-name
            )
            self.layoutlm_model.to(self.device)
            self.layoutlm_model.eval()
            self.logger.info("LayoutLM model loaded successfully")
            
        except Exception as e:
            self.logger.warning(f"Could not load LayoutLM model: {e}")
            self.logger.info("LayoutLM will be disabled - using pattern-based detection only")
            self.layoutlm_model = None
            self.layoutlm_tokenizer = None
        
        try:
            # Load BERT NER for general name recognition
            # Use a more appropriate model for person name detection
            self.bert_ner_tokenizer = BertTokenizer.from_pretrained("dbmdz/bert-large-cased-finetuned-conll03-english")
            self.bert_ner_model = BertForTokenClassification.from_pretrained("dbmdz/bert-large-cased-finetuned-conll03-english")
            self.bert_ner_model.to(self.device)
            self.bert_ner_model.eval()
            self.logger.info("BERT NER model loaded successfully")
            
        except Exception as e:
            self.logger.warning(f"Could not load BERT NER model: {e}")
            self.logger.info("BERT NER will be disabled - using pattern-based detection only")
            self.bert_ner_model = None
            self.bert_ner_tokenizer = None
        
        # Log which models are available
        available_models = []
        if self.layoutlm_model:
            available_models.append("LayoutLM")
        if self.bert_ner_model:
            available_models.append("BERT NER")
        if not available_models:
            self.logger.warning("No ML models loaded - will rely on pattern-based detection only")
        else:
            self.logger.info(f"Available models: {', '.join(available_models)}")
    
    def detect_names_in_document(self, image_path: str, doc_type: str = None) -> Dict:
        """
        Comprehensive name detection using multiple approaches
        
        Args:
            image_path: Path to the document image
            doc_type: Document type (optional, for targeted detection)
            
        Returns:
            Dictionary with detected names and confidence scores
        """
        results = {
            'layoutlm_names': [],
            'bert_ner_names': [],
            'pattern_names': [],
            'location_names': [],
            'combined_names': [],
            'confidence': 0.0,
            'detection_methods': []
        }
        
        try:
            # Validate input
            if not image_path or not os.path.exists(image_path):
                self.logger.error(f"Invalid image path: {image_path}")
                return results
            
            # Method 1: LayoutLM for document-specific detection
            if self.layoutlm_model and self.layoutlm_tokenizer:
                try:
                    layoutlm_results = self._detect_names_layoutlm(image_path)
                    results['layoutlm_names'] = layoutlm_results
                    results['detection_methods'].append('layoutlm')
                    self.logger.info(f"LayoutLM detected {len(layoutlm_results)} names")
                except Exception as e:
                    self.logger.error(f"LayoutLM detection failed: {e}")
                    results['layoutlm_names'] = []
            
            # Method 2: BERT NER for general name recognition
            if self.bert_ner_model and self.bert_ner_tokenizer:
                try:
                    bert_results = self._detect_names_bert_ner(image_path)
                    results['bert_ner_names'] = bert_results
                    results['detection_methods'].append('bert_ner')
                    self.logger.info(f"BERT NER detected {len(bert_results)} names")
                except Exception as e:
                    self.logger.error(f"BERT NER detection failed: {e}")
                    results['bert_ner_names'] = []
            
            # Method 3: Pattern-based detection for tax documents
            if doc_type:
                try:
                    pattern_results = self._detect_names_patterns(image_path, doc_type)
                    results['pattern_names'] = pattern_results
                    results['detection_methods'].append('patterns')
                    self.logger.info(f"Pattern detection found {len(pattern_results)} names")
                except Exception as e:
                    self.logger.error(f"Pattern detection failed: {e}")
                    results['pattern_names'] = []
            
            # Method 4: Location-based detection using learned patterns
            if doc_type:
                try:
                    location_results = self._detect_names_by_location(image_path, doc_type)
                    results['location_names'] = location_results
                    results['detection_methods'].append('location_pattern')
                    self.logger.info(f"Location-based detection found {len(location_results)} names")
                except Exception as e:
                    self.logger.error(f"Location-based detection failed: {e}")
                    results['location_names'] = []
            
            # Combine and rank results
            results['combined_names'] = self._combine_name_results(results)
            results['confidence'] = self._calculate_confidence(results)
            
            return results
            
        except Exception as e:
            self.logger.error(f"Error in name detection: {e}")
            return results
    
    def _detect_names_layoutlm(self, image_path: str) -> List[Dict]:
        """Detect names using LayoutLM model"""
        try:
            # Load and preprocess image (handle PDFs)
            if image_path.lower().endswith('.pdf'):
                import pdf2image
                images = pdf2image.convert_from_path(image_path, dpi=300)
                if not images:
                    return []
                image = images[0].convert("RGB")
            else:
                image = Image.open(image_path).convert("RGB")
            width, height = image.size
            
            # Run OCR to get text and bounding boxes
            ocr_results = self._run_ocr_with_boxes(image)
            if not ocr_results:
                self.logger.warning("No OCR results obtained for LayoutLM processing")
                return []
            
            # Validate OCR results structure
            words = []
            boxes = []
            for item in ocr_results:
                if isinstance(item, dict) and 'text' in item and 'bbox' in item:
                    if isinstance(item['bbox'], list) and len(item['bbox']) == 4:
                        words.append(item['text'])
                        boxes.append(item['bbox'])
                    else:
                        self.logger.warning(f"Invalid bbox format: {item['bbox']}")
                else:
                    self.logger.warning(f"Invalid OCR result item: {item}")
            
            if not words or not boxes:
                self.logger.warning("No valid words or boxes found for LayoutLM processing")
                return []
            
            # Normalize boxes to 1000x1000
            normalized_boxes = []
            for i, box in enumerate(boxes):
                try:
                    # Debug: log original box values
                    self.logger.debug(f"Original box {i}: {box}, width: {width}, height: {height}")
                    
                    # Ensure values are within 0-1000 range
                    x0 = max(0, min(1000, int(1000 * box[0] / width)))
                    y0 = max(0, min(1000, int(1000 * box[1] / height)))
                    x1 = max(0, min(1000, int(1000 * box[2] / width)))
                    y1 = max(0, min(1000, int(1000 * box[3] / height)))
                    
                    # Ensure x1 > x0 and y1 > y0
                    x1 = max(x1, x0 + 1)
                    y1 = max(y1, y0 + 1)
                    
                    normalized_box = [x0, y0, x1, y1]
                    normalized_boxes.append(normalized_box)
                    
                    # Debug: log normalized box values
                    self.logger.debug(f"Normalized box {i}: {normalized_box}")
                    
                except (TypeError, ValueError, ZeroDivisionError) as e:
                    self.logger.warning(f"Error normalizing box {box}: {e}")
                    continue
            
            if not normalized_boxes:
                self.logger.warning("No valid normalized boxes for LayoutLM processing")
                return []
            
            # Debug: log all normalized boxes
            self.logger.debug(f"All normalized boxes: {normalized_boxes[:5]}...")  # Show first 5
            
            # Tokenize with proper padding and truncation
            # LayoutLM tokenizer expects boxes as a list of lists, not as a keyword argument
            encoding = self.layoutlm_tokenizer(
                words,
                return_tensors="pt",
                truncation=True,
                padding=True,
                max_length=512
            )
            
            # Add boxes manually since LayoutLM tokenizer doesn't accept boxes parameter
            # We need to create the bbox tensor manually
            bbox_tensor = torch.tensor(normalized_boxes).to(self.device)
            
            # Ensure bbox tensor has the correct shape for LayoutLM
            # LayoutLM expects bbox to have shape (batch_size, sequence_length, 4)
            if len(bbox_tensor.shape) == 2:
                bbox_tensor = bbox_tensor.unsqueeze(0)  # Add batch dimension
            
            # Move to device
            input_ids = encoding["input_ids"].to(self.device)
            attention_mask = encoding["attention_mask"].to(self.device)
            
            # Ensure bbox tensor matches input_ids length
            # If bbox tensor is shorter than input_ids, pad with zeros
            if bbox_tensor.shape[1] < input_ids.shape[1]:
                padding_length = input_ids.shape[1] - bbox_tensor.shape[1]
                padding = torch.zeros((1, padding_length, 4), device=self.device)
                bbox_tensor = torch.cat([bbox_tensor, padding], dim=1)
            elif bbox_tensor.shape[1] > input_ids.shape[1]:
                # Truncate bbox tensor to match input_ids
                bbox_tensor = bbox_tensor[:, :input_ids.shape[1], :]
            
            # Get predictions
            with torch.no_grad():
                outputs = self.layoutlm_model(
                    input_ids=input_ids,
                    attention_mask=attention_mask,
                    bbox=bbox_tensor
                )
            
            # Process predictions
            predictions = outputs.logits.argmax(-1).squeeze().cpu().numpy()
            
            # Handle different prediction shapes
            if len(predictions.shape) == 0:
                # Single scalar prediction
                predictions = [predictions.item()]
            elif len(predictions.shape) == 1:
                # 1D array
                predictions = predictions.tolist()
            else:
                # Multi-dimensional array - take the first dimension
                predictions = predictions[0].tolist()
            
            # Extract names based on predictions (binary classification: 0 = not name, 1 = name)
            names = []
            current_name = []
            
            for i, (word, pred) in enumerate(zip(words, predictions)):
                if pred == 1:  # Name label
                    current_name.append(word)
                elif current_name:
                    # End of name sequence
                    full_name = ' '.join(current_name).strip()
                    if len(full_name) > 2:  # Filter out very short names
                        names.append({
                            'name': full_name,
                            'confidence': 0.8,
                            'method': 'layoutlm',
                            'bbox': ocr_results[i-1]['bbox'] if i > 0 and i-1 < len(ocr_results) else None
                        })
                    current_name = []
            
            # Handle case where name is at the end
            if current_name:
                full_name = ' '.join(current_name).strip()
                if len(full_name) > 2:
                    names.append({
                        'name': full_name,
                        'confidence': 0.8,
                        'method': 'layoutlm',
                        'bbox': ocr_results[-1]['bbox'] if ocr_results else None
                    })
            
            return names
            
        except Exception as e:
            self.logger.error(f"Error in LayoutLM name detection: {e}")
            return []
    
    def _detect_names_bert_ner(self, image_path: str) -> List[Dict]:
        """Detect names using BERT NER model"""
        try:
            # Extract text from image (handle PDFs)
            if image_path.lower().endswith('.pdf'):
                import pdf2image
                images = pdf2image.convert_from_path(image_path, dpi=300)
                if not images:
                    return []
                image = images[0]
            else:
                image = Image.open(image_path)
            
            text = pytesseract.image_to_string(image)
            if not text.strip():
                self.logger.warning("No text extracted from image for BERT NER")
                return []
            
            # Tokenize text
            tokens = self.bert_ner_tokenizer(
                text,
                return_tensors="pt",
                truncation=True,
                max_length=512
            )
            
            # Move to device
            input_ids = tokens["input_ids"].to(self.device)
            attention_mask = tokens["attention_mask"].to(self.device)
            
            # Get predictions
            with torch.no_grad():
                outputs = self.bert_ner_model(
                    input_ids=input_ids,
                    attention_mask=attention_mask
                )
            
            # Process predictions
            predictions = outputs.logits.argmax(-1).squeeze().cpu().numpy()
            tokens_list = self.bert_ner_tokenizer.convert_ids_to_tokens(input_ids[0])
            
            # Define label mapping for CONLL-03 format
            # 0: O (Outside), 1: B-PER (Beginning of Person), 2: I-PER (Inside of Person)
            # 3: B-ORG, 4: I-ORG, 5: B-LOC, 6: I-LOC, 7: B-MISC, 8: I-MISC
            PERSON_LABELS = [1, 2]  # B-PER and I-PER
            
            # Extract names (PERSON entities)
            names = []
            current_name = []
            
            for i, (token, pred) in enumerate(zip(tokens_list, predictions)):
                if pred in PERSON_LABELS:  # PERSON label (B-PER or I-PER)
                    # Clean up token (remove ## for subword tokens)
                    clean_token = token.replace('##', '')
                    if clean_token:  # Only add non-empty tokens
                        current_name.append(clean_token)
                elif current_name:
                    # End of name sequence
                    full_name = ' '.join(current_name).strip()
                    if len(full_name) > 2:  # Filter out very short names
                        names.append({
                            'name': full_name,
                            'confidence': 0.85,
                            'method': 'bert_ner',
                            'bbox': None
                        })
                    current_name = []
            
            # Handle case where name is at the end
            if current_name:
                full_name = ' '.join(current_name).strip()
                if len(full_name) > 2:
                    names.append({
                        'name': full_name,
                        'confidence': 0.85,
                        'method': 'bert_ner',
                        'bbox': None
                    })
            
            # Debug logging
            if not names:
                self.logger.debug(f"BERT NER: No names detected in text: '{text[:100]}...'")
                self.logger.debug(f"BERT NER: Predictions sample: {predictions[:10]}")
                self.logger.debug(f"BERT NER: Tokens sample: {tokens_list[:10]}")
            
            return names
            
        except Exception as e:
            self.logger.error(f"Error in BERT NER name detection: {e}")
            return []
    
    def _detect_names_patterns(self, image_path: str, doc_type: str) -> List[Dict]:
        """ENHANCED: Detect names using pattern matching for tax documents with better filtering"""
        try:
            # Extract text from image (handle PDFs)
            if image_path.lower().endswith('.pdf'):
                import pdf2image
                images = pdf2image.convert_from_path(image_path, dpi=300)
                if not images:
                    return []
                image = images[0]
            else:
                image = Image.open(image_path)
            
            text = pytesseract.image_to_string(image)
            if not text.strip():
                return []
            
            names = []
            entity_types = []
            
            # ENHANCED: More specific patterns for actual person names
            person_name_patterns = [
                # Individual names with proper capitalization
                r'([A-Z][a-z]+ [A-Z][a-z]+)',
                r'([A-Z][a-z]+ [A-Z][a-z]+ [A-Z][a-z]+)',  # First Middle Last
                # Names with titles
                r'(Mr\.|Mrs\.|Ms\.|Dr\.) ([A-Z][a-z]+ [A-Z][a-z]+)',
                # Names in specific contexts
                r'(Partner|Recipient|Employee|Taxpayer|Borrower): ([A-Z][a-z]+ [A-Z][a-z]+)',
                r'([A-Z][a-z]+ [A-Z][a-z]+) (Partner|Recipient|Employee|Taxpayer|Borrower)',
                # Trust beneficiary patterns
                r'([A-Z][a-z]+ [A-Z][a-z]+) Trust',
                r'Trust of ([A-Z][a-z]+ [A-Z][a-z]+)',
                # Partnership patterns
                r'([A-Z][a-z]+ [A-Z][a-z]+) & ([A-Z][a-z]+ [A-Z][a-z]+)',
                r'([A-Z][a-z]+ [A-Z][a-z]+) AND ([A-Z][a-z]+ [A-Z][a-z]+)',
            ]
            
            # ENHANCED: Filter out common non-name terms
            exclude_terms = {
                'federal', 'state', 'total', 'units', 'value', 'amount', 'tax', 'trust', 'assets',
                'liquid', 'estate', 'other', 'held', 'goodman', 'llc', 'applicable', 'discounts',
                'net', 'taxable', 'related', 'generation', 'skipping', 'payable', 'available',
                'estimated', 'capital', 'gains', 'monetization', 'beneficiaries', 'transfer',
                'basis', 'personal', 'article', 'exempt', 'nia', 'uw', 'appt', 'farber'
            }
            
            for pattern in person_name_patterns:
                matches = re.finditer(pattern, text, re.IGNORECASE)
                for match in matches:
                    if len(match.groups()) == 1:
                        name = match.group(1).strip()
                    else:
                        # For patterns with multiple groups (like partnerships)
                        name_parts = [match.group(i).strip() for i in range(1, len(match.groups()) + 1)]
                        name = ' '.join(name_parts)
                    
                    # ENHANCED: Filter out non-name terms
                    if self._is_valid_person_name(name, exclude_terms):
                        entity_type = self._detect_entity_type_from_pattern(pattern, name, text)
                        names.append({
                            'name': name,
                            'confidence': 0.8,  # Higher confidence for filtered names
                            'method': 'patterns',
                            'entity_type': entity_type,
                            'bbox': None
                        })
                        
                        if entity_type and entity_type not in entity_types:
                            entity_types.append(entity_type)
            
            # Add entity type information to results
            if entity_types:
                self.logger.info(f"Detected entity types: {entity_types}")
            
            return names
            
        except Exception as e:
            self.logger.error(f"Error in pattern-based name detection: {e}")
            return []
    
    def _is_valid_person_name(self, name: str, exclude_terms: set) -> bool:
        """ENHANCED: Validate if a detected name is actually a person name"""
        if not name or len(name.strip()) < 3:
            return False
        
        name_lower = name.lower()
        name_parts = name.split()
        
        # Must have at least first and last name
        if len(name_parts) < 2:
            return False
        
        # Check if any part is in exclude terms
        for part in name_parts:
            if part.lower() in exclude_terms:
                return False
        
        # Check for proper capitalization (first letter of each part should be uppercase)
        for part in name_parts:
            if not part or not part[0].isupper():
                return False
        
        # Check for reasonable name length (not too long)
        if len(name) > 50:
            return False
        
        # Check for common name patterns
        # Should not be all uppercase (likely a header)
        if name.isupper():
            return False
        
        # Should not contain numbers (likely not a person name)
        if any(char.isdigit() for char in name):
            return False
        
        # Should not be common financial terms
        financial_terms = {'total', 'value', 'amount', 'units', 'federal', 'state', 'tax'}
        if any(term in name_lower for term in financial_terms):
            return False
        
        return True
    
    def _detect_entity_type_from_pattern(self, pattern: str, name: str, text: str) -> str:
        """Detect entity type based on the pattern and context"""
        pattern_lower = pattern.lower()
        text_lower = text.lower()
        name_lower = name.lower()
        
        # Check for trust patterns
        if 'trust' in pattern_lower or 'trust' in text_lower:
            return 'Trust'
        
        # Check for LLC patterns
        if 'llc' in pattern_lower or 'limited liability' in pattern_lower:
            return 'LLC'
        
        # Check for corporation patterns
        if 'corp' in pattern_lower or 'corporation' in pattern_lower:
            return 'Corporation'
        
        # Check for partnership patterns
        if 'partnership' in pattern_lower or '&' in pattern or 'and' in pattern_lower:
            return 'Partnership'
        
        # Check for estate patterns
        if 'estate' in pattern_lower:
            return 'Estate'
        
        # Check for joint return patterns
        if '&' in pattern or 'and' in pattern_lower:
            return 'Joint Return'
        
        # Default to individual
        return 'Individual'
    
    def _run_ocr_with_boxes(self, image: Image.Image) -> List[Dict]:
        """Run OCR and return text with bounding boxes"""
        try:
            # Use pytesseract to get OCR data with bounding boxes
            ocr_data = pytesseract.image_to_data(image, output_type=pytesseract.Output.DICT)
            
            results = []
            for i in range(len(ocr_data['text'])):
                text = ocr_data['text'][i].strip()
                if text and int(ocr_data['conf'][i]) > 30:  # Confidence threshold
                    results.append({
                        'text': text,
                        'bbox': [
                            ocr_data['left'][i],
                            ocr_data['top'][i],
                            ocr_data['left'][i] + ocr_data['width'][i],
                            ocr_data['top'][i] + ocr_data['height'][i]
                        ],
                        'confidence': int(ocr_data['conf'][i]) / 100.0
                    })
            
            return results
            
        except Exception as e:
            self.logger.error(f"Error in OCR with boxes: {e}")
            return []
    
    def _combine_name_results(self, results: Dict) -> List[Dict]:
        """Combine and deduplicate name results from different methods"""
        all_names = []
        
        # Collect all names
        for method_names in [results['layoutlm_names'], results['bert_ner_names'], results['pattern_names'], results['location_names']]:
            all_names.extend(method_names)
        
        # Deduplicate and rank
        unique_names = {}
        for name_info in all_names:
            name = name_info['name'].lower().strip()
            if name not in unique_names:
                unique_names[name] = name_info
            else:
                # If we have multiple detections, use the highest confidence
                if name_info['confidence'] > unique_names[name]['confidence']:
                    unique_names[name] = name_info
        
        # Sort by confidence
        combined = list(unique_names.values())
        combined.sort(key=lambda x: x['confidence'], reverse=True)
        
        return combined
    
    def _calculate_confidence(self, results: Dict) -> float:
        """Calculate overall confidence based on detection methods and results"""
        if not results['combined_names']:
            return 0.0
        
        # Base confidence on number of methods used and quality of results
        method_count = len(results['detection_methods'])
        name_count = len(results['combined_names'])
        
        # Higher confidence if multiple methods agree
        base_confidence = min(0.9, 0.3 + (method_count * 0.2))
        
        # Boost confidence if we found multiple names
        if name_count > 1:
            base_confidence += 0.1
        
        # Boost confidence if we have high-confidence individual detections
        avg_confidence = sum(n['confidence'] for n in results['combined_names']) / len(results['combined_names'])
        base_confidence = (base_confidence + avg_confidence) / 2
        
        return min(1.0, base_confidence)
    
    def get_primary_client_name(self, results: Dict) -> Optional[str]:
        """ENHANCED: Extract the most likely primary client name from detection results"""
        if not results.get('combined_names'):
            self.logger.warning("No combined names found in results")
            return None
        
        # Log all detected names for debugging
        self.logger.info(f"All detected names: {[n['name'] for n in results['combined_names']]}")
        
        # ENHANCED: Filter out non-person names
        person_names = []
        for name_info in results['combined_names']:
            name = name_info['name'].strip()
            if self._is_likely_person_name(name):
                person_names.append(name_info)
        
        if not person_names:
            self.logger.warning("No valid person names found after filtering")
            return None
        
        # Enhanced selection logic for person names
        best_name = None
        best_score = 0.0
        
        for name_info in person_names:
            name = name_info['name'].strip()
            confidence = name_info['confidence']
            
            # Calculate a score based on multiple factors
            score = confidence
            
            # Boost score for names that look like real person names
            name_parts = name.split()
            if len(name_parts) >= 2:
                # Boost for full names (first + last)
                score += 0.2
                
                # Boost for names with proper capitalization
                if name_parts[0][0].isupper() and name_parts[1][0].isupper():
                    score += 0.1
            
            # Boost for names detected by multiple methods
            detection_methods = name_info.get('detection_methods', [])
            if len(detection_methods) > 1:
                score += 0.15
            
            # Boost for names with higher confidence
            if confidence > 0.8:
                score += 0.1
            
            # Update best name if this one has a higher score
            if score > best_score:
                best_score = score
                best_name = name
        
        if best_name:
            self.logger.info(f"Selected primary name: {best_name} (score: {best_score:.2f})")
            return best_name
        else:
            self.logger.warning("No suitable primary name found")
            return None
    
    def _is_likely_person_name(self, name: str) -> bool:
        """ENHANCED: Check if a name is likely to be a real person name"""
        if not name or len(name.strip()) < 3:
            return False
        
        name_parts = name.split()
        
        # Must have at least first and last name
        if len(name_parts) < 2:
            return False
        
        # Check for proper capitalization
        for part in name_parts:
            if not part or not part[0].isupper():
                return False
        
        # Check for reasonable name length
        if len(name) > 50:
            return False
        
        # Should not be all uppercase (likely a header)
        if name.isupper():
            return False
        
        # Should not contain numbers
        if any(char.isdigit() for char in name):
            return False
        
        # Should not be common financial/legal terms
        exclude_terms = {
            'federal', 'state', 'total', 'units', 'value', 'amount', 'tax', 'trust', 'assets',
            'liquid', 'estate', 'other', 'held', 'goodman', 'llc', 'applicable', 'discounts',
            'net', 'taxable', 'related', 'generation', 'skipping', 'payable', 'available',
            'estimated', 'capital', 'gains', 'monetization', 'beneficiaries', 'transfer',
            'basis', 'personal', 'article', 'exempt', 'nia', 'uw', 'appt', 'farber'
        }
        
        name_lower = name.lower()
        for term in exclude_terms:
            if term in name_lower:
                return False
        
        return True
    
    def get_all_detected_names(self, results: Dict) -> List[str]:
        """Get all detected names as a list"""
        return [name_info['name'] for name_info in results['combined_names']] 

    def learn_from_manual_input(self, image_path: str, manual_name: str, doc_type: str = None, 
                               bbox_location: List[int] = None, confidence: float = 1.0):
        """
        Learn from manual client input to improve future detection
        
        Args:
            image_path: Path to the document image
            manual_name: Name manually entered by user
            doc_type: Document type (optional)
            bbox_location: Bounding box where name was found (optional)
            confidence: Confidence level of manual input (default 1.0)
        """
        try:
            # Extract OCR results for learning
            image = Image.open(image_path).convert("RGB")
            ocr_results = self._run_ocr_with_boxes(image)
            
            # Create learning entry
            learning_entry = {
                'timestamp': datetime.now().isoformat(),
                'image_path': image_path,
                'manual_name': manual_name,
                'doc_type': doc_type or 'Unknown',
                'bbox_location': bbox_location,
                'confidence': confidence,
                'ocr_results': ocr_results,
                'image_size': image.size
            }
            
            # Add to learning data
            self.learning_data['manual_inputs'].append(learning_entry)
            
            # Update form type patterns
            if doc_type:
                if doc_type not in self.learning_data['form_types']:
                    self.learning_data['form_types'][doc_type] = []
                self.learning_data['form_types'][doc_type].append({
                    'name': manual_name,
                    'bbox': bbox_location,
                    'timestamp': datetime.now().isoformat()
                })
            
            # Update location patterns
            if bbox_location and doc_type:
                self._update_location_patterns(doc_type, manual_name, bbox_location, image.size)
            
            # Save learning data
            self._save_learning_data()
            self._save_location_patterns()
            
            self.logger.info(f"Learned from manual input: {manual_name} on {doc_type or 'Unknown'} form")
            
        except Exception as e:
            self.logger.error(f"Error learning from manual input: {e}")
    
    def _update_location_patterns(self, doc_type: str, name: str, bbox: List[int], image_size: Tuple[int, int]):
        """Update location-based patterns for specific form types"""
        try:
            # Normalize bbox coordinates
            width, height = image_size
            normalized_bbox = [
                bbox[0] / width,
                bbox[1] / height,
                bbox[2] / width,
                bbox[3] / height
            ]
            
            if doc_type not in self.location_patterns['form_types']:
                self.location_patterns['form_types'][doc_type] = {
                    'name_locations': [],
                    'confidence_threshold': 0.7
                }
            
            # Add location pattern
            self.location_patterns['form_types'][doc_type]['name_locations'].append({
                'name': name,
                'bbox': normalized_bbox,
                'timestamp': datetime.now().isoformat()
            })
            
            # Keep only recent patterns (last 50)
            if len(self.location_patterns['form_types'][doc_type]['name_locations']) > 50:
                self.location_patterns['form_types'][doc_type]['name_locations'] = \
                    self.location_patterns['form_types'][doc_type]['name_locations'][-50:]
                    
        except Exception as e:
            self.logger.error(f"Error updating location patterns: {e}")
    
    def _detect_names_by_location(self, image_path: str, doc_type: str) -> List[Dict]:
        """Detect names based on learned location patterns"""
        try:
            if doc_type not in self.location_patterns['form_types']:
                return []
            
            image = Image.open(image_path).convert("RGB")
            width, height = image.size
            ocr_results = self._run_ocr_with_boxes(image)
            
            detected_names = []
            patterns = self.location_patterns['form_types'][doc_type]['name_locations']
            
            for pattern in patterns:
                pattern_bbox = pattern['bbox']
                # Convert normalized coordinates back to pixel coordinates
                target_bbox = [
                    int(pattern_bbox[0] * width),
                    int(pattern_bbox[1] * height),
                    int(pattern_bbox[2] * width),
                    int(pattern_bbox[3] * height)
                ]
                
                # Find OCR results that overlap with the target location
                for ocr_item in ocr_results:
                    if 'bbox' in ocr_item and ocr_item['bbox']:
                        ocr_bbox = ocr_item['bbox']
                        if self._bboxes_overlap(ocr_bbox, target_bbox, threshold=0.3):
                            detected_names.append({
                                'name': ocr_item['text'],
                                'confidence': 0.8,
                                'method': 'location_pattern',
                                'bbox': ocr_item['bbox'],
                                'learned_from': pattern['name']
                            })
            
            return detected_names
            
        except Exception as e:
            self.logger.error(f"Error in location-based detection: {e}")
            return []
    
    def _bboxes_overlap(self, bbox1: List[int], bbox2: List[int], threshold: float = 0.3) -> bool:
        """Check if two bounding boxes overlap significantly"""
        try:
            # Calculate intersection
            x1 = max(bbox1[0], bbox2[0])
            y1 = max(bbox1[1], bbox2[1])
            x2 = min(bbox1[2], bbox2[2])
            y2 = min(bbox1[3], bbox2[3])
            
            if x2 <= x1 or y2 <= y1:
                return False
            
            intersection = (x2 - x1) * (y2 - y1)
            area1 = (bbox1[2] - bbox1[0]) * (bbox1[3] - bbox1[1])
            area2 = (bbox2[2] - bbox2[0]) * (bbox2[3] - bbox2[1])
            
            # Calculate overlap ratio
            overlap_ratio = intersection / min(area1, area2)
            return overlap_ratio >= threshold
            
        except Exception as e:
            self.logger.error(f"Error calculating bbox overlap: {e}")
            return False 

    def _load_learning_data(self) -> Dict:
        """Load learning data from file"""
        try:
            if os.path.exists(self.learning_data_file):
                with open(self.learning_data_file, 'r') as f:
                    return json.load(f)
        except Exception as e:
            self.logger.warning(f"Could not load learning data: {e}")
        return {
            'manual_inputs': [],
            'form_types': {},
            'confidence_improvements': [],
            'last_updated': None
        }
    
    def _save_learning_data(self):
        """Save learning data to file"""
        try:
            os.makedirs(os.path.dirname(self.learning_data_file), exist_ok=True)
            with open(self.learning_data_file, 'w') as f:
                json.dump(self.learning_data, f, indent=2)
        except Exception as e:
            self.logger.error(f"Could not save learning data: {e}")
    
    def _load_location_patterns(self) -> Dict:
        """Load location-based patterns from file"""
        try:
            if os.path.exists(self.location_patterns_file):
                with open(self.location_patterns_file, 'r') as f:
                    return json.load(f)
        except Exception as e:
            self.logger.warning(f"Could not load location patterns: {e}")
        return {
            'form_types': {},
            'name_locations': {},
            'confidence_thresholds': {}
        }
    
    def _save_location_patterns(self):
        """Save location patterns to file"""
        try:
            os.makedirs(os.path.dirname(self.location_patterns_file), exist_ok=True)
            with open(self.location_patterns_file, 'w') as f:
                json.dump(self.location_patterns, f, indent=2)
        except Exception as e:
            self.logger.error(f"Could not save location patterns: {e}") 