import anthropic
import base64
import os
from PIL import Image
import io
import re
import json
import logging

class EnhancedClaudeOCR:
    def __init__(self, api_key):
        self.client = anthropic.Anthropic(api_key=api_key)
        self.logger = logging.getLogger(__name__)
        
        # Configuration for amendment and correction indicators
        self.amendment_indicators = [
            'AMENDED', 'CORRECTED', 'SUPERSEDED', 'REVISED', 'SUBSTITUTE',
            'CORRECTION', 'AMENDMENT', 'SUPERSEDING'
        ]
        
        # Business entity indicators
        self.entity_indicators = {
            'LLC': ['LLC', 'L.L.C.', 'LIMITED LIABILITY COMPANY', 'LTD LIABILITY CO'],
            'Corporation': ['CORP', 'INC', 'CORPORATION', 'INCORPORATED', 'CO.'],
            'Partnership': ['PARTNERSHIP', 'PARTNERS', 'LP', 'LLP', 'L.P.', 'L.L.P.'],
            'Trust': ['TRUST', 'TR', 'FBO', 'TRUSTEE'],
            'Estate': ['ESTATE', 'EST'],
            'S-Corp': ['S CORP', 'S-CORP', 'S CORPORATION']
        }
    
    def image_to_base64(self, image_path):
        """Convert image to base64 for Claude API with optimization"""
        try:
            with Image.open(image_path) as img:
                # Convert to RGB if necessary
                if img.mode != 'RGB':
                    img = img.convert('RGB')
                
                # Resize image if too large (Claude has size limits)
                max_size = (1568, 1568)
                img.thumbnail(max_size, Image.Resampling.LANCZOS)
                
                # Convert to base64
                buffer = io.BytesIO()
                img.save(buffer, format='JPEG', quality=90)
                img_data = buffer.getvalue()
                return base64.b64encode(img_data).decode('utf-8')
        except Exception as e:
            self.logger.error(f"Error converting image to base64: {e}")
            return None
    
    def extract_comprehensive_document_info(self, image_path):
        """
        Multi-pass extraction that identifies document type first, then extracts specific information
        Returns: dict with all extracted information
        """
        try:
            img_base64 = self.image_to_base64(image_path)
            if not img_base64:
                return self._empty_result()
            
            # First pass: Document identification and basic info
            doc_type, basic_info = self._identify_document_type(img_base64)
            
            # Second pass: Form-specific detailed extraction
            if doc_type in ['K-1', 'Schedule K-1']:
                detailed_info = self._extract_k1_info(img_base64)
            elif 'Form 1099' in doc_type or '1099' in doc_type:
                detailed_info = self._extract_1099_info(img_base64)
            elif 'Form W-2' in doc_type or 'W-2' in doc_type:
                detailed_info = self._extract_w2_info(img_base64)
            elif 'Form 1098' in doc_type or '1098' in doc_type:
                detailed_info = self._extract_1098_info(img_base64)
            elif 'Form 1040' in doc_type or '1040' in doc_type:
                detailed_info = self._extract_1040_info(img_base64)
            else:
                # Generic extraction for other documents
                detailed_info = self._extract_generic_info(img_base64)
            
            # Merge results
            result = {**basic_info, **detailed_info}
            result['document_type'] = doc_type
            result['confidence'] = self._calculate_confidence(result)
            
            return result
            
        except Exception as e:
            self.logger.error(f"Error in comprehensive extraction: {e}")
            return self._empty_result()
    
    def _identify_document_type(self, img_base64):
        """First pass: Identify document type and extract basic information"""
        prompt = """
        Analyze this tax document and identify:
        
        1. DOCUMENT TYPE: What specific tax form is this? Look for form numbers and titles.
        2. TAX YEAR: What tax year does this document relate to?
        3. AMENDMENT STATUS: Is this an amended, corrected, or superseded document?
        4. PRIMARY ENTITY: Who is the main subject/recipient of this document?
        
        Common document types to look for:
        - Form 1040 (Individual Income Tax Return)
        - Form W-2 (Wage and Tax Statement)
        - Form 1099 (various types: NEC, MISC, INT, DIV, R, etc.)
        - Schedule K-1 (Partner's Share of Income)
        - Form 1098 (Mortgage Interest Statement, Tuition Statement)
        - Form W-9 (Request for Taxpayer Identification)
        - State tax forms
        - Property tax statements
        - Bank/investment statements
        
        Return ONLY in this JSON format:
        {
            "document_type": "exact form name/type",
            "tax_year": "YYYY or null",
            "is_amended": true/false,
            "amendment_type": "AMENDED/CORRECTED/SUPERSEDED or null",
            "primary_entity_name": "name of primary person/entity or null"
        }
        """
        
        try:
            response = self.client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=300,
                messages=[{
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": "image/jpeg",
                                "data": img_base64
                            }
                        },
                        {
                            "type": "text",
                            "text": prompt
                        }
                    ]
                }]
            )
            
            content = response.content[0].text
            # Extract JSON from response
            json_match = re.search(r'\{.*\}', content, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group())
                return result.get('document_type', 'Unknown Document'), result
            else:
                return 'Unknown Document', {}
                
        except Exception as e:
            self.logger.error(f"Error in document identification: {e}")
            return 'Unknown Document', {}
    
    def _extract_k1_info(self, img_base64):
        """Extract K-1 specific information"""
        prompt = """
        This is a Schedule K-1 document. Extract the following information precisely:
        
        PARTNERSHIP/ENTITY INFORMATION (the issuer):
        - Partnership/Entity name
        - Partnership EIN
        - Partnership address
        - Form source (1065/1120S/1041)
        - Entity type (Partnership, S Corporation, Trust, Estate)
        
        PARTNER/SHAREHOLDER INFORMATION (the recipient):
        - Partner/shareholder name (FIRST and LAST name separately)
        - Partner's percentage or share (if visible)
        - Partner type (General Partner, Limited Partner, Shareholder, Beneficiary)
        - Partner's SSN or EIN (if visible)
        
        DOCUMENT DETAILS:
        - Tax year
        - Final K-1 indicator (check for "Final K-1" checkbox)
        - Amendment status
        
        Return ONLY in this JSON format:
        {
            "partnership_name": "name or null",
            "partnership_ein": "EIN or null",
            "partnership_address": "address or null",
            "form_source": "1065/1120S/1041 or null",
            "entity_type": "Partnership/S Corporation/Trust/Estate or null",
            "partner_first_name": "first name or null",
            "partner_last_name": "last name or null",
            "partner_percentage": "percentage or null",
            "partner_type": "type or null",
            "is_final_k1": true/false,
            "tax_year": "YYYY or null"
        }
        """
        
        return self._make_api_call(img_base64, prompt)
    
    def _extract_1099_info(self, img_base64):
        """Extract 1099 specific information"""
        prompt = """
        This is a Form 1099. Extract the following information precisely:
        
        PAYER INFORMATION (who paid):
        - Payer name (business/organization name)
        - Payer address
        - Payer's Federal ID number
        
        RECIPIENT INFORMATION (who received payment):
        - Recipient name (FIRST and LAST name separately if individual, or business name)
        - Recipient address
        - Recipient's TIN/SSN
        
        FORM DETAILS:
        - Specific 1099 type (1099-NEC, 1099-MISC, 1099-INT, 1099-DIV, etc.)
        - Tax year
        - Box amounts (key amounts paid)
        - Correction indicator
        
        BUSINESS CONTEXT:
        - Type of service/payment (for NEC/MISC)
        - Account designation (for investment forms)
        
        Return ONLY in this JSON format:
        {
            "form_type": "1099-XXX",
            "payer_name": "name or null",
            "payer_address": "address or null",
            "recipient_first_name": "first name or null",
            "recipient_last_name": "last name or null",
            "recipient_business_name": "business name if not individual or null",
            "payment_type": "service type or null",
            "tax_year": "YYYY or null",
            "is_corrected": true/false
        }
        """
        
        return self._make_api_call(img_base64, prompt)
    
    def _extract_w2_info(self, img_base64):
        """Extract W-2 specific information"""
        prompt = """
        This is a Form W-2. Extract the following information precisely:
        
        EMPLOYER INFORMATION:
        - Employer name
        - Employer address
        - Employer EIN
        
        EMPLOYEE INFORMATION:
        - Employee name (FIRST and LAST name separately)
        - Employee address
        - Employee SSN
        
        DOCUMENT DETAILS:
        - Tax year
        - Control number
        - Copy designation (Copy A, B, C, etc.)
        - State information (if state W-2)
        
        Return ONLY in this JSON format:
        {
            "employer_name": "name or null",
            "employer_address": "address or null",
            "employee_first_name": "first name or null",
            "employee_last_name": "last name or null",
            "employee_address": "address or null",
            "tax_year": "YYYY or null",
            "control_number": "number or null",
            "copy_designation": "copy type or null"
        }
        """
        
        return self._make_api_call(img_base64, prompt)
    
    def _extract_1098_info(self, img_base64):
        """Extract 1098 specific information"""
        prompt = """
        This is a Form 1098. Extract the following information precisely:
        
        LENDER/INSTITUTION INFORMATION:
        - Lender/institution name
        - Lender address
        - Lender TIN
        
        BORROWER/STUDENT INFORMATION:
        - Borrower/student name (FIRST and LAST name separately)
        - Borrower address
        - Borrower SSN
        
        FORM DETAILS:
        - Specific 1098 type (1098, 1098-E, 1098-T, etc.)
        - Tax year
        - Property address (for mortgage forms)
        - Account number
        
        Return ONLY in this JSON format:
        {
            "form_type": "1098-XXX or 1098",
            "lender_name": "name or null",
            "lender_address": "address or null",
            "borrower_first_name": "first name or null",
            "borrower_last_name": "last name or null",
            "property_address": "address or null",
            "account_number": "number or null",
            "tax_year": "YYYY or null"
        }
        """
        
        return self._make_api_call(img_base64, prompt)
    
    def _extract_1040_info(self, img_base64):
        """Extract 1040 specific information"""
        prompt = """
        This is a Form 1040. Extract the following information precisely:
        
        TAXPAYER INFORMATION:
        - Primary taxpayer name (FIRST and LAST name separately)
        - Spouse name if joint return (FIRST and LAST name separately)
        - Filing status (Single, Married Filing Jointly, etc.)
        - Address
        
        DOCUMENT DETAILS:
        - Tax year
        - Form type (1040, 1040EZ, 1040A, 1040NR, etc.)
        - Amendment status
        - State (if state return)
        
        Return ONLY in this JSON format:
        {
            "primary_first_name": "first name or null",
            "primary_last_name": "last name or null",
            "spouse_first_name": "first name or null",
            "spouse_last_name": "last name or null",
            "filing_status": "status or null",
            "form_type": "1040 variant",
            "tax_year": "YYYY or null",
            "is_joint_return": true/false,
            "state": "state code or null"
        }
        """
        
        return self._make_api_call(img_base64, prompt)
    
    def _extract_generic_info(self, img_base64):
        """Extract generic information for unknown document types"""
        prompt = """
        Extract any identifiable information from this document:
        
        PERSON/ENTITY INFORMATION:
        - Any person's name (FIRST and LAST name separately)
        - Any business/organization name
        - Address information
        
        DOCUMENT DETAILS:
        - Document type/title
        - Date or year information
        - Account numbers or reference numbers
        
        Return ONLY in this JSON format:
        {
            "person_first_name": "first name or null",
            "person_last_name": "last name or null",
            "business_name": "business name or null",
            "document_title": "title or null",
            "year": "YYYY or null",
            "reference_number": "number or null"
        }
        """
        
        return self._make_api_call(img_base64, prompt)
    
    def _make_api_call(self, img_base64, prompt):
        """Make API call to Claude and parse JSON response"""
        try:
            response = self.client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=500,
                messages=[{
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": "image/jpeg",
                                "data": img_base64
                            }
                        },
                        {
                            "type": "text",
                            "text": prompt
                        }
                    ]
                }]
            )
            
            content = response.content[0].text
            # Extract JSON from response
            json_match = re.search(r'\{.*\}', content, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())
            else:
                return {}
                
        except Exception as e:
            self.logger.error(f"Error in API call: {e}")
            return {}
    
    def _calculate_confidence(self, result):
        """Calculate confidence score based on extracted information completeness"""
        score = 0.0
        total_fields = 0
        filled_fields = 0
        
        # Count filled vs total fields (excluding null values)
        for key, value in result.items():
            if key not in ['confidence', 'document_type']:
                total_fields += 1
                if value and value != 'null' and str(value).strip():
                    filled_fields += 1
        
        if total_fields > 0:
            score = filled_fields / total_fields
        
        # Bonus for having key information
        if result.get('tax_year'):
            score += 0.1
        if result.get('document_type') and result['document_type'] != 'Unknown Document':
            score += 0.1
        
        return min(1.0, score)
    
    def _empty_result(self):
        """Return empty result structure"""
        return {
            'document_type': 'Unknown Document',
            'tax_year': None,
            'confidence': 0.0,
            'is_amended': False,
            'amendment_type': None
        }
    
    def detect_business_entity_type(self, text):
        """Detect business entity type from text"""
        if not text:
            return 'Individual', text
        
        text_upper = text.upper()
        
        for entity_type, indicators in self.entity_indicators.items():
            for indicator in indicators:
                if indicator in text_upper:
                    return entity_type, text
        
        return 'Individual', text
    
    def extract_client_name_legacy(self, image_path):
        """
        Legacy method for backward compatibility
        Extract client name and tax year from document
        Returns: (first_name, last_name, tax_year)
        """
        try:
            result = self.extract_comprehensive_document_info(image_path)
            
            # Extract first and last name from various possible fields
            first_name = (result.get('partner_first_name') or 
                         result.get('recipient_first_name') or 
                         result.get('employee_first_name') or 
                         result.get('borrower_first_name') or 
                         result.get('primary_first_name') or 
                         result.get('person_first_name'))
            
            last_name = (result.get('partner_last_name') or 
                        result.get('recipient_last_name') or 
                        result.get('employee_last_name') or 
                        result.get('borrower_last_name') or 
                        result.get('primary_last_name') or 
                        result.get('person_last_name'))
            
            tax_year = result.get('tax_year')
            
            return first_name, last_name, tax_year
            
        except Exception as e:
            self.logger.error(f"Error in legacy extraction: {e}")
            return None, None, None 