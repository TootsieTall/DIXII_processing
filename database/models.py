"""
Database models and Data Access Objects (DAOs) for tax document processing
"""

import logging
import uuid
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from dataclasses import dataclass
from database.supabase_client import get_supabase
import unicodedata
import re

logger = logging.getLogger(__name__)

@dataclass
class Client:
    """Client data model"""
    id: Optional[int] = None
    user_id: str = ""  # Supabase user ID
    first_name: str = ""
    last_name: str = ""
    name: str = ""  # Auto-generated from first_name + last_name
    normalized_name: str = ""
    email: Optional[str] = None
    phone: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    # Additional fields from views
    total_documents: int = 0
    completed_documents: int = 0
    error_documents: int = 0
    unique_tax_years: int = 0
    last_document_processed: Optional[datetime] = None

@dataclass
class ProcessingSession:
    """Processing session data model"""
    id: Optional[int] = None
    user_id: str = ""  # Supabase user ID
    session_id: str = ""
    status: str = "processing"
    processing_mode: str = "auto"
    total_files: int = 0
    completed_files: int = 0
    error_files: int = 0
    manual_client_info: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

@dataclass
class DocumentResult:
    """Document result data model"""
    id: Optional[int] = None
    user_id: str = ""  # Supabase user ID
    session_id: str = ""  # UUID string that references processing_sessions.session_id
    client_id: Optional[int] = None
    original_filename: str = ""
    new_filename: Optional[str] = None
    document_type: Optional[str] = None
    tax_year: Optional[int] = None
    client_name: Optional[str] = None
    client_folder: Optional[str] = None
    processed_path: Optional[str] = None
    status: str = "processing"
    confidence: Optional[float] = None
    error_message: Optional[str] = None
    processing_time_seconds: Optional[int] = None
    file_size_bytes: Optional[int] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

class ClientDAO:
    """Data Access Object for Client operations"""

    @staticmethod
    def normalize_name(first_name: str, last_name: str) -> str:
        """
        Normalize client name for case-insensitive storage and lookup

        Args:
            first_name: Client's first name
            last_name: Client's last name

        Returns:
            Normalized name string for database storage
        """
        if not first_name or not last_name:
            return ""

        # Convert to lowercase and normalize unicode
        normalized_first = unicodedata.normalize('NFD', first_name.lower())
        normalized_last = unicodedata.normalize('NFD', last_name.lower())

        # Remove diacritical marks (accents)
        first_clean = ''.join(c for c in normalized_first if unicodedata.category(c) != 'Mn')
        last_clean = ''.join(c for c in normalized_last if unicodedata.category(c) != 'Mn')

        # Remove extra whitespace and join
        first_clean = re.sub(r'\s+', ' ', first_clean.strip())
        last_clean = re.sub(r'\s+', ' ', last_clean.strip())

        return f"{first_clean} {last_clean}"

    @staticmethod
    def create_client(user_id: str, first_name: str, last_name: str, email: Optional[str] = None,
                     phone: Optional[str] = None) -> Optional[Client]:
        """
        Create a new client

        Args:
            user_id: Authenticated user ID
            first_name: Client's first name
            last_name: Client's last name
            email: Optional email address
            phone: Optional phone number

        Returns:
            Optional[Client]: Created client if successful, None otherwise
        """
        try:
            supabase = get_supabase()
            if not supabase:
                logger.warning("Database not available, cannot create client")
                return None

            normalized_name = ClientDAO.normalize_name(first_name, last_name)

            data = {
                'user_id': user_id,
                'first_name': first_name.strip(),
                'last_name': last_name.strip(),
                'normalized_name': normalized_name,
                'email': email.strip() if email else None,
                'phone': phone.strip() if phone else None
            }

            result = supabase.table('clients').insert(data).execute()

            if result.data:
                client_data = result.data[0]
                return Client(
                    id=client_data['id'],
                    user_id=client_data['user_id'],
                    first_name=client_data['first_name'],
                    last_name=client_data['last_name'],
                    normalized_name=client_data['normalized_name'],
                    email=client_data.get('email'),
                    phone=client_data.get('phone'),
                    created_at=datetime.fromisoformat(client_data['created_at'].replace('Z', '+00:00')),
                    updated_at=datetime.fromisoformat(client_data['updated_at'].replace('Z', '+00:00'))
                )

        except Exception as e:
            logger.error(f"Error creating client: {e}")

        return None

    @staticmethod
    def find_by_name(user_id: str, first_name: str, last_name: str) -> Optional[Client]:
        """
        Find client by name (case-insensitive) for specific user

        Args:
            user_id: Authenticated user ID
            first_name: Client's first name
            last_name: Client's last name

        Returns:
            Optional[Client]: Found client if exists, None otherwise
        """
        try:
            supabase = get_supabase()
            if not supabase:
                return None

            normalized_name = ClientDAO.normalize_name(first_name, last_name)

            result = supabase.table('clients').select('*')\
                .eq('user_id', user_id)\
                .eq('normalized_name', normalized_name)\
                .execute()

            if result.data:
                client_data = result.data[0]
                return Client(
                    id=client_data['id'],
                    user_id=client_data['user_id'],
                    first_name=client_data['first_name'],
                    last_name=client_data['last_name'],
                    normalized_name=client_data['normalized_name'],
                    email=client_data.get('email'),
                    phone=client_data.get('phone'),
                    created_at=datetime.fromisoformat(client_data['created_at'].replace('Z', '+00:00')),
                    updated_at=datetime.fromisoformat(client_data['updated_at'].replace('Z', '+00:00'))
                )

        except Exception as e:
            logger.error(f"Error finding client by name: {e}")

        return None

    @staticmethod
    def find_or_create(user_id: str, first_name: str, last_name: str, email: Optional[str] = None) -> Optional[Client]:
        """
        Find existing client or create new one

        Args:
            user_id: Authenticated user ID
            first_name: Client's first name
            last_name: Client's last name
            email: Optional email address

        Returns:
            Optional[Client]: Found or created client if successful, None otherwise
        """
        # Try to find existing client first
        client = ClientDAO.find_by_name(user_id, first_name, last_name)
        if client:
            return client

        # Create new client if not found
        return ClientDAO.create_client(user_id, first_name, last_name, email)

    @staticmethod
    def get_all_with_stats(user_id: str) -> List[Client]:
        """
        Get all clients with document statistics for a specific user

        Args:
            user_id: Authenticated user ID

        Returns:
            List[Client]: List of clients with statistics
        """
        try:
            supabase = get_supabase()
            if not supabase:
                return []

            result = supabase.table('client_statistics').select('*').eq('user_id', user_id).execute()

            clients = []
            for client_data in result.data:
                client = Client(
                    id=client_data['id'],
                    user_id=client_data['user_id'],
                    first_name=client_data['first_name'],
                    last_name=client_data['last_name'],
                    name=client_data['name'],
                    normalized_name=client_data.get('normalized_name', ''),
                    email=client_data.get('email'),
                    phone=client_data.get('phone'),
                    created_at=datetime.fromisoformat(client_data['created_at'].replace('Z', '+00:00')),
                    total_documents=client_data.get('total_documents', 0),
                    completed_documents=client_data.get('completed_documents', 0),
                    error_documents=client_data.get('error_documents', 0),
                    unique_tax_years=client_data.get('unique_tax_years', 0)
                )

                if client_data.get('last_document_processed'):
                    client.last_document_processed = datetime.fromisoformat(
                        client_data['last_document_processed'].replace('Z', '+00:00')
                    )

                clients.append(client)

            return clients

        except Exception as e:
            logger.error(f"Error getting clients with stats: {e}")
            return []

    @staticmethod
    def get_by_id(user_id: str, client_id: int) -> Optional[Client]:
        """
        Get client by ID for a specific user

        Args:
            user_id: Authenticated user ID
            client_id: Client's ID

        Returns:
            Optional[Client]: Found client if exists, None otherwise
        """
        try:
            supabase = get_supabase()
            if not supabase:
                return None

            result = supabase.table('clients').select('*')\
                .eq('user_id', user_id)\
                .eq('id', client_id)\
                .execute()

            if result.data:
                client_data = result.data[0]
                return Client(
                    id=client_data['id'],
                    user_id=client_data['user_id'],
                    first_name=client_data['first_name'],
                    last_name=client_data['last_name'],
                    normalized_name=client_data['normalized_name'],
                    email=client_data.get('email'),
                    phone=client_data.get('phone'),
                    created_at=datetime.fromisoformat(client_data['created_at'].replace('Z', '+00:00')),
                    updated_at=datetime.fromisoformat(client_data['updated_at'].replace('Z', '+00:00'))
                )

        except Exception as e:
            logger.error(f"Error getting client by ID: {e}")

        return None

class ProcessingSessionDAO:
    """Data Access Object for ProcessingSession operations"""

    @staticmethod
    def create_session(user_id: str, session_id: str, processing_mode: str = "auto",
                      total_files: int = 0, manual_client_info: Optional[Dict] = None) -> Optional[ProcessingSession]:
        """
        Create a new processing session

        Args:
            user_id: Authenticated user ID
            session_id: Unique session identifier (UUID string)
            processing_mode: Processing mode (auto/manual)
            total_files: Total number of files to process
            manual_client_info: Manual client info if provided

        Returns:
            Optional[ProcessingSession]: Created session if successful, None otherwise
        """
        try:
            supabase = get_supabase()
            if not supabase:
                logger.warning("Database not available, cannot create processing session")
                return None

            data = {
                'user_id': user_id,
                'session_id': session_id,  # This will be stored as UUID
                'status': 'processing',
                'processing_mode': processing_mode,
                'total_files': total_files,
                'completed_files': 0,
                'error_files': 0,
                'manual_client_info': manual_client_info,
                'started_at': datetime.utcnow().isoformat()
            }

            result = supabase.table('processing_sessions').insert(data).execute()

            if result.data:
                session_data = result.data[0]
                return ProcessingSession(
                    id=session_data['id'],  # This is the INTEGER primary key
                    user_id=session_data['user_id'],
                    session_id=session_data['session_id'],  # This is the UUID
                    status=session_data['status'],
                    processing_mode=session_data['processing_mode'],
                    total_files=session_data['total_files'],
                    completed_files=session_data['completed_files'],
                    error_files=session_data['error_files'],
                    manual_client_info=session_data.get('manual_client_info'),
                    started_at=datetime.fromisoformat(session_data['started_at'].replace('Z', '+00:00')),
                    created_at=datetime.fromisoformat(session_data['created_at'].replace('Z', '+00:00'))
                )

        except Exception as e:
            logger.error(f"Error creating processing session: {e}")

        return None

    @staticmethod
    def get_by_session_id(session_id: str) -> Optional[ProcessingSession]:
        """
        Get processing session by session_id

        Args:
            session_id: Session identifier

        Returns:
            Optional[ProcessingSession]: Found session if exists, None otherwise
        """
        try:
            supabase = get_supabase()
            if not supabase:
                return None

            result = supabase.table('processing_sessions').select('*').eq('session_id', session_id).execute()

            if result.data:
                session_data = result.data[0]
                return ProcessingSession(
                    id=session_data['id'],
                    session_id=session_data['session_id'],
                    status=session_data['status'],
                    processing_mode=session_data['processing_mode'],
                    total_files=session_data['total_files'],
                    completed_files=session_data['completed_files'],
                    error_files=session_data['error_files'],
                    manual_client_info=session_data.get('manual_client_info'),
                    error_message=session_data.get('error_message'),
                    started_at=datetime.fromisoformat(session_data['started_at'].replace('Z', '+00:00')) if session_data.get('started_at') else None,
                    completed_at=datetime.fromisoformat(session_data['completed_at'].replace('Z', '+00:00')) if session_data.get('completed_at') else None,
                    created_at=datetime.fromisoformat(session_data['created_at'].replace('Z', '+00:00')),
                    updated_at=datetime.fromisoformat(session_data['updated_at'].replace('Z', '+00:00'))
                )

        except Exception as e:
            logger.error(f"Error getting processing session: {e}")

        return None

    @staticmethod
    def update_session_status(session_id: str, status: str, error_message: Optional[str] = None,
                             completed_files: Optional[int] = None, error_files: Optional[int] = None) -> bool:
        """
        Update processing session status

        Args:
            session_id: Session identifier
            status: New status
            error_message: Error message if any
            completed_files: Number of completed files
            error_files: Number of files with errors

        Returns:
            bool: True if update successful, False otherwise
        """
        try:
            supabase = get_supabase()
            if not supabase:
                return False

            update_data = {'status': status}

            if error_message is not None:
                update_data['error_message'] = error_message

            if completed_files is not None:
                update_data['completed_files'] = completed_files

            if error_files is not None:
                update_data['error_files'] = error_files

            if status == 'completed':
                update_data['completed_at'] = datetime.utcnow().isoformat()

            result = supabase.table('processing_sessions').update(update_data).eq('session_id', session_id).execute()

            return len(result.data) > 0

        except Exception as e:
            logger.error(f"Error updating processing session: {e}")
            return False

    @staticmethod
    def get_recent_sessions(limit: int = 10) -> List[ProcessingSession]:
        """
        Get recent processing sessions

        Args:
            limit: Maximum number of sessions to return

        Returns:
            List[ProcessingSession]: List of recent sessions
        """
        try:
            supabase = get_supabase()
            if not supabase:
                return []

            result = supabase.table('processing_sessions')\
                .select('*')\
                .order('created_at', desc=True)\
                .limit(limit)\
                .execute()

            sessions = []
            for session_data in result.data:
                session = ProcessingSession(
                    id=session_data['id'],
                    session_id=session_data['session_id'],
                    status=session_data['status'],
                    processing_mode=session_data['processing_mode'],
                    total_files=session_data['total_files'],
                    completed_files=session_data['completed_files'],
                    error_files=session_data['error_files'],
                    manual_client_info=session_data.get('manual_client_info'),
                    error_message=session_data.get('error_message'),
                    started_at=datetime.fromisoformat(session_data['started_at'].replace('Z', '+00:00')) if session_data.get('started_at') else None,
                    completed_at=datetime.fromisoformat(session_data['completed_at'].replace('Z', '+00:00')) if session_data.get('completed_at') else None,
                    created_at=datetime.fromisoformat(session_data['created_at'].replace('Z', '+00:00')),
                    updated_at=datetime.fromisoformat(session_data['updated_at'].replace('Z', '+00:00'))
                )
                sessions.append(session)

            return sessions

        except Exception as e:
            logger.error(f"Error getting recent sessions: {e}")
            return []

class DocumentResultDAO:
    """Data Access Object for DocumentResult operations"""

    @staticmethod
    def create_document_result(user_id: str, session_uuid: str, original_filename: str,
                              client_id: Optional[int] = None) -> Optional[DocumentResult]:
        """
        Create a new document result

        Args:
            user_id: Authenticated user ID
            session_uuid: Session UUID string from processing_sessions.session_id
            original_filename: Original filename
            client_id: Optional client ID

        Returns:
            Optional[DocumentResult]: Created document result if successful, None otherwise
        """
        try:
            supabase = get_supabase()
            if not supabase:
                logger.warning("Database not available, cannot create document result")
                return None

            data = {
                'user_id': user_id,
                'session_id': session_uuid,  # Use the UUID string directly
                'client_id': client_id,
                'original_filename': original_filename,
                'status': 'waiting'
            }

            result = supabase.table('document_results').insert(data).execute()

            if result.data:
                doc_data = result.data[0]
                return DocumentResult(
                    id=doc_data['id'],
                    user_id=doc_data['user_id'],
                    session_id=doc_data['session_id'],
                    client_id=doc_data.get('client_id'),
                    original_filename=doc_data['original_filename'],
                    status=doc_data['status'],
                    created_at=datetime.fromisoformat(doc_data['created_at'].replace('Z', '+00:00'))
                )

        except Exception as e:
            logger.error(f"Error creating document result: {e}")

        return None

    @staticmethod
    def update_document_result(doc_id: str, **kwargs) -> bool:
        """
        Update document result

        Args:
            doc_id: Document result ID
            **kwargs: Fields to update

        Returns:
            bool: True if update successful, False otherwise
        """
        try:
            supabase = get_supabase()
            if not supabase:
                return False

            # Filter out None values and prepare update data
            update_data = {k: v for k, v in kwargs.items() if v is not None}

            if not update_data:
                return True

            result = supabase.table('document_results').update(update_data).eq('id', doc_id).execute()

            return len(result.data) > 0

        except Exception as e:
            logger.error(f"Error updating document result: {e}")
            return False

    @staticmethod
    def get_by_session_id(session_uuid: str) -> List[DocumentResult]:
        """
        Get all document results for a session

        Args:
            session_uuid: Session UUID string from processing_sessions.session_id

        Returns:
            List[DocumentResult]: List of document results
        """
        try:
            supabase = get_supabase()
            if not supabase:
                return []

            result = supabase.table('document_results')\
                .select('*')\
                .eq('session_id', session_uuid)\
                .order('created_at')\
                .execute()

            documents = []
            for doc_data in result.data:
                doc = DocumentResult(
                    id=doc_data['id'],
                    session_id=doc_data['session_id'],
                    client_id=doc_data.get('client_id'),
                    original_filename=doc_data['original_filename'],
                    new_filename=doc_data.get('new_filename'),
                    document_type=doc_data.get('document_type'),
                    tax_year=doc_data.get('tax_year'),
                    client_name=doc_data.get('client_name'),
                    client_folder=doc_data.get('client_folder'),
                    processed_path=doc_data.get('processed_path'),
                    status=doc_data['status'],
                    confidence=float(doc_data['confidence']) if doc_data.get('confidence') else None,
                    error_message=doc_data.get('error_message'),
                    processing_time_seconds=doc_data.get('processing_time_seconds'),
                    file_size_bytes=doc_data.get('file_size_bytes'),
                    created_at=datetime.fromisoformat(doc_data['created_at'].replace('Z', '+00:00')),
                    updated_at=datetime.fromisoformat(doc_data['updated_at'].replace('Z', '+00:00'))
                )
                documents.append(doc)

            return documents

        except Exception as e:
            logger.error(f"Error getting document results by session: {e}")
            return []

    @staticmethod
    def get_by_client_id(client_id: int, limit: Optional[int] = None) -> List[DocumentResult]:
        """
        Get document results for a specific client

        Args:
            client_id: Client ID
            limit: Optional limit on number of results

        Returns:
            List[DocumentResult]: List of document results
        """
        try:
            supabase = get_supabase()
            if not supabase:
                return []

            query = supabase.table('document_results')\
                .select('*')\
                .eq('client_id', client_id)\
                .order('created_at', desc=True)

            if limit:
                query = query.limit(limit)

            result = query.execute()

            documents = []
            for doc_data in result.data:
                doc = DocumentResult(
                    id=doc_data['id'],
                    session_id=doc_data['session_id'],
                    client_id=doc_data.get('client_id'),
                    original_filename=doc_data['original_filename'],
                    new_filename=doc_data.get('new_filename'),
                    document_type=doc_data.get('document_type'),
                    tax_year=doc_data.get('tax_year'),
                    client_name=doc_data.get('client_name'),
                    client_folder=doc_data.get('client_folder'),
                    processed_path=doc_data.get('processed_path'),
                    status=doc_data['status'],
                    confidence=float(doc_data['confidence']) if doc_data.get('confidence') else None,
                    error_message=doc_data.get('error_message'),
                    processing_time_seconds=doc_data.get('processing_time_seconds'),
                    file_size_bytes=doc_data.get('file_size_bytes'),
                    created_at=datetime.fromisoformat(doc_data['created_at'].replace('Z', '+00:00')),
                    updated_at=datetime.fromisoformat(doc_data['updated_at'].replace('Z', '+00:00'))
                )
                documents.append(doc)

            return documents

        except Exception as e:
            logger.error(f"Error getting document results by client: {e}")
            return []

    @staticmethod
    def search_documents(client_name: Optional[str] = None, document_type: Optional[str] = None,
                        tax_year: Optional[int] = None, limit: int = 100) -> List[DocumentResult]:
        """
        Search documents with filters using database search function

        Args:
            client_name: Optional client name filter
            document_type: Optional document type filter
            tax_year: Optional tax year filter
            limit: Maximum number of results

        Returns:
            List[DocumentResult]: List of matching document results
        """
        try:
            supabase = get_supabase()
            if not supabase:
                return []

            # Use the database search function
            search_query = client_name or ''
            result = supabase.rpc(
                'search_documents',
                {
                    'search_query': search_query,
                    'client_id_filter': None,
                    'document_type_filter': document_type,
                    'tax_year_filter': tax_year,
                    'limit_count': limit
                }
            ).execute()

            documents = []
            for doc_data in result.data:
                doc = DocumentResult(
                    id=doc_data['id'],
                    session_id=doc_data['session_id'],
                    client_id=doc_data.get('client_id'),
                    original_filename=doc_data['original_filename'],
                    new_filename=doc_data.get('new_filename'),
                    document_type=doc_data.get('document_type'),
                    tax_year=doc_data.get('tax_year'),
                    client_name=doc_data.get('client_name'),
                    status=doc_data['status'],
                    confidence=float(doc_data['confidence']) if doc_data.get('confidence') else None,
                    created_at=datetime.fromisoformat(doc_data['created_at'].replace('Z', '+00:00'))
                )
                documents.append(doc)

            return documents

        except Exception as e:
            logger.error(f"Error searching documents: {e}")
            return []

class StatisticsDAO:
    """Data Access Object for statistics and analytics"""

    @staticmethod
    def get_processing_statistics(days: int = 30) -> Dict[str, Any]:
        """
        Get processing statistics for the last N days

        Args:
            days: Number of days to look back

        Returns:
            Dict[str, Any]: Statistics data
        """
        try:
            supabase = get_supabase()
            if not supabase:
                return {}

            # Get summary stats
            end_date = datetime.utcnow()
            start_date = end_date - timedelta(days=days)

            # Get session stats
            session_result = supabase.table('processing_sessions')\
                .select('*')\
                .gte('created_at', start_date.isoformat())\
                .lte('created_at', end_date.isoformat())\
                .execute()

            # Get document stats
            doc_result = supabase.table('document_results')\
                .select('*')\
                .gte('created_at', start_date.isoformat())\
                .lte('created_at', end_date.isoformat())\
                .execute()

            sessions = session_result.data
            documents = doc_result.data

            total_sessions = len(sessions)
            completed_sessions = len([s for s in sessions if s['status'] == 'completed'])
            error_sessions = len([s for s in sessions if s['status'] == 'error'])

            total_documents = len(documents)
            completed_documents = len([d for d in documents if d['status'] == 'completed'])
            error_documents = len([d for d in documents if d['status'] == 'error'])

            # Calculate unique clients
            unique_clients = len(set(d['client_id'] for d in documents if d.get('client_id')))

            return {
                'period_days': days,
                'total_sessions': total_sessions,
                'completed_sessions': completed_sessions,
                'error_sessions': error_sessions,
                'session_success_rate': (completed_sessions / total_sessions * 100) if total_sessions > 0 else 0,
                'total_documents': total_documents,
                'completed_documents': completed_documents,
                'error_documents': error_documents,
                'document_success_rate': (completed_documents / total_documents * 100) if total_documents > 0 else 0,
                'unique_clients': unique_clients,
                'start_date': start_date.isoformat(),
                'end_date': end_date.isoformat()
            }

        except Exception as e:
            logger.error(f"Error getting processing statistics: {e}")
            return {}

    @staticmethod
    def get_document_type_summary() -> List[Dict[str, Any]]:
        """
        Get document type summary from view

        Returns:
            List[Dict[str, Any]]: Document type statistics
        """
        try:
            supabase = get_supabase()
            if not supabase:
                return []

            result = supabase.table('document_type_statistics').select('*').execute()

            return result.data

        except Exception as e:
            logger.error(f"Error getting document type summary: {e}")
            return []