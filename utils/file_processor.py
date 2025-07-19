import os
import shutil
from pathlib import Path
import uuid
from PIL import Image
import pdf2image
import re
import unicodedata
from models.donut_classifier import DonutTaxClassifier
from models.claude_ocr import ClaudeOCR
from config import Config

class TaxDocumentProcessor:
    def __init__(self, donut_model_path, claude_api_key):
        self.donut_classifier = DonutTaxClassifier(donut_model_path)
        self.claude_ocr = ClaudeOCR(claude_api_key)
        self.processed_folder = Config.PROCESSED_FOLDER
        
    def convert_pdf_to_images(self, pdf_path):
        """Convert PDF to images for processing"""
        try:
            images = pdf2image.convert_from_path(pdf_path, dpi=200)
            temp_images = []
            
            for i, image in enumerate(images):
                temp_path = f"temp_{uuid.uuid4()}_{i}.jpg"
                image.save(temp_path, 'JPEG')
                temp_images.append(temp_path)
            
            return temp_images
        except Exception as e:
            print(f"Error converting PDF to images: {e}")
            return []
    
    def clean_temp_files(self, temp_files):
        """Clean up temporary files"""
        for temp_file in temp_files:
            try:
                if os.path.exists(temp_file):
                    os.remove(temp_file)
            except Exception as e:
                print(f"Error cleaning temp file {temp_file}: {e}")
    
    def sanitize_filename(self, filename):
        """Remove invalid characters from filename"""
        # Replace invalid characters with space
        filename = re.sub(r'[<>:"/\\|?*]', ' ', filename)
        # Remove extra spaces and trim
        filename = re.sub(r'\s+', ' ', filename).strip()
        return filename
    
    def normalize_client_name(self, first_name, last_name):
        """
        Normalize client name for case-insensitive folder organization.
        Returns a consistent folder name regardless of case variations.
        
        Args:
            first_name: Client's first name
            last_name: Client's last name
            
        Returns:
            Normalized folder name in format "FirstName_LastName"
        """
        if not first_name or not last_name:
            return None
            
        # Clean and normalize the names
        # Remove extra whitespace and convert to title case for consistent formatting
        # This ensures "john smith", "JOHN SMITH", "John Smith" all become "John_Smith"
        normalized_first = re.sub(r'\s+', ' ', first_name.strip()).title()
        normalized_last = re.sub(r'\s+', ' ', last_name.strip()).title()
        
        # Handle special cases like hyphenated names, apostrophes, etc.
        # Keep common name patterns intact
        normalized_first = re.sub(r"([a-z])'([a-z])", r"\1'\2", normalized_first)  # Fix O'connor -> O'Connor
        normalized_last = re.sub(r"([a-z])'([a-z])", r"\1'\2", normalized_last)
        
        return f"{normalized_first}_{normalized_last}"
    
    def normalize_for_comparison(self, text):
        """
        Normalize text for case-insensitive comparison.
        Handles accented characters and case variations.
        
        Args:
            text: Text to normalize
            
        Returns:
            Normalized text for comparison purposes
        """
        if not text:
            return ""
            
        # Convert to lowercase and normalize unicode (NFD = decomposed form)
        # This converts "José" to "jose" and "García" to "garcia" for comparison
        normalized = unicodedata.normalize('NFD', text.lower())
        
        # Remove diacritical marks (accents)
        without_accents = ''.join(c for c in normalized if unicodedata.category(c) != 'Mn')
        
        # Clean whitespace
        clean_text = re.sub(r'\s+', ' ', without_accents.strip())
        
        return clean_text
    
    def find_existing_client_folder(self, first_name, last_name):
        """
        Find existing client folder with case-insensitive matching.
        
        Args:
            first_name: Client's first name
            last_name: Client's last name
            
        Returns:
            Existing folder name if found, otherwise normalized folder name
        """
        if not first_name or not last_name:
            return None
            
        # Get the normalized version
        normalized_folder = self.normalize_client_name(first_name, last_name)
        
        # Check if processed folder exists
        if not os.path.exists(self.processed_folder):
            return normalized_folder
            
        # Get all existing client folders
        try:
            existing_folders = [d for d in os.listdir(self.processed_folder) 
                              if os.path.isdir(os.path.join(self.processed_folder, d))]
        except OSError:
            return normalized_folder
            
        # Check for case-insensitive match with accent handling
        normalized_comparison = self.normalize_for_comparison(normalized_folder)
        for folder in existing_folders:
            folder_comparison = self.normalize_for_comparison(folder)
            if folder_comparison == normalized_comparison:
                # Found existing folder with same name (case-insensitive and accent-insensitive)
                print(f"Found existing client folder: {folder} (matches {normalized_folder})")
                return folder
                
        # No existing folder found, return normalized name
        return normalized_folder
    
    def process_document(self, file_path, original_filename, manual_client_info=None):
        """
        Process a single document and return processing results
        Args:
            file_path: Path to the document file
            original_filename: Original filename
            manual_client_info: Dict with 'first_name' and 'last_name' for manual mode
        Returns: dict with processing information
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
            'processed_path': None
        }
        
        try:
            # Determine if file is PDF or image
            file_ext = Path(file_path).suffix.lower()
            temp_files = []
            
            if file_ext == '.pdf':
                # Convert PDF to images
                temp_images = self.convert_pdf_to_images(file_path)
                if not temp_images:
                    result['status'] = 'error'
                    result['error'] = 'Failed to convert PDF to images'
                    return result
                
                temp_files = temp_images
                # Use first page for classification and OCR
                image_path = temp_images[0]
            else:
                # Direct image file
                image_path = file_path
            
            # Step 1: Classify document type using Donut
            doc_type, confidence = self.donut_classifier.classify_document(image_path)
            
            if doc_type and confidence > 0.5:  # Use donut result if confident
                result['document_type'] = self.donut_classifier.get_human_readable_label(doc_type)
                result['confidence'] = confidence
                print(f"Donut classified {original_filename} as: {result['document_type']} (confidence: {confidence:.2f})")
            else:
                # Step 1b: Use Claude for unknown documents
                print(f"Donut classification failed for {original_filename} (confidence: {confidence:.2f}), trying Claude...")
                claude_doc_type = self.claude_ocr.classify_unknown_document(image_path)
                result['document_type'] = claude_doc_type
                result['confidence'] = 0.7  # Assume moderate confidence for Claude classification
                print(f"Claude classified {original_filename} as: {claude_doc_type}")
            
            # Step 2: Extract client info
            if manual_client_info:
                # Manual mode - use provided client info, only extract tax year
                first_name = manual_client_info['first_name']
                last_name = manual_client_info['last_name']
                tax_year = self.claude_ocr.extract_tax_year_only(image_path)  # More efficient for manual mode
            else:
                # Auto mode - extract all info using Claude OCR
                first_name, last_name, tax_year = self.claude_ocr.extract_client_info(image_path)
                
                # If we couldn't extract client info, try comprehensive extraction as a final attempt
                if not first_name or not last_name:
                    print(f"Initial extraction failed for {original_filename}, trying comprehensive extraction...")
                    comp_first, comp_last, comp_year, comp_doc_type = self.claude_ocr.extract_comprehensive_info(image_path)
                    
                    # Use comprehensive results if we got better information
                    if comp_first and not first_name:
                        first_name = comp_first
                    if comp_last and not last_name:
                        last_name = comp_last
                    if comp_year and not tax_year:
                        tax_year = comp_year
                    # Also update document type if comprehensive extraction found something better
                    if comp_doc_type and comp_doc_type != "Unknown Document" and not result['document_type']:
                        result['document_type'] = comp_doc_type
            
            # Step 3: Generate new filename and organize
            if first_name and last_name:
                result['client_name'] = f"{first_name} {last_name}"
                client_folder_name = self.find_existing_client_folder(first_name, last_name)
                # Create last name initial with period
                last_initial = last_name[0].upper() + "." if last_name else ""
                print(f"Successfully extracted client info: {first_name} {last_name}")
            else:
                print(f"Could not extract client information for {original_filename}")
                print(f"Extracted: first_name='{first_name}', last_name='{last_name}', tax_year='{tax_year}'")
                result['client_name'] = "Unknown Client"
                client_folder_name = "Unknown_Client"
                first_name = "Unknown"
                last_initial = "C."
            
            result['tax_year'] = tax_year if tax_year else "Unknown Year"
            
            # Create sanitized filename with short document type
            year_str = str(tax_year) if tax_year else "Unknown Year"
            doc_type_clean = self._get_short_document_type(result['document_type'])
            
            if first_name and last_name:
                new_filename = f"{first_name} {last_initial} {doc_type_clean} {year_str}{file_ext}"
            else:
                new_filename = f"Unknown C. {doc_type_clean} {year_str}{file_ext}"
            
            new_filename = self.sanitize_filename(new_filename)
            result['new_filename'] = new_filename
            
            # Step 4: Handle misc documents specially (get better name but place in main client folder)
            is_misc_document = (result['document_type'] and 
                              result['document_type'].lower() in ['misc', 'other_misc', 'letter'])
            
            if is_misc_document:
                # For misc documents, use Claude to get a better name
                print(f"Processing misc document {original_filename} - getting better name from Claude...")
                better_name = self.claude_ocr.generate_misc_document_name(image_path)
                
                # Update the document type with the better name
                result['document_type'] = better_name
                doc_type_clean = better_name
                
                # Create filename with the better name: "John D. Better Name Year"
                if first_name and last_name:
                    new_filename = f"{first_name} {last_initial} {doc_type_clean} {year_str}{file_ext}"
                else:
                    new_filename = f"Unknown C. {doc_type_clean} {year_str}{file_ext}"
                
                new_filename = self.sanitize_filename(new_filename)
                result['new_filename'] = new_filename
            
            # All documents (including misc) go directly into the client folder
            client_folder_path = os.path.join(self.processed_folder, client_folder_name)
            os.makedirs(client_folder_path, exist_ok=True)
            result['client_folder'] = client_folder_name
            
            # Copy file to client folder
            new_file_path = os.path.join(client_folder_path, new_filename)
            print(f"Placing document in: {client_folder_path}")
            
            # Handle duplicate filenames
            counter = 1
            original_new_file_path = new_file_path
            while os.path.exists(new_file_path):
                base, ext = os.path.splitext(original_new_file_path)
                new_file_path = f"{base}_{counter}{ext}"
                counter += 1
            
            shutil.copy2(file_path, new_file_path)
            result['processed_path'] = new_file_path
            result['status'] = 'completed'
            
            # Clean up temp files after successful processing
            self.clean_temp_files(temp_files)
            
        except Exception as e:
            result['status'] = 'error'
            result['error'] = str(e)
            # Clean up temp files in case of error
            if 'temp_files' in locals():
                self.clean_temp_files(temp_files)
        
        return result
    
    def _get_short_document_type(self, document_type):
        """Convert document type to short form for filename"""
        if not document_type:
            return "Unknown"
        
        # Handle Claude-classified documents
        doc_lower = document_type.lower()
        if 'w-9' in doc_lower or 'w9' in doc_lower:
            return "W-9"
        elif 'w-2' in doc_lower or 'w2' in doc_lower:
            return "W-2"
        elif '1099' in doc_lower:
            # Extract specific 1099 type if present
            match = re.search(r'1099[-\s]?([A-Z]{1,4})', document_type, re.IGNORECASE)
            if match:
                return f"1099-{match.group(1).upper()}"
            return "1099"
        elif 'state tax' in doc_lower:
            return "State Tax"
        elif 'property tax' in doc_lower:
            return "Property Tax"
        
        # For Donut classifications, they're already short
        return document_type
    
    def get_processing_stats(self, results):
        """Generate statistics from processing results"""
        total = len(results)
        completed = len([r for r in results if r['status'] == 'completed'])
        errors = len([r for r in results if r['status'] == 'error'])
        
        # Count unique clients (case-insensitive and accent-insensitive)
        clients = set()
        for result in results:
            if result['status'] == 'completed' and result['client_name']:
                # Use normalized client name for counting to avoid duplicates from case and accent variations
                normalized_name = self.normalize_for_comparison(result['client_name'])
                clients.add(normalized_name)
        
        return {
            'total_documents': total,
            'completed': completed,
            'errors': errors,
            'unique_clients': len(clients),
            'success_rate': (completed / total * 100) if total > 0 else 0
        } 