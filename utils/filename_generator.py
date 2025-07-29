import re
import os
import logging
from typing import Dict, Optional, Tuple
from pathlib import Path

class FilenameGenerator:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        
        # Filename templates for different document types and entity types
        self.templates = {
            'individual': {
                'default': '{first_name} {last_initial} {doc_type} {year}{amended}.{ext}',
                'k1': '{first_name} {last_initial} K-1 {partnership} {year}{amended}.{ext}',
                '1099': '{first_name} {last_initial} {form_type} {payer} {year}{amended}.{ext}',
                'w2': '{first_name} {last_initial} W-2 {employer} {year}{amended}.{ext}',
                '1098': '{first_name} {last_initial} {form_type} {lender} {year}{amended}.{ext}',
                '1040': '{first_name} {last_initial} {form_type} {year}{amended}.{ext}',
                'joint': '{first_name} {spouse_first} {last_name} {doc_type} {year}{amended}.{ext}'
            },
            'business': {
                'default': '{business_name} {doc_type} {year}{amended}.{ext}',
                'k1': '{business_name} K-1 {partnership} {year}{amended}.{ext}',
                '1099': '{business_name} {form_type} {payer} {year}{amended}.{ext}',
                'w2': '{business_name} W-2 {employer} {year}{amended}.{ext}',
                'tax_return': '{business_name} {form_type} {year}{amended}.{ext}'
            }
        }
        
        # Document type abbreviations for filename efficiency
        self.doc_abbreviations = {
            'Form 1040': '1040',
            'Form 1040EZ': '1040EZ',
            'Form 1040A': '1040A',
            'Form 1040NR': '1040NR',
            'Form 1040X': '1040X',
            'Form 1120': '1120',
            'Form 1120S': '1120S',
            'Form 1065': '1065',
            'Form 1041': '1041',
            'Form W-2': 'W-2',
            'Form W-9': 'W-9',
            'Form 1099-NEC': '1099-NEC',
            'Form 1099-MISC': '1099-MISC',
            'Form 1099-INT': '1099-INT',
            'Form 1099-DIV': '1099-DIV',
            'Form 1099-R': '1099-R',
            'Form 1098': '1098',
            'Form 1098-E': '1098-E',
            'Form 1098-T': '1098-T',
            'Schedule K-1': 'K-1',
            'Property Tax Statement': 'Property Tax',
            'Bank Statement': 'Bank Statement',
            'Investment Statement': 'Investment Statement'
        }
        
        # Amendment indicators
        self.amendment_indicators = [
            'AMENDED', 'CORRECTED', 'SUPERSEDED', 'REVISED', 'SUBSTITUTE'
        ]
        
        # State abbreviations for state forms
        self.state_forms = {
            'CA': 'CA', 'NY': 'NY', 'TX': 'TX', 'FL': 'FL', 'IL': 'IL',
            # Add more states as needed
        }
    
    def generate_filename(self, extracted_info: Dict, entity_info: Dict, 
                         original_filename: str) -> str:
        """
        Generate intelligent filename based on document and entity information
        
        Args:
            extracted_info: Information extracted from document
            entity_info: Entity analysis results
            original_filename: Original filename for extension
            
        Returns:
            Generated filename string
        """
        try:
            # Get file extension
            ext = self._get_file_extension(original_filename)
            
            # Determine document type and get abbreviation
            doc_type = self._get_document_abbreviation(extracted_info.get('document_type', ''))
            
            # Check for amendments
            amended_suffix = self._get_amendment_suffix(extracted_info)
            
            # Get tax year
            year = extracted_info.get('tax_year') or 'Unknown_Year'
            
            # Generate filename based on entity type
            if entity_info.get('entity_type') == 'Individual':
                filename = self._generate_individual_filename(
                    extracted_info, entity_info, doc_type, year, amended_suffix, ext
                )
            else:
                filename = self._generate_business_filename(
                    extracted_info, entity_info, doc_type, year, amended_suffix, ext
                )
            
            # Clean and validate filename
            filename = self._clean_filename(filename)
            
            return filename
            
        except Exception as e:
            self.logger.error(f"Error generating filename: {e}")
            return self._generate_fallback_filename(original_filename, extracted_info)
    
    def _generate_individual_filename(self, extracted_info: Dict, entity_info: Dict,
                                    doc_type: str, year: str, amended_suffix: str, ext: str) -> str:
        """Generate filename for individual entities"""
        first_name = entity_info.get('first_name', 'Unknown')
        last_name = entity_info.get('last_name', 'Unknown')
        last_initial = last_name[0].upper() + '.' if last_name and last_name != 'Unknown' else 'U.'
        
        # Check for joint return
        if entity_info.get('is_joint'):
            spouse_first = entity_info.get('spouse_first_name', 'Unknown')
            template = self.templates['individual']['joint']
            return template.format(
                first_name=first_name,
                spouse_first=spouse_first,
                last_name=last_name,
                doc_type=doc_type,
                year=year,
                amended=amended_suffix,
                ext=ext
            )
        
        # Document-specific templates
        document_type = extracted_info.get('document_type', '').lower()
        
        if 'k-1' in document_type or 'schedule k-1' in document_type:
            partnership = self._clean_entity_name(extracted_info.get('partnership_name', 'Unknown'))
            template = self.templates['individual']['k1']
            return template.format(
                first_name=first_name,
                last_initial=last_initial,
                partnership=partnership,
                year=year,
                amended=amended_suffix,
                ext=ext
            )
        
        elif '1099' in document_type:
            form_type = extracted_info.get('form_type', '1099')
            payer = self._clean_entity_name(extracted_info.get('payer_name', 'Unknown'))
            template = self.templates['individual']['1099']
            return template.format(
                first_name=first_name,
                last_initial=last_initial,
                form_type=form_type,
                payer=payer,
                year=year,
                amended=amended_suffix,
                ext=ext
            )
        
        elif 'w-2' in document_type:
            employer = self._clean_entity_name(extracted_info.get('employer_name', 'Unknown'))
            template = self.templates['individual']['w2']
            return template.format(
                first_name=first_name,
                last_initial=last_initial,
                employer=employer,
                year=year,
                amended=amended_suffix,
                ext=ext
            )
        
        elif '1098' in document_type:
            form_type = extracted_info.get('form_type', '1098')
            lender = self._clean_entity_name(extracted_info.get('lender_name', 'Unknown'))
            template = self.templates['individual']['1098']
            return template.format(
                first_name=first_name,
                last_initial=last_initial,
                form_type=form_type,
                lender=lender,
                year=year,
                amended=amended_suffix,
                ext=ext
            )
        
        elif '1040' in document_type:
            form_type = self._get_specific_1040_type(extracted_info)
            # Check for state form
            state = extracted_info.get('state')
            if state:
                form_type = f"{state}_{form_type}"
            
            template = self.templates['individual']['1040']
            return template.format(
                first_name=first_name,
                last_initial=last_initial,
                form_type=form_type,
                year=year,
                amended=amended_suffix,
                ext=ext
            )
        
        else:
            # Default individual template
            template = self.templates['individual']['default']
            return template.format(
                first_name=first_name,
                last_initial=last_initial,
                doc_type=doc_type,
                year=year,
                amended=amended_suffix,
                ext=ext
            )
    
    def _generate_business_filename(self, extracted_info: Dict, entity_info: Dict,
                                  doc_type: str, year: str, amended_suffix: str, ext: str) -> str:
        """Generate filename for business entities"""
        business_name = self._clean_entity_name(entity_info.get('business_name', 'Unknown_Business'))
        
        document_type = extracted_info.get('document_type', '').lower()
        
        if 'k-1' in document_type:
            partnership = self._clean_entity_name(extracted_info.get('partnership_name', 'Unknown'))
            template = self.templates['business']['k1']
            return template.format(
                business_name=business_name,
                partnership=partnership,
                year=year,
                amended=amended_suffix,
                ext=ext
            )
        
        elif '1099' in document_type:
            form_type = extracted_info.get('form_type', '1099')
            payer = self._clean_entity_name(extracted_info.get('payer_name', 'Unknown'))
            template = self.templates['business']['1099']
            return template.format(
                business_name=business_name,
                form_type=form_type,
                payer=payer,
                year=year,
                amended=amended_suffix,
                ext=ext
            )
        
        elif any(tax_form in document_type for tax_form in ['1120', '1065', '1041']):
            form_type = self._get_business_tax_form_type(extracted_info)
            template = self.templates['business']['tax_return']
            return template.format(
                business_name=business_name,
                form_type=form_type,
                year=year,
                amended=amended_suffix,
                ext=ext
            )
        
        else:
            # Default business template
            template = self.templates['business']['default']
            return template.format(
                business_name=business_name,
                doc_type=doc_type,
                year=year,
                amended=amended_suffix,
                ext=ext
            )
    
    def _get_document_abbreviation(self, document_type: str) -> str:
        """Get abbreviated document type for filename"""
        if not document_type:
            return 'Unknown_Doc'
        
        # Check exact matches first
        for full_name, abbrev in self.doc_abbreviations.items():
            if full_name.lower() in document_type.lower():
                return abbrev
        
        # Extract form numbers if present
        form_match = re.search(r'(Form\s+)?(\d{4}[A-Z]*(?:-[A-Z0-9]+)?)', document_type, re.IGNORECASE)
        if form_match:
            return form_match.group(2)
        
        # Extract other recognizable patterns
        if 'schedule' in document_type.lower():
            schedule_match = re.search(r'Schedule\s+([A-Z0-9-]+)', document_type, re.IGNORECASE)
            if schedule_match:
                return f"Sch_{schedule_match.group(1)}"
        
        # Fallback to cleaned document type
        clean_type = re.sub(r'[^A-Za-z0-9 -]', ' ', document_type)
        clean_type = re.sub(r'\s+', ' ', clean_type).strip(' ')
        return clean_type[:20]  # Limit length
    
    def _get_amendment_suffix(self, extracted_info: Dict) -> str:
        """Get amendment suffix for filename"""
        if extracted_info.get('is_amended'):
            amendment_type = extracted_info.get('amendment_type', 'AMENDED')
            return f"_{amendment_type}"
        return ""
    
    def _get_specific_1040_type(self, extracted_info: Dict) -> str:
        """Get specific 1040 form type"""
        form_type = extracted_info.get('form_type', '')
        if form_type and '1040' in form_type:
            return form_type
        return '1040'
    
    def _get_business_tax_form_type(self, extracted_info: Dict) -> str:
        """Get business tax form type"""
        form_type = extracted_info.get('form_type', '')
        document_type = extracted_info.get('document_type', '')
        
        # Check form_type first
        if form_type:
            return form_type
        
        # Extract from document_type
        for form_num in ['1120S', '1120', '1065', '1041']:
            if form_num in document_type:
                return form_num
        
        return 'Tax_Return'
    
    def _clean_entity_name(self, name: str) -> str:
        """Clean entity name for use in filenames"""
        if not name or name == 'Unknown':
            return 'Unknown'
        
        # Remove problematic characters
        clean_name = re.sub(r'[<>:"/\\|?*]', '', name)
        
        # Keep spaces instead of underscores, just clean up multiple spaces
        clean_name = re.sub(r'\s+', ' ', clean_name)
        
        # Remove leading/trailing spaces
        clean_name = clean_name.strip(' ')
        
        # Limit length and handle abbreviation if too long
        if len(clean_name) > 30:
            clean_name = self._abbreviate_name(clean_name)
        
        return clean_name
    
    def _abbreviate_name(self, name: str) -> str:
        """Intelligently abbreviate long names"""
        if len(name) <= 30:
            return name
        
        # Split by underscores (spaces converted to underscores)
        parts = name.split('_')
        
        # If single word, truncate
        if len(parts) == 1:
            return name[:30]
        
        # Abbreviate each part
        abbreviated_parts = []
        for part in parts:
            if len(part) > 8:
                # Keep first 5 chars + last 3 chars for longer words
                abbreviated_parts.append(part[:5] + part[-3:])
            elif len(part) > 3:
                # Keep first 3 chars for medium words
                abbreviated_parts.append(part[:3])
            else:
                # Keep short words as is
                abbreviated_parts.append(part)
        
        result = '_'.join(abbreviated_parts)
        
        # If still too long, take first 30 characters
        if len(result) > 30:
            result = result[:30]
        
        return result
    
    def _get_file_extension(self, filename: str) -> str:
        """Get file extension from filename"""
        return Path(filename).suffix.lower().lstrip('.')
    
    def _clean_filename(self, filename: str) -> str:
        """Clean filename to ensure it's valid"""
        # Remove invalid characters
        filename = re.sub(r'[<>:"/\\|?*]', '', filename)
        
        # Clean up multiple spaces and replace underscores with spaces
        filename = re.sub(r'_+', ' ', filename)  # Replace underscores with spaces
        filename = re.sub(r'\s+', ' ', filename)  # Clean up multiple spaces
        
        # Remove leading/trailing spaces and dots
        filename = filename.strip(' .')
        
        # Ensure it's not empty
        if not filename:
            filename = "Unknown Document"
        
        return filename
    
    def _generate_fallback_filename(self, original_filename: str, extracted_info: Dict) -> str:
        """Generate fallback filename when normal generation fails"""
        try:
            base_name = Path(original_filename).stem
            ext = Path(original_filename).suffix
            
            # Try to get year
            year = extracted_info.get('tax_year', 'Unknown_Year')
            
            return f"Processed_{base_name}_{year}{ext}"
            
        except Exception:
            return f"Processed_{original_filename}"
    
    def resolve_filename_conflict(self, filename: str, destination_folder: str) -> str:
        """Resolve filename conflicts by appending numbers"""
        if not os.path.exists(destination_folder):
            return filename
        
        base_name = Path(filename).stem
        extension = Path(filename).suffix
        
        counter = 1
        new_filename = filename
        
        while os.path.exists(os.path.join(destination_folder, new_filename)):
            new_filename = f"{base_name}_{counter:02d}{extension}"
            counter += 1
            
            # Prevent infinite loop
            if counter > 99:
                break
        
        return new_filename
    
    def get_filename_preview(self, extracted_info: Dict, entity_info: Dict, 
                           original_filename: str) -> Dict:
        """Get filename preview with explanation"""
        try:
            filename = self.generate_filename(extracted_info, entity_info, original_filename)
            
            # Generate explanation
            explanation_parts = []
            
            entity_type = entity_info.get('entity_type', 'Unknown')
            if entity_type == 'Individual':
                if entity_info.get('is_joint'):
                    explanation_parts.append("Joint return detected")
                else:
                    explanation_parts.append("Individual return")
            else:
                explanation_parts.append(f"{entity_type} entity")
            
            doc_type = extracted_info.get('document_type', 'Unknown')
            explanation_parts.append(f"Document: {doc_type}")
            
            if extracted_info.get('is_amended'):
                explanation_parts.append("Amendment detected")
            
            year = extracted_info.get('tax_year')
            if year:
                explanation_parts.append(f"Tax year: {year}")
            
            return {
                'filename': filename,
                'explanation': ' | '.join(explanation_parts),
                'confidence': extracted_info.get('confidence', 0.0)
            }
            
        except Exception as e:
            self.logger.error(f"Error generating filename preview: {e}")
            return {
                'filename': self._generate_fallback_filename(original_filename, extracted_info),
                'explanation': 'Fallback filename due to processing error',
                'confidence': 0.0
            } 