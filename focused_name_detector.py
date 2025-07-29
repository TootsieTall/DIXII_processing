#!/usr/bin/env python3
"""
Focused name detection for tax documents
"""

import os
import sys
import logging
import re
import pytesseract
import pdf2image
from PIL import Image
from transformers import BertForTokenClassification, BertTokenizer
import torch

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class FocusedNameDetector:
    """Focused name detector for tax documents"""
    
    def __init__(self):
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.bert_ner_model = None
        self.bert_ner_tokenizer = None
        self._load_bert_ner()
        
        # Focused name patterns for tax documents
        self.name_patterns = [
            # Simple person names (2-3 words, capitalized)
            r'\b([A-Z][a-z]+\s+[A-Z][a-z]+)\b',
            r'\b([A-Z][a-z]+\s+[A-Z][a-z]+\s+[A-Z][a-z]+)\b',
            
            # Names with titles
            r'\b(Mr\.|Ms\.|Mrs\.|Dr\.)\s+([A-Z][a-z]+\s+[A-Z][a-z]+)\b',
            
            # Trust/estate patterns
            r'\b([A-Z][a-z]+\s+[A-Z][a-z]+)\s+(?:Trust|Estate)\b',
            r'\b(?:Trust|Estate)\s+of\s+([A-Z][a-z]+\s+[A-Z][a-z]+)\b',
            
            # Business names with person names
            r'\b([A-Z][a-z]+\s+[A-Z][a-z]+)\s+(?:LLC|Corp|Inc|Co)\b',
        ]
    
    def _load_bert_ner(self):
        """Load BERT NER model"""
        try:
            self.bert_ner_tokenizer = BertTokenizer.from_pretrained("dbmdz/bert-large-cased-finetuned-conll03-english")
            self.bert_ner_model = BertForTokenClassification.from_pretrained("dbmdz/bert-large-cased-finetuned-conll03-english")
            self.bert_ner_model.to(self.device)
            self.bert_ner_model.eval()
            logger.info("BERT NER model loaded successfully")
        except Exception as e:
            logger.warning(f"Could not load BERT NER model: {e}")
            self.bert_ner_model = None
            self.bert_ner_tokenizer = None
    
    def detect_names(self, file_path: str):
        """Detect names in document"""
        results = {
            'bert_ner_names': [],
            'pattern_names': [],
            'filtered_names': [],
            'confidence': 0.0
        }
        
        try:
            # Extract text
            text = self._extract_text(file_path)
            if not text.strip():
                return results
            
            print(f"\nExtracted text (first 300 chars):")
            print(text[:300])
            print("..." if len(text) > 300 else "")
            
            # BERT NER detection
            if self.bert_ner_model and self.bert_ner_tokenizer:
                bert_names = self._detect_names_bert_ner(text)
                results['bert_ner_names'] = bert_names
                print(f"\nBERT NER found: {bert_names}")
            
            # Pattern detection
            pattern_names = self._detect_names_patterns(text)
            results['pattern_names'] = pattern_names
            print(f"\nPattern matching found: {pattern_names}")
            
            # Filter and combine results
            all_names = bert_names + pattern_names
            filtered_names = self._filter_names(all_names)
            results['filtered_names'] = filtered_names
            
            # Calculate confidence
            confidence = min(1.0, len(filtered_names) * 0.4 + (len(bert_names) > 0) * 0.3 + (len(pattern_names) > 0) * 0.3)
            results['confidence'] = confidence
            
            return results
            
        except Exception as e:
            logger.error(f"Error in name detection: {e}")
            return results
    
    def _extract_text(self, file_path: str) -> str:
        """Extract text from PDF or image"""
        try:
            if file_path.lower().endswith('.pdf'):
                images = pdf2image.convert_from_path(file_path, dpi=300)
                if not images:
                    return ""
                image = images[0]
            else:
                image = Image.open(file_path)
            
            text = pytesseract.image_to_string(image)
            return text
        except Exception as e:
            logger.error(f"Error extracting text: {e}")
            return ""
    
    def _detect_names_bert_ner(self, text: str) -> list:
        """Detect names using BERT NER"""
        try:
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
            
            # Extract names (PERSON entities - label 1)
            names = []
            current_name = []
            
            for i, (token, pred) in enumerate(zip(tokens_list, predictions)):
                if pred == 1:  # PERSON label
                    current_name.append(token.replace('##', ''))
                elif current_name:
                    # End of name sequence
                    full_name = ''.join(current_name).replace('##', '')
                    if len(full_name) > 2:  # Filter out very short names
                        names.append(full_name)
                    current_name = []
            
            return names
            
        except Exception as e:
            logger.error(f"Error in BERT NER name detection: {e}")
            return []
    
    def _detect_names_patterns(self, text: str) -> list:
        """Detect names using pattern matching"""
        names = []
        
        for pattern in self.name_patterns:
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                if len(match.groups()) == 1:
                    name = match.group(1).strip()
                else:
                    # For patterns with titles, combine title + name
                    title = match.group(1).strip()
                    name = match.group(2).strip()
                    name = f"{title} {name}"
                
                if name and len(name.split()) >= 2:
                    names.append(name)
        
        return names
    
    def _filter_names(self, names: list) -> list:
        """Filter and clean detected names"""
        filtered = []
        
        for name in names:
            # Clean the name
            clean_name = re.sub(r'\s+', ' ', name.strip())
            
            # Skip if too short or too long
            if len(clean_name) < 4 or len(clean_name) > 50:
                continue
            
            # Skip if contains common non-name words
            skip_words = ['email', 'phone', 'fax', 'address', 'account', 'trust', 'estate', 'llc', 'corp', 'inc', 'am', 'pm', 'com', 'http', 'www', 'outlook', 'mail', 'to', 'from', 'subject', 'date', 'time', 'attachment', 'file', 'kb', 'mb', 'bytes']
            if any(word in clean_name.lower() for word in skip_words):
                continue
            
            # Skip if it's just numbers or common words
            if re.match(r'^[0-9\s]+$', clean_name):
                continue
            
            # Skip if contains newlines or special characters
            if '\n' in clean_name or len(clean_name.split()) > 4:
                continue
            
            # Must contain at least one letter and look like a name
            if not re.search(r'[A-Za-z]', clean_name):
                continue
            
            # Must start with a capital letter
            if not clean_name[0].isupper():
                continue
            
            # Must contain at least one space (first and last name)
            if ' ' not in clean_name:
                continue
            
            filtered.append(clean_name)
        
        # Remove duplicates and sort
        unique_names = list(set(filtered))
        unique_names.sort()
        
        return unique_names

def test_document(file_path: str):
    """Test name detection on a document"""
    print(f"\n{'='*60}")
    print(f"FOCUSED NAME DETECTION TEST: {file_path}")
    print(f"{'='*60}")
    
    detector = FocusedNameDetector()
    results = detector.detect_names(file_path)
    
    print(f"\n{'='*60}")
    print("FINAL RESULTS")
    print(f"{'='*60}")
    print(f"BERT NER Names: {results['bert_ner_names']}")
    print(f"Pattern Names: {results['pattern_names']}")
    print(f"Filtered Names: {results['filtered_names']}")
    print(f"Confidence: {results['confidence']:.2f}")
    
    if results['filtered_names']:
        print(f"\nPrimary detected name: {results['filtered_names'][0]}")
        print(f"All detected names: {', '.join(results['filtered_names'])}")
    else:
        print("\nNo valid names detected")
    
    return results

if __name__ == "__main__":
    if len(sys.argv) > 1:
        file_path = sys.argv[1]
        if os.path.exists(file_path):
            test_document(file_path)
        else:
            print(f"Error: File not found: {file_path}")
    else:
        print("Usage: python3 focused_name_detector.py <document_path>")
        print("\nTesting with sample document...")
        test_document("uploads/cd10cad8-ebd9-4853-b2e3-a6aac6d0ae3d_20250211202535.pdf") 