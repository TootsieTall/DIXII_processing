"""
⚠️  DEPRECATION WARNING ⚠️ 
This legacy claude_ocr.py is deprecated and will be removed in a future version.
Please use models/enhanced_claude_ocr.py for advanced document processing.
See MIGRATION_GUIDE.md for details.
"""

import anthropic
import base64
import os
from PIL import Image
import io
import re
import warnings

# Issue deprecation warning
warnings.warn(
    "claude_ocr.py is deprecated. Use models/enhanced_claude_ocr.py instead.",
    DeprecationWarning,
    stacklevel=2
)

class ClaudeOCR:
    def __init__(self, api_key):
        self.client = anthropic.Anthropic(api_key=api_key)
        
    def image_to_base64(self, image_path):
        """Convert image to base64 for Claude API"""
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
                img.save(buffer, format='JPEG', quality=85)
                img_data = buffer.getvalue()
                return base64.b64encode(img_data).decode('utf-8')
        except Exception as e:
            print(f"Error converting image to base64: {e}")
            return None
    
    def extract_client_info(self, image_path):
        """
        Extract client name and tax year from document using Claude
        Returns: (first_name, last_name, tax_year)
        """
        try:
            # Convert image to base64
            img_base64 = self.image_to_base64(image_path)
            if not img_base64:
                return None, None, None
            
            # Prepare the prompt
            prompt = """
            Please analyze this tax document and extract the following information:
            1. Client's first name
            2. Client's last name  
            3. Tax year (the year this tax document is for)
            
            Look for:
            - Names in fields like "Name", "Taxpayer name", "Employee name", etc.
            - Tax year information (usually prominently displayed, like "2023", "2022", etc.)
            - Form headers that indicate the tax year
            
            Return ONLY the information in this exact format:
            FIRST_NAME: [first name or UNKNOWN]
            LAST_NAME: [last name or UNKNOWN]
            TAX_YEAR: [4-digit year or UNKNOWN]
            
            If any information cannot be clearly determined, use "UNKNOWN" for that field.
            Be conservative - only extract information you are confident about.
            """
            
            # Make API call to Claude
            response = self.client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=200,
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
            
            # Parse the response
            content = response.content[0].text
            return self._parse_claude_response(content)
            
        except Exception as e:
            print(f"Error extracting client info with Claude: {e}")
            return None, None, None
    
    def _parse_claude_response(self, response_text):
        """Parse Claude's response to extract structured data"""
        try:
            first_name = None
            last_name = None
            tax_year = None
            
            # Extract first name
            first_match = re.search(r'FIRST_NAME:\s*([^\n]+)', response_text)
            if first_match:
                first_name = first_match.group(1).strip()
                if first_name.upper() == 'UNKNOWN':
                    first_name = None
            
            # Extract last name
            last_match = re.search(r'LAST_NAME:\s*([^\n]+)', response_text)
            if last_match:
                last_name = last_match.group(1).strip()
                if last_name.upper() == 'UNKNOWN':
                    last_name = None
            
            # Extract tax year
            year_match = re.search(r'TAX_YEAR:\s*([^\n]+)', response_text)
            if year_match:
                tax_year = year_match.group(1).strip()
                if tax_year.upper() == 'UNKNOWN':
                    tax_year = None
                else:
                    # Validate year format
                    if re.match(r'^\d{4}$', tax_year):
                        tax_year = int(tax_year)
                    else:
                        tax_year = None
            
            return first_name, last_name, tax_year
            
        except Exception as e:
            print(f"Error parsing Claude response: {e}")
            return None, None, None
    

    def extract_tax_year_only(self, image_path):
        """
        Extract only the tax year from document (for manual mode)
        Returns: tax_year
        """
        try:
            # Convert image to base64
            img_base64 = self.image_to_base64(image_path)
            if not img_base64:
                return None
            
            # Prepare the prompt
            prompt = """
            Please analyze this tax document and extract ONLY the tax year.
            
            Look for:
            - Tax year information (usually prominently displayed, like "2023", "2022", etc.)
            - Form headers that indicate the tax year
            - Year fields on the document
            
            Return ONLY the information in this exact format:
            TAX_YEAR: [4-digit year or UNKNOWN]
            
            If the tax year cannot be clearly determined, use "UNKNOWN".
            """
            
            # Make API call to Claude
            response = self.client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=100,
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
            
            # Parse the response
            content = response.content[0].text
            
            # Extract tax year
            year_match = re.search(r'TAX_YEAR:\s*([^\n]+)', content)
            if year_match:
                tax_year = year_match.group(1).strip()
                if tax_year.upper() == 'UNKNOWN':
                    return None
                else:
                    # Validate year format
                    if re.match(r'^\d{4}$', tax_year):
                        return int(tax_year)
                    else:
                        return None
            
            return None
            
        except Exception as e:
            print(f"Error extracting tax year with Claude: {e}")
            return None

    def extract_comprehensive_info(self, image_path):
        """
        Comprehensive extraction that tries to get client name, document type, and tax year all at once
        This is used as a final attempt before marking anything as unknown
        Returns: (first_name, last_name, tax_year, document_type)
        """
        try:
            # Convert image to base64
            img_base64 = self.image_to_base64(image_path)
            if not img_base64:
                return None, None, None, "Unknown Document"
            
            prompt = """
            Please analyze this document very carefully and extract ALL available information.
            This is a comprehensive analysis - please look thoroughly for any identifying information.
            
            Extract the following:
            1. Client's first name (any person's name on the document - taxpayer, employee, recipient, etc.)
            2. Client's last name
            3. Tax year (the year this document relates to)
            4. Document type
            
            Look everywhere for names:
            - Header sections with taxpayer information
            - Employee/recipient name fields
            - Signature areas
            - Address sections
            - Any person identified on the document
            
            Look for tax years:
            - Form headers (e.g., "2023 Form 1040")
            - Tax year fields
            - Period covered dates
            - Any 4-digit year prominently displayed
            
            Common document types:
            - Form 1040, Form W-2, Form 1099 (various types)
            - Form W-9, Form 8889, State tax returns
            - Property tax statements, Bank statements
            - Investment statements, Tax notices
            
            Return information in this EXACT format:
            FIRST_NAME: [first name or UNKNOWN]
            LAST_NAME: [last name or UNKNOWN]
            TAX_YEAR: [4-digit year or UNKNOWN]
            DOCUMENT_TYPE: [specific document type or UNKNOWN]
            
            Be thorough but conservative - only extract information you can clearly see.
            If any information is unclear or not visible, use "UNKNOWN" for that field.
            """
            
            # Make API call to Claude
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
            
            # Parse the response
            content = response.content[0].text
            first_name, last_name, tax_year = self._parse_claude_response(content)
            
            # Extract document type
            doc_match = re.search(r'DOCUMENT_TYPE:\s*([^\n]+)', content)
            document_type = "Unknown Document"
            if doc_match:
                doc_type = doc_match.group(1).strip()
                if doc_type.upper() != 'UNKNOWN':
                    document_type = doc_type
            
            return first_name, last_name, tax_year, document_type
            
        except Exception as e:
            print(f"Error in comprehensive extraction with Claude: {e}")
            return None, None, None, "Unknown Document"

    def classify_unknown_document(self, image_path):
        """
        Use Claude to classify documents that donut couldn't recognize
        Returns: document_type
        """
        try:
            # Convert image to base64
            img_base64 = self.image_to_base64(image_path)
            if not img_base64:
                return "Unknown Document"
            
            prompt = """
            Please analyze this document and determine what type of tax document it is.
            
            Common tax document types include:
            - Form 1040 (Individual Income Tax Return)
            - Form W-2 (Wage and Tax Statement)
            - Form 1099 (various types like 1099-INT, 1099-DIV, etc.)
            - Form 8889 (Health Savings Account)
            - State tax returns
            - Property tax statements
            - Tax letters or notices
            - Bank statements
            - Investment statements
            
            Return ONLY the document type in this format:
            DOCUMENT_TYPE: [specific document type]
            
            If you cannot determine the document type, respond with:
            DOCUMENT_TYPE: Unknown Document
            """
            
            # Make API call to Claude
            response = self.client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=100,
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
            
            # Parse the response
            content = response.content[0].text
            doc_match = re.search(r'DOCUMENT_TYPE:\s*([^\n]+)', content)
            if doc_match:
                return doc_match.group(1).strip()
            else:
                return "Unknown Document"
            
        except Exception as e:
            print(f"Error classifying unknown document with Claude: {e}")
            return "Unknown Document"

    def generate_misc_document_name(self, image_path):
        """
        Use Claude to generate a descriptive name for misc documents
        Returns: short_document_name (4 words or less)
        """
        try:
            # Convert image to base64
            img_base64 = self.image_to_base64(image_path)
            if not img_base64:
                return "Misc Document"
            
            prompt = """
            Please analyze this document and provide a short, descriptive name that captures what this document is.
            
            Requirements:
            - The name should be 4 words or less
            - Be specific but concise
            - Use proper capitalization
            - Focus on the document's purpose or content
            
            Examples of good names:
            - "Bank Statement"
            - "Insurance Form"
            - "Investment Summary"
            - "Tax Notice"
            - "Receipt Document"
            - "Legal Notice"
            - "Medical Form"
            
            Return ONLY the document name in this format:
            DOCUMENT_NAME: [short descriptive name]
            
            If you cannot determine a specific name, respond with:
            DOCUMENT_NAME: Misc Document
            """
            
            # Make API call to Claude
            response = self.client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=100,
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
            
            # Parse the response
            content = response.content[0].text
            name_match = re.search(r'DOCUMENT_NAME:\s*([^\n]+)', content)
            if name_match:
                document_name = name_match.group(1).strip()
                # Ensure it's 4 words or less
                words = document_name.split()
                if len(words) > 4:
                    document_name = ' '.join(words[:4])
                return document_name if document_name != "Misc Document" else "Misc Document"
            else:
                return "Misc Document"
            
        except Exception as e:
            print(f"Error generating misc document name with Claude: {e}")
            return "Misc Document" 