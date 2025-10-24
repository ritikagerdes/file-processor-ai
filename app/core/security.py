"""
Security utilities for HIPAA-compliant data handling.
"""

import hashlib
import hmac
import ipaddress
import secrets
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Union

from cryptography.fernet import Fernet
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel

from app.config import settings


class SecurityError(Exception):
    """Custom security exception."""
    pass


class IPWhitelistError(SecurityError):
    """IP address not in whitelist."""
    pass


class TokenError(SecurityError):
    """Invalid or expired token."""
    pass


class EncryptionError(SecurityError):
    """Encryption/decryption error."""
    pass


class SecurityManager:
    """Manages security operations including encryption, authentication, and IP whitelisting."""
    
    def __init__(self):
        """Initialize security manager with encryption and password hashing."""
        self.pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
        self.fernet = Fernet(settings.encryption_key.encode())
        self.allowed_ips = self._parse_ip_ranges(settings.allowed_ips)
    
    def _parse_ip_ranges(self, ip_strings: List[str]) -> List[Union[ipaddress.IPv4Network, ipaddress.IPv6Network]]:
        """Parse IP addresses and CIDR blocks into network objects."""
        networks = []
        for ip_str in ip_strings:
            try:
                if '/' in ip_str:
                    networks.append(ipaddress.ip_network(ip_str, strict=False))
                else:
                    networks.append(ipaddress.ip_address(ip_str))
            except ValueError as e:
                raise SecurityError(f"Invalid IP address or CIDR block: {ip_str}") from e
        return networks
    
    def verify_ip_address(self, client_ip: str) -> bool:
        """
        Verify if client IP address is in the whitelist.
        
        Args:
            client_ip: Client IP address to verify
            
        Returns:
            True if IP is allowed, False otherwise
            
        Raises:
            IPWhitelistError: If IP is not in whitelist
        """
        try:
            client_ip_obj = ipaddress.ip_address(client_ip)
            for allowed_network in self.allowed_ips:
                if isinstance(allowed_network, (ipaddress.IPv4Network, ipaddress.IPv6Network)):
                    if client_ip_obj in allowed_network:
                        return True
                elif client_ip_obj == allowed_network:
                    return True
            return False
        except ValueError as e:
            raise IPWhitelistError(f"Invalid IP address format: {client_ip}") from e
    
    def hash_password(self, password: str) -> str:
        """
        Hash a password using bcrypt.
        
        Args:
            password: Plain text password
            
        Returns:
            Hashed password
        """
        return self.pwd_context.hash(password)
    
    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """
        Verify a password against its hash.
        
        Args:
            plain_password: Plain text password
            hashed_password: Hashed password
            
        Returns:
            True if password matches, False otherwise
        """
        return self.pwd_context.verify(plain_password, hashed_password)
    
    def create_access_token(self, data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
        """
        Create a JWT access token.
        
        Args:
            data: Data to encode in the token
            expires_delta: Token expiration time
            
        Returns:
            Encoded JWT token
        """
        to_encode = data.copy()
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(minutes=settings.access_token_expire_minutes)
        
        to_encode.update({"exp": expire})
        encoded_jwt = jwt.encode(to_encode, settings.secret_key, algorithm=settings.algorithm)
        return encoded_jwt
    
    def verify_token(self, token: str) -> Dict[str, Any]:
        """
        Verify and decode a JWT token.
        
        Args:
            token: JWT token to verify
            
        Returns:
            Decoded token data
            
        Raises:
            TokenError: If token is invalid or expired
        """
        try:
            payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
            return payload
        except JWTError as e:
            raise TokenError(f"Invalid token: {str(e)}") from e
    
    def encrypt_data(self, data: str) -> bytes:
        """
        Encrypt sensitive data.
        
        Args:
            data: Data to encrypt
            
        Returns:
            Encrypted data as bytes
            
        Raises:
            EncryptionError: If encryption fails
        """
        try:
            return self.fernet.encrypt(data.encode())
        except Exception as e:
            raise EncryptionError(f"Failed to encrypt data: {str(e)}") from e
    
    def decrypt_data(self, encrypted_data: bytes) -> str:
        """
        Decrypt sensitive data.
        
        Args:
            encrypted_data: Encrypted data as bytes
            
        Returns:
            Decrypted data as string
            
        Raises:
            EncryptionError: If decryption fails
        """
        try:
            return self.fernet.decrypt(encrypted_data).decode()
        except Exception as e:
            raise EncryptionError(f"Failed to decrypt data: {str(e)}") from e
    
    def generate_secure_filename(self, original_filename: str, client_id: str) -> str:
        """
        Generate a secure filename for storage.
        
        Args:
            original_filename: Original filename
            client_id: Client identifier
            
        Returns:
            Secure filename
        """
        # Create a hash of the original filename and client ID
        hash_input = f"{original_filename}_{client_id}_{secrets.token_hex(16)}"
        file_hash = hashlib.sha256(hash_input.encode()).hexdigest()[:16]
        
        # Get file extension
        if '.' in original_filename:
            extension = original_filename.split('.')[-1]
            return f"{file_hash}.{extension}"
        return file_hash
    
    def create_audit_hash(self, data: str) -> str:
        """
        Create an audit hash for data integrity verification.
        
        Args:
            data: Data to hash
            
        Returns:
            SHA-256 hash of the data
        """
        return hashlib.sha256(data.encode()).hexdigest()


class TokenData(BaseModel):
    """Token data model."""
    client_id: Optional[str] = None
    username: Optional[str] = None
    permissions: List[str] = []


# Global security manager instance
security_manager = SecurityManager()