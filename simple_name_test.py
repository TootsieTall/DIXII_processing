#!/usr/bin/env python3
"""
Simple name detection test focusing on BERT NER and pattern matching
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

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class SimpleNameDetector:
    """Simplified name detector using BERT NER and pattern matching"""
    
    def __init__(self):
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.bert_ner_model = None
        self.bert_ner_tokenizer = None
        self._load_bert_ner()
        
        # Tax document name patterns
        self.tax_name_patterns = {
            'estate': [
                r'ESTATE\s+OF\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)',
                r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\s+ESTATE',
                r'TRUST\s+FBO\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)',
                r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\s+TRUST'
            ],
            'business': [
                r'([A-Z][A-Z\s&]+(?:LLC|CORP|INC|CO|LTD))',
                r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\s+(?:LLC|CORP|INC|CO|LTD)'
            ],
            'person': [
                r'\b([A-Z][a-z]+\s+[A-Z][a-z]+)\b',  # Simple 2-word names
                r'\b([A-Z][a-z]+\s+[A-Z][a-z]+\s+[A-Z][a-z]+)\b',  # 3-word names
                r'MR\.\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)',
                r'MS\.\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)',
                r'MRS\.\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)'
            ]
        }
    
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
        """Detect names in document using multiple methods"""
        results = {
            'bert_ner_names': [],
            'pattern_names': [],
            'combined_names': [],
            'confidence': 0.0
        }
        
        try:
            # Extract text from document
            text = self._extract_text(file_path)
            if not text.strip():
                return results
            
            print(f"\nExtracted text (first 500 chars):")
            print(text[:500])
            print("..." if len(text) > 500 else "")
            
            # Method 1: BERT NER
            if self.bert_ner_model and self.bert_ner_tokenizer:
                bert_names = self._detect_names_bert_ner(text)
                results['bert_ner_names'] = bert_names
                print(f"\nBERT NER found {len(bert_names)} names: {bert_names}")
            
            # Method 2: Pattern matching
            pattern_names = self._detect_names_patterns(text)
            results['pattern_names'] = pattern_names
            print(f"\nPattern matching found {len(pattern_names)} names: {pattern_names}")
            
            # Combine results
            all_names = bert_names + pattern_names
            unique_names = list(set(all_names))  # Remove duplicates
            results['combined_names'] = unique_names
            
            # Calculate confidence
            confidence = min(1.0, len(unique_names) * 0.3 + (len(bert_names) > 0) * 0.4 + (len(pattern_names) > 0) * 0.3)
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
        
        for category, patterns in self.tax_name_patterns.items():
            for pattern in patterns:
                matches = re.finditer(pattern, text, re.IGNORECASE)
                for match in matches:
                    name = match.group(1).strip()
                    if name and len(name.split()) >= 1:
                        names.append(name)
        
        return names

def test_document(file_path: str):
    """Test name detection on a document"""
    print(f"\n{'='*60}")
    print(f"TESTING NAME DETECTION ON: {file_path}")
    print(f"{'='*60}")
    
    detector = SimpleNameDetector()
    results = detector.detect_names(file_path)
    
    print(f"\n{'='*60}")
    print("RESULTS")
    print(f"{'='*60}")
    print(f"BERT NER Names: {results['bert_ner_names']}")
    print(f"Pattern Names: {results['pattern_names']}")
    print(f"Combined Names: {results['combined_names']}")
    print(f"Confidence: {results['confidence']:.2f}")
    
    if results['combined_names']:
        print(f"\nPrimary detected name: {results['combined_names'][0]}")
    else:
        print("\nNo names detected")
    
    return results

if __name__ == "__main__":
    if len(sys.argv) > 1:
        file_path = sys.argv[1]
        if os.path.exists(file_path):
            test_document(file_path)
        else:
            print(f"Error: File not found: {file_path}")
    else:
        print("Usage: python3 simple_name_test.py <document_path>")
        print("\nTesting with sample document...")
        test_document("uploads/cd10cad8-ebd9-4853-b2e3-a6aac6d0ae3d_20250211201838.pdf") 