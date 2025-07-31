import os
import re
import unicodedata
import logging
from typing import Tuple, Dict, Optional, List

class EntityRecognizer:
    def __init__(self, processed_folder: str):
        self.processed_folder = processed_folder
        self.logger = logging.getLogger(__name__)
        
        # Business entity indicators and their normalized forms
        self.entity_patterns = {
            'LLC': {
                'indicators': ['LLC', 'L.L.C.', 'LIMITED LIABILITY COMPANY', 'LTD LIABILITY CO', 'LTD LIABILITY'],
                'suffixes': ['LLC', 'L.L.C.'],
                'normalized_suffix': 'LLC'
            },
            'Corporation': {
                'indicators': ['CORP', 'INC', 'CORPORATION', 'INCORPORATED', 'CO.', 'COMPANY'],
                'suffixes': ['Corp', 'Inc', 'Co'],
                'normalized_suffix': 'Corp'
            },
            'Partnership': {
                'indicators': ['PARTNERSHIP', 'PARTNERS', 'LP', 'LLP', 'L.P.', 'L.L.P.', 'LIMITED PARTNERSHIP'],
                'suffixes': ['LP', 'LLP', 'Partnership'],
                'normalized_suffix': 'LP'
            },
            'Trust': {
                'indicators': ['TRUST', 'TR', 'FBO', 'TRUSTEE', 'FAMILY TRUST', 'LIVING TRUST'],
                'suffixes': ['Trust', 'Tr'],
                'normalized_suffix': 'Trust'
            },
            'Estate': {
                'indicators': ['ESTATE', 'EST', 'ESTATE OF'],
                'suffixes': ['Estate', 'Est'],
                'normalized_suffix': 'Estate'
            },
            'S-Corporation': {
                'indicators': ['S CORP', 'S-CORP', 'S CORPORATION', 'S-CORPORATION'],
                'suffixes': ['S-Corp'],
                'normalized_suffix': 'S-Corp'
            }
        }
        
        # Joint return patterns
        self.joint_patterns = [
            r'(.+?)\s+&\s+(.+)',  # John & Jane Smith
            r'(.+?)\s+AND\s+(.+)',  # John AND Jane Smith
            r'(.+?),\s*(.+)',  # John, Jane Smith (less common)
        ]
        
        # Trust name patterns
        self.trust_patterns = [
            r'(.+?)\s+TRUST',
            r'(.+?)\s+FAMILY\s+TRUST',
            r'(.+?)\s+LIVING\s+TRUST',
            r'TRUST\s+FBO\s+(.+)',
            r'(.+?)\s+TR',
        ]
    
    def analyze_entity(self, extracted_info: Dict) -> Dict:
        """
        Analyze extracted document information to determine entity type and naming
        
        Args:
            extracted_info: Dictionary from enhanced Claude OCR
            
        Returns:
            Dictionary with entity analysis results
        """
        try:
            # Determine primary entity name and type
            entity_info = self._determine_primary_entity(extracted_info)
            
            # Validate entity_info is not None
            if entity_info is None:
                self.logger.warning("_determine_primary_entity returned None, using default")
                entity_info = self._default_entity_info()
            
            # If it's an individual, check for joint returns
            if entity_info.get('entity_type') == 'Individual':
                joint_info = self._analyze_joint_return(extracted_info)
                if joint_info['is_joint']:
                    entity_info.update(joint_info)
            
            # Generate normalized folder name
            folder_name = self._generate_folder_name(entity_info)
            
            # Find existing folder with case-insensitive matching
            existing_folder = self._find_existing_folder(folder_name)
            
            entity_info.update({
                'folder_name': folder_name,
                'existing_folder': existing_folder,
                'final_folder': existing_folder or folder_name
            })
            
            return entity_info
            
        except Exception as e:
            self.logger.error(f"Error analyzing entity: {e}")
            return self._default_entity_info()
    
    def _determine_primary_entity(self, extracted_info: Dict) -> Dict:
        """ENHANCED: Determine the primary entity from extracted information with improved name handling"""
        doc_type = extracted_info.get('document_type', '')
        
        # ENHANCED: Check for mapped names first (from enhanced name detection)
        mapped_first_name = extracted_info.get('mapped_first_name')
        mapped_last_name = extracted_info.get('mapped_last_name')
        
        if mapped_first_name and mapped_last_name:
            # Use mapped names from enhanced detection
            first_name = mapped_first_name
            last_name = mapped_last_name
            self.logger.info(f"Using mapped names from enhanced detection: {first_name} {last_name}")
        else:
            # Fallback to document-specific field extraction
            first_name = None
            last_name = None
        
        # For K-1s, the recipient (partner) is the primary entity
        if 'K-1' in doc_type or 'Schedule K-1' in doc_type:
            if not first_name or not last_name:
                first_name = extracted_info.get('partner_first_name')
                last_name = extracted_info.get('partner_last_name')
            
            partnership_name = extracted_info.get('partnership_name')
            
            if first_name and last_name:
                return {
                    'entity_type': 'Individual',
                    'first_name': first_name,
                    'last_name': last_name,
                    'business_name': None,
                    'source_entity': partnership_name,
                    'document_context': 'K-1 Recipient'
                }
            else:
                # Fallback for K-1 without clear recipient names
                return {
                    'entity_type': 'Individual',
                    'first_name': 'Unknown',
                    'last_name': 'Partner',
                    'business_name': None,
                    'source_entity': partnership_name,
                    'document_context': 'K-1 Recipient (Unknown Names)'
                }
        
        # For 1099s, the recipient is the primary entity
        elif '1099' in doc_type:
            # Check if recipient is business or individual
            business_name = extracted_info.get('recipient_business_name')
            if business_name:
                entity_type, clean_name = self._classify_business_entity(business_name)
                return {
                    'entity_type': entity_type,
                    'first_name': None,
                    'last_name': None,
                    'business_name': clean_name,
                    'source_entity': extracted_info.get('payer_name'),
                    'document_context': '1099 Recipient'
                }
            else:
                if not first_name or not last_name:
                    first_name = extracted_info.get('recipient_first_name') or 'Unknown'
                    last_name = extracted_info.get('recipient_last_name') or 'Recipient'
                return {
                    'entity_type': 'Individual',
                    'first_name': first_name,
                    'last_name': last_name,
                    'business_name': None,
                    'source_entity': extracted_info.get('payer_name'),
                    'document_context': '1099 Recipient'
                }
        
        # For W-2s, the employee is the primary entity
        elif 'W-2' in doc_type:
            if not first_name or not last_name:
                first_name = extracted_info.get('employee_first_name') or 'Unknown'
                last_name = extracted_info.get('employee_last_name') or 'Employee'
            return {
                'entity_type': 'Individual',
                'first_name': first_name,
                'last_name': last_name,
                'business_name': None,
                'source_entity': extracted_info.get('employer_name'),
                'document_context': 'W-2 Employee'
            }
        
        # For 1098s, the borrower/student is the primary entity
        elif '1098' in doc_type:
            if not first_name or not last_name:
                first_name = extracted_info.get('borrower_first_name') or 'Unknown'
                last_name = extracted_info.get('borrower_last_name') or 'Borrower'
            return {
                'entity_type': 'Individual',
                'first_name': first_name,
                'last_name': last_name,
                'business_name': None,
                'source_entity': extracted_info.get('lender_name'),
                'document_context': '1098 Borrower'
            }
        
        # For 1040s, primary taxpayer is the main entity
        elif '1040' in doc_type:
            if not first_name or not last_name:
                first_name = extracted_info.get('primary_first_name') or 'Unknown'
                last_name = extracted_info.get('primary_last_name') or 'Taxpayer'
            return {
                'entity_type': 'Individual',
                'first_name': first_name,
                'last_name': last_name,
                'business_name': None,
                'source_entity': None,
                'document_context': '1040 Taxpayer'
            }
        
        # Generic extraction
        else:
            business_name = extracted_info.get('business_name')
            if business_name:
                entity_type, clean_name = self._classify_business_entity(business_name)
                return {
                    'entity_type': entity_type,
                    'first_name': None,
                    'last_name': None,
                    'business_name': clean_name,
                    'source_entity': None,
                    'document_context': 'Generic Business'
                }
            else:
                if not first_name or not last_name:
                    first_name = extracted_info.get('person_first_name') or 'Unknown'
                    last_name = extracted_info.get('person_last_name') or 'Individual'
                return {
                    'entity_type': 'Individual',
                    'first_name': first_name,
                    'last_name': last_name,
                    'business_name': None,
                    'source_entity': None,
                    'document_context': 'Generic Individual'
                }
    
    def _classify_business_entity(self, business_name: str) -> Tuple[str, str]:
        """Classify business entity type and clean the name"""
        if not business_name:
            return 'Individual', business_name
        
        name_upper = business_name.upper()
        
        # Check each entity type
        for entity_type, config in self.entity_patterns.items():
            for indicator in config['indicators']:
                if indicator in name_upper:
                    clean_name = self._clean_business_name(business_name, entity_type)
                    return entity_type, clean_name
        
        # Check for trust patterns specifically
        for pattern in self.trust_patterns:
            if re.search(pattern, name_upper):
                clean_name = self._clean_trust_name(business_name)
                return 'Trust', clean_name
        
        return 'Business', business_name
    
    def _analyze_joint_return(self, extracted_info: Dict) -> Dict:
        """Analyze if this is a joint return and extract both names"""
        doc_type = extracted_info.get('document_type', '')
        
        # Check 1040 joint return
        if '1040' in doc_type:
            spouse_first = extracted_info.get('spouse_first_name')
            spouse_last = extracted_info.get('spouse_last_name')
            is_joint = extracted_info.get('is_joint_return', False)
            
            if spouse_first and spouse_last and is_joint:
                return {
                    'is_joint': True,
                    'spouse_first_name': spouse_first,
                    'spouse_last_name': spouse_last
                }
        
        # Check for joint patterns in any name field
        name_fields = [
            extracted_info.get('primary_first_name', ''),
            extracted_info.get('partner_first_name', ''),
            extracted_info.get('recipient_first_name', ''),
            extracted_info.get('employee_first_name', ''),
            extracted_info.get('borrower_first_name', ''),
            extracted_info.get('person_first_name', '')
        ]
        
        for full_name in name_fields:
            if full_name:
                joint_result = self._parse_joint_name(full_name)
                if joint_result['is_joint']:
                    return joint_result
        
        return {'is_joint': False}
    
    def _parse_joint_name(self, full_name: str) -> Dict:
        """Parse potential joint name like 'John & Jane Smith'"""
        if not full_name:
            return {'is_joint': False}
        
        for pattern in self.joint_patterns:
            match = re.match(pattern, full_name.strip(), re.IGNORECASE)
            if match:
                first_part = match.group(1).strip()
                second_part = match.group(2).strip()
                
                # Try to parse as "First1 & First2 Last"
                if ' ' not in second_part:  # Second part is likely just second first name
                    # Assume they share the same last name
                    # This is a simplified approach - real implementation might need more logic
                    return {
                        'is_joint': True,
                        'spouse_first_name': second_part,
                        'spouse_last_name': None  # Will use primary last name
                    }
                else:
                    # Second part contains first and last name
                    second_parts = second_part.split()
                    if len(second_parts) >= 2:
                        return {
                            'is_joint': True,
                            'spouse_first_name': second_parts[0],
                            'spouse_last_name': ' '.join(second_parts[1:])
                        }
        
        return {'is_joint': False}
    
    def _clean_business_name(self, business_name: str, entity_type: str) -> str:
        """Clean business name by standardizing entity suffixes"""
        if not business_name:
            return business_name
        
        # Remove existing suffixes and add normalized suffix
        config = self.entity_patterns.get(entity_type, {})
        name_clean = business_name
        
        # Remove known suffixes
        for suffix in config.get('suffixes', []):
            # Remove suffix with word boundaries
            pattern = r'\b' + re.escape(suffix) + r'\b'
            name_clean = re.sub(pattern, '', name_clean, flags=re.IGNORECASE)
        
        # Clean up extra spaces
        name_clean = re.sub(r'\s+', ' ', name_clean).strip()
        
        # Add normalized suffix
        normalized_suffix = config.get('normalized_suffix', '')
        if normalized_suffix:
            name_clean = f"{name_clean} {normalized_suffix}"
        
        return name_clean
    
    def _clean_trust_name(self, trust_name: str) -> str:
        """Clean trust name to standard format"""
        if not trust_name:
            return trust_name
        
        # Remove common trust suffixes and standardize
        trust_clean = trust_name
        trust_upper = trust_name.upper()
        
        # Handle "TRUST FBO JOHN SMITH" -> "John Smith Trust"
        fbo_match = re.search(r'TRUST\s+FBO\s+(.+)', trust_upper)
        if fbo_match:
            beneficiary = fbo_match.group(1)
            return f"{beneficiary.title()} Trust"
        
        # Handle "JOHN SMITH FAMILY TRUST" -> "John Smith Family Trust"
        family_match = re.search(r'(.+?)\s+FAMILY\s+TRUST', trust_upper)
        if family_match:
            name = family_match.group(1)
            return f"{name.title()} Family Trust"
        
        # Handle "JOHN SMITH TRUST" -> "John Smith Trust"
        basic_match = re.search(r'(.+?)\s+TRUST', trust_upper)
        if basic_match:
            name = basic_match.group(1)
            return f"{name.title()} Trust"
        
        return trust_name
    
    def _generate_folder_name(self, entity_info: Dict) -> str:
        """Generate folder name based on entity information"""
        entity_type = entity_info.get('entity_type', 'Individual')
        
        if entity_type == 'Individual':
            first_name = entity_info.get('first_name')
            last_name = entity_info.get('last_name')
            
            if not first_name or not last_name:
                return 'Unknown_Client'
            
            # Check for joint return
            if entity_info.get('is_joint'):
                spouse_first = entity_info.get('spouse_first_name')
                spouse_last = entity_info.get('spouse_last_name', last_name)  # Default to primary last name
                
                if spouse_first:
                    return f"{first_name}_{spouse_first}_{spouse_last or last_name}"
            
            return f"{first_name}_{last_name}"
        
        else:
            # Business entity
            business_name = entity_info.get('business_name')
            if business_name:
                # Replace spaces with underscores and clean invalid characters
                folder_name = re.sub(r'[<>:"/\\|?*]', '', business_name)
                folder_name = re.sub(r'\s+', '_', folder_name)
                return folder_name
            else:
                return f'Unknown_{entity_type}'
    
    def _find_existing_folder(self, folder_name: str) -> Optional[str]:
        """Find existing folder with case-insensitive matching"""
        if not folder_name or not os.path.exists(self.processed_folder):
            return None
        
        try:
            existing_folders = [d for d in os.listdir(self.processed_folder) 
                              if os.path.isdir(os.path.join(self.processed_folder, d))]
        except OSError:
            return None
        
        # Normalize for comparison
        normalized_target = self._normalize_for_comparison(folder_name)
        
        for existing_folder in existing_folders:
            normalized_existing = self._normalize_for_comparison(existing_folder)
            if normalized_existing == normalized_target:
                self.logger.info(f"Found existing folder: {existing_folder} (matches {folder_name})")
                return existing_folder
        
        return None
    
    def _normalize_for_comparison(self, text: str) -> str:
        """Normalize text for case-insensitive comparison"""
        if not text:
            return ""
        
        # Convert to lowercase and normalize unicode
        normalized = unicodedata.normalize('NFD', text.lower())
        
        # Remove diacritical marks
        without_accents = ''.join(c for c in normalized if unicodedata.category(c) != 'Mn')
        
        # Clean whitespace and underscores
        clean_text = re.sub(r'[\s_]+', '_', without_accents.strip())
        
        return clean_text
    
    def _default_entity_info(self) -> Dict:
        """Return default entity info for error cases"""
        return {
            'entity_type': 'Individual',
            'first_name': None,
            'last_name': None,
            'business_name': None,
            'folder_name': 'Unknown_Client',
            'existing_folder': None,
            'final_folder': 'Unknown_Client',
            'is_joint': False,
            'document_context': 'Unknown'
        }
    
    def get_entity_summary(self, entity_info: Dict) -> str:
        """Get human-readable summary of entity"""
        entity_type = entity_info.get('entity_type', 'Unknown')
        
        if entity_type == 'Individual':
            if entity_info.get('is_joint'):
                first_name = entity_info.get('first_name', 'Unknown')
                last_name = entity_info.get('last_name', 'Unknown')
                spouse_first = entity_info.get('spouse_first_name', 'Unknown')
                return f"{first_name} & {spouse_first} {last_name} (Joint Return)"
            else:
                first_name = entity_info.get('first_name', 'Unknown')
                last_name = entity_info.get('last_name', 'Unknown')
                return f"{first_name} {last_name}"
        else:
            business_name = entity_info.get('business_name', 'Unknown Business')
            return f"{business_name} ({entity_type})" 